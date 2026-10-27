from __future__ import annotations

import sqlite3

from ._helper import read_only_authorizer

POLICIES = ("historical_static_catalog", "snapshot")
MUTABLE_FIELDS = ("price", "average_rating", "rating_number")


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
    masked = list(MUTABLE_FIELDS) if policy == "historical_static_catalog" else []
    record = {
        "name": policy, "version": 1, "as_of_timestamp": as_of_timestamp,
        "masked_fields": masked, "aggregate_observed_at": None,
        "metadata_temporal_validity": "unverified",
        "catalog_assumption": "static titles/taxonomy/store/full item vocabulary; availability as-of unverified",
        "historical_causal_claim": False,
        "snapshot_mutable_fields_used": policy == "snapshot",
    }
    if masked:
        conn = corpus._conn
        # Trusted setup only. TEMP view shadows items without copying or updating
        # the large corpus. Restore a SELECT-only authorizer even on failure.
        conn.set_authorizer(None)
        try:
            columns = [r[1] for r in conn.execute("PRAGMA main.table_info(items)")]
            projection = ", ".join(f'NULL AS "{c}"' if c in masked else f'"{c}"' for c in columns)
            conn.execute("PRAGMA query_only = OFF")
            conn.execute(f"CREATE TEMP VIEW items AS SELECT rowid AS rowid, {projection} FROM main.items")
        finally:
            conn.execute("PRAGMA query_only = ON")
            base = read_only_authorizer()

            def authorize(action, table, column, database, source):
                if action == sqlite3.SQLITE_READ and database == "main" and table == "items" and column in masked:
                    return sqlite3.SQLITE_DENY
                return base(action, table, column, database, source)

            conn.set_authorizer(authorize)
    corpus._evaluation_metadata_policy = record
    return dict(record)
