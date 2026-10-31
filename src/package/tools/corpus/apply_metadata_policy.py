from __future__ import annotations

import sqlite3

from ._helper import read_only_authorizer
from ._sql import FTS_POPULATE_SQL, FTS_TABLE_SCHEMA

POLICIES = ("historical_static_catalog", "snapshot")
MUTABLE_FIELDS = ("price", "average_rating", "rating_number")
_PROTECTED_MAIN_TABLES = {"items", "item_categories"}


def apply_metadata_policy(corpus, policy: str, *, as_of_timestamp: int) -> dict:
    if policy not in POLICIES:
        raise ValueError(f"metadata policy must be one of {POLICIES}")
    if isinstance(as_of_timestamp, bool) or not isinstance(as_of_timestamp, int) or as_of_timestamp <= 0:
        raise ValueError("a positive integer prediction cutoff is required")
    previous = getattr(corpus, "_evaluation_metadata_policy", None)
    if previous is not None:
        if previous["name"] != policy or previous["as_of_timestamp"] != as_of_timestamp:
            raise ValueError("metadata policy/cutoff already fixed; reload corpus to change")
        return dict(previous)

    conn = corpus._conn
    masked = list(MUTABLE_FIELDS) if policy == "historical_static_catalog" else []
    record = {
        "name": policy,
        "version": 2,
        "as_of_timestamp": as_of_timestamp,
        "masked_fields": masked,
        "first_seen_filter": True,
        "first_seen_proxy": "minimum timestamp per item in all cleaned interactions; not an actual launch/availability date",
        "aggregate_observed_at": None,
        "metadata_temporal_validity": "first_seen proxy only; static metadata validity unverified",
        "catalog_assumption": (
            "visible items satisfy first_seen_ts <= as_of_timestamp; first_seen_ts is a cleaned-interaction proxy, "
            "not launch date; title/taxonomy/store values remain static metadata with historical validity unverified"
        ),
        "historical_causal_claim": False,
        "snapshot_mutable_fields_used": policy == "snapshot",
    }

    # Trusted setup only. The TEMP items view keeps base rowids for FTS joins,
    # and categories/FTS are rebuilt over exactly that visible set. Main tables
    # remain immutable and are denied to all later user SQL.
    conn.set_authorizer(None)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA main.table_info(items)")]
        if "first_seen_ts" not in columns:
            raise ValueError("corpus lacks first_seen_ts; rebuild it from cleaned interactions before applying as-of policy")
        total_items = int(conn.execute("SELECT COUNT(*) FROM main.items").fetchone()[0])
        known_first_seen = int(conn.execute(
            "SELECT COUNT(*) FROM main.items WHERE first_seen_ts IS NOT NULL"
        ).fetchone()[0])
        if total_items and not known_first_seen:
            raise ValueError("corpus has no first_seen_ts values; rebuild it from cleaned interactions before applying as-of policy")
        projection = ", ".join(
            f'NULL AS "{column}"' if column in masked else f'"{column}"' for column in columns
        )
        conn.execute("PRAGMA query_only = OFF")
        conn.execute(
            "CREATE TEMP VIEW items AS "
            f"SELECT rowid AS rowid, {projection} FROM main.items "
            f"WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= {int(as_of_timestamp)}"
        )
        conn.execute(
            "CREATE TEMP VIEW item_categories AS "
            "SELECT c.item_id, c.category FROM main.item_categories AS c "
            "JOIN temp.items AS i ON i.item_id = c.item_id"
        )
        temp_fts_schema = FTS_TABLE_SCHEMA.replace(
            "CREATE VIRTUAL TABLE items_fts", "CREATE VIRTUAL TABLE temp.items_fts", 1
        )
        conn.execute(temp_fts_schema)
        conn.execute(FTS_POPULATE_SQL)
        conn.commit()
    except Exception:
        conn.execute("PRAGMA query_only = OFF")
        for kind, name in (("table", "items_fts"), ("view", "item_categories"), ("view", "items")):
            try:
                conn.execute(f"DROP {kind.upper()} IF EXISTS temp.{name}")
            except sqlite3.Error:
                pass
        conn.commit()
        raise
    finally:
        conn.execute("PRAGMA query_only = ON")

        base = read_only_authorizer()

        def authorize(action, table, column, database, source):
            if action == sqlite3.SQLITE_READ and database == "main":
                if table in _PROTECTED_MAIN_TABLES or table.startswith("items_fts"):
                    # Reads performed by the policy's own TEMP views are allowed;
                    # direct main.* reads and FTS shadow-table probes are denied.
                    if source not in {"items", "item_categories"}:
                        return sqlite3.SQLITE_DENY
                if table == "items" and column in masked:
                    return sqlite3.SQLITE_DENY
            return base(action, table, column, database, source)

        conn.set_authorizer(authorize)
    corpus._evaluation_metadata_policy = record
    return dict(record)
