from __future__ import annotations

import sqlite3

from ._helper import read_only_authorizer
from ._sql import FTS_POPULATE_SQL, FTS_TABLE_SCHEMA

POLICIES = ("historical_static_catalog", "snapshot", "no_filter")
MUTABLE_FIELDS = ("price", "average_rating", "rating_number")
_PROTECTED_MAIN_TABLES = {"items", "item_categories"}


def apply_metadata_policy(corpus, policy: str, *, as_of_timestamp: int,
                          popularity: dict | None = None,
                          ratings: dict | None = None,
                          inferred_categories: dict | None = None,
                          availability: dict | None = None) -> dict:
    """Apply a metadata visibility policy to the corpus.

    ``popularity`` (optional): ``{item_id: interaction_count}`` from the fit
    split only — a causal, pre-as_of popularity proxy. When provided, a temp
    ``item_popularity`` table (with cnt/item_id indexes covering every visible
    item) lets FilterTool order by ``popularity`` even when mutable fields
    (rating_number etc.) are masked to NULL.

    ``ratings`` (optional): ``{item_id: mean_rating}`` from the fit split only
    — a causal proxy for masked ``average_rating``. Creates ``item_rating``
    covering every visible item (missing -> NULL) so ``min_rating`` filters and
    ``average_rating`` ordering can be evaluated without leaking the
    scrape-time snapshot.

    ``inferred_categories`` (optional): ``{item_id: category | [categories]}``
    for items that have NO rows in ``item_categories`` (the uncategorized
    tail). Inferred rows are unioned into the temp ``item_categories`` table
    for visible items only, so FilterTool category filters and FTS category
    text reach them. Items that already have real categories are never
    overridden.

    ``availability`` (optional): ``{item_id: avail_ts}`` — raw parseable
    ``details["Date First Available"]`` timestamps (epoch ms). When provided,
    an item is ALSO visible if its availability date is plausible and
    <= as_of, even when ``first_seen_ts`` (the interaction proxy) is later —
    the item existed but had no cleaned pre-cutoff interactions. Plausibility
    is enforced here: ``avail_ts >= 1995-01-01`` and, when ``first_seen_ts``
    exists, ``avail_ts <= first_seen_ts`` (a date after the first observed
    interaction is junk, e.g. "July 6, 1931" placeholders). This is a causal,
    fixed historical fact — unlike mutable snapshot fields.
    """
    if policy not in POLICIES:
        raise ValueError(f"metadata policy must be one of {POLICIES}")
    if isinstance(as_of_timestamp, bool) or not isinstance(as_of_timestamp, int) or as_of_timestamp <= 0:
        raise ValueError("a positive integer prediction cutoff is required")
    previous = getattr(corpus, "_evaluation_metadata_policy", None)
    if previous is not None:
        if previous["name"] != policy or previous["as_of_timestamp"] != as_of_timestamp:
            raise ValueError("metadata policy/cutoff already fixed; reload corpus to change")
        return dict(previous)

    # ------------------------------------------------------------------
    # no_filter: legacy corpus without first_seen_ts; expose full catalog.
    # No temporal filtering is applied; mutable fields are always visible.
    # ------------------------------------------------------------------
    if policy == "no_filter":
        conn = corpus._conn
        conn.set_authorizer(None)
        try:
            columns = [row[1] for row in conn.execute("PRAGMA main.table_info(items)")]
            projection = ", ".join(f'"{col}"' for col in columns)
            conn.execute("PRAGMA query_only = OFF")
            conn.execute(
                "CREATE TEMP VIEW IF NOT EXISTS items AS "
                f"SELECT rowid AS rowid, {projection} FROM main.items"
            )
            conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS item_categories AS "
                "SELECT c.rowid AS rowid, c.item_id, c.category FROM main.item_categories AS c "
                "JOIN temp.items AS i ON i.item_id = c.item_id"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_item_categories_item_id ON item_categories(item_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_item_categories_category ON item_categories(category)")
            temp_fts_schema = FTS_TABLE_SCHEMA.replace(
                "CREATE VIRTUAL TABLE items_fts", "CREATE VIRTUAL TABLE temp.items_fts", 1
            )
            conn.execute(temp_fts_schema)
            conn.execute(FTS_POPULATE_SQL)
            conn.commit()
        except Exception:
            conn.execute("PRAGMA query_only = OFF")
            for kind, name in (("table", "items_fts"), ("table", "item_categories"), ("view", "items")):
                try:
                    conn.execute(f"DROP {kind.upper()} IF EXISTS temp.{name}")
                except Exception:
                    pass
            conn.commit()
            raise
        finally:
            conn.execute("PRAGMA query_only = ON")
            base = read_only_authorizer()
            conn.set_authorizer(base)
        record = {
            "name": "no_filter",
            "version": 2,
            "as_of_timestamp": as_of_timestamp,
            "masked_fields": [],
            "first_seen_filter": False,
            "first_seen_proxy": "N/A — legacy corpus without first_seen_ts; full catalog exposed",
            "aggregate_observed_at": None,
            "metadata_temporal_validity": "none — static metadata only, no temporal filtering",
            "catalog_assumption": (
                "all items in corpus are visible; no first_seen_ts filter applied; "
                "legacy corpus (format_version=1) without temporal metadata"
            ),
            "historical_causal_claim": False,
            "snapshot_mutable_fields_used": True,
        }
        corpus._evaluation_metadata_policy = record
        return dict(record)

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
        "popularity_available": bool(popularity),
        "popularity_proxy": (
            "fit-split interaction count per item (causal: only pre-as_of "
            "interactions); exposed as temp.item_popularity for FilterTool "
            "order_by='popularity' when provided"
            if popularity else None
        ),
        "rating_proxy_available": bool(ratings),
        "rating_proxy": (
            "fit-split mean rating per item (causal: only pre-as_of "
            "interactions); exposed as temp.item_rating for FilterTool "
            "min_rating filter and order_by='average_rating' when provided"
            if ratings else None
        ),
        "inferred_categories": bool(inferred_categories),
        "availability_dates": bool(availability),
        "availability_proxy": (
            "details['Date First Available'] epoch-ms per item (fixed historical "
            "fact, causal); plausible dates (>=1995-01-01, <= first_seen_ts when "
            "known) also grant visibility at as_of — recovers items that existed "
            "but had no cleaned pre-cutoff interactions"
            if availability else None
        ),
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
        conn.execute("PRAGMA query_only = OFF")
        as_of = int(as_of_timestamp)
        avail_join = ""
        avail_where = ""
        item_alias = ""
        rowid_expr = "rowid"
        if availability:
            # avail_ts >= 1995-01-01 filters placeholder dates ("July 6, 1931",
            # "January 1, 1970"); avail_ts <= first_seen_ts filters impossible
            # future dates. Precompute the small set of items that become
            # visible ONLY via availability so per-query cost stays a PK
            # lookup — a per-row LEFT JOIN here exceeded the SQL time budget
            # on the 2.6M-item view (availability A/B exp_1, 2026-11-24).
            conn.execute(
                "CREATE TEMP TABLE item_availability (item_id TEXT PRIMARY KEY, avail_ts INTEGER)"
            )
            conn.executemany(
                "INSERT INTO item_availability VALUES (?, ?)",
                ((iid, int(ts)) for iid, ts in availability.items()),
            )
            conn.execute("CREATE TEMP TABLE avail_extra (item_id TEXT PRIMARY KEY)")
            conn.execute(
                "INSERT INTO avail_extra(item_id) "
                "SELECT a.item_id FROM temp.item_availability AS a "
                "JOIN main.items AS i ON i.item_id = a.item_id "
                "WHERE a.avail_ts >= 788918400000 "
                f"AND a.avail_ts <= {as_of} "
                "AND (i.first_seen_ts IS NULL OR i.first_seen_ts > "
                f"{as_of}) "
                "AND (i.first_seen_ts IS NULL OR a.avail_ts <= i.first_seen_ts)"
            )
            avail_where = " OR i.item_id IN (SELECT item_id FROM temp.avail_extra)"
            item_alias = "i."
            rowid_expr = "i.rowid"
        visibility_where = (
            f"(i.first_seen_ts IS NOT NULL AND i.first_seen_ts <= {as_of}{avail_where})"
        )
        projection = ", ".join(
            f'NULL AS "{column}"' if column in masked else f'{item_alias}"{column}"'
            for column in columns
        )
        if popularity:
            conn.execute(
                "CREATE TEMP TABLE item_popularity (item_id TEXT PRIMARY KEY, cnt INTEGER)"
            )
            conn.executemany(
                "INSERT INTO item_popularity VALUES (?, ?)",
                ((iid, int(c)) for iid, c in popularity.items()),
            )
            # Every visible item needs a row so FilterTool can INNER JOIN the
            # popularity index without silently dropping zero-fit items.
            conn.execute(
                "INSERT INTO item_popularity(item_id, cnt) "
                f"SELECT i.item_id, 0 FROM main.items AS i{avail_join} "
                f"WHERE {visibility_where} "
                "AND i.item_id NOT IN (SELECT item_id FROM item_popularity)"
            )
            conn.execute(
                "CREATE INDEX idx_item_popularity_cnt_desc "
                "ON item_popularity(cnt DESC, item_id)"
            )
            conn.execute(
                "CREATE INDEX idx_item_popularity_cnt_asc "
                "ON item_popularity(cnt ASC, item_id)"
            )
        if ratings:
            conn.execute(
                "CREATE TEMP TABLE item_rating (item_id TEXT PRIMARY KEY, avg_rating REAL)"
            )
            conn.executemany(
                "INSERT INTO item_rating VALUES (?, ?)",
                ((iid, float(r)) for iid, r in ratings.items()),
            )
            # Every visible item needs a row; items without fit ratings get
            # NULL so they sort last and fail min_rating thresholds honestly.
            conn.execute(
                "INSERT INTO item_rating(item_id, avg_rating) "
                f"SELECT i.item_id, NULL FROM main.items AS i{avail_join} "
                f"WHERE {visibility_where} "
                "AND i.item_id NOT IN (SELECT item_id FROM item_rating)"
            )
            # Expression index keeps NULL ratings last in BOTH directions.
            conn.execute(
                "CREATE INDEX idx_item_rating_desc "
                "ON item_rating(avg_rating IS NULL, avg_rating DESC, item_id)"
            )
            conn.execute(
                "CREATE INDEX idx_item_rating_asc "
                "ON item_rating(avg_rating IS NULL, avg_rating ASC, item_id)"
            )
        if availability:
            conn.execute(
                "CREATE TEMP VIEW items AS "
                f"SELECT {rowid_expr} AS rowid, {projection} FROM main.items AS i{avail_join} "
                f"WHERE {visibility_where}"
            )
        else:
            conn.execute(
                "CREATE TEMP VIEW items AS "
                f"SELECT rowid AS rowid, {projection} FROM main.items "
                f"WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= {as_of}"
            )
        conn.execute(
            "CREATE TEMP TABLE item_categories AS "
            "SELECT c.rowid AS rowid, c.item_id, c.category FROM main.item_categories AS c "
            "JOIN temp.items AS i ON i.item_id = c.item_id"
        )
        conn.execute("CREATE INDEX idx_temp_item_categories_item_id ON item_categories(item_id)")
        conn.execute("CREATE INDEX idx_temp_item_categories_category ON item_categories(category)")
        if inferred_categories:
            flat = []
            for iid, cats in inferred_categories.items():
                for cat in ([cats] if isinstance(cats, str) else list(cats)):
                    flat.append((iid, cat))
            conn.execute(
                "CREATE TEMP TABLE inferred_categories_raw (item_id TEXT, category TEXT)"
            )
            conn.executemany(
                "INSERT INTO inferred_categories_raw VALUES (?, ?)", flat
            )
            # Only items with NO real category rows get inferred ones, and only
            # when visible under the as-of filter.
            conn.execute(
                "INSERT INTO item_categories(item_id, category) "
                "SELECT r.item_id, r.category FROM inferred_categories_raw r "
                "JOIN temp.items i ON i.item_id = r.item_id "
                "WHERE NOT EXISTS (SELECT 1 FROM main.item_categories c "
                "WHERE c.item_id = r.item_id)"
            )
            record["inferred_categories_count"] = conn.execute(
                "SELECT changes()"
            ).fetchone()[0]
            conn.execute("DROP TABLE temp.inferred_categories_raw")
        temp_fts_schema = FTS_TABLE_SCHEMA.replace(
            "CREATE VIRTUAL TABLE items_fts", "CREATE VIRTUAL TABLE temp.items_fts", 1
        )
        conn.execute(temp_fts_schema)
        conn.execute(FTS_POPULATE_SQL)
        conn.commit()
    except Exception:
        conn.execute("PRAGMA query_only = OFF")
        for kind, name in (("table", "items_fts"), ("table", "item_categories"),
                           ("table", "item_popularity"), ("table", "item_rating"),
                           ("table", "item_availability"), ("table", "avail_extra"),
                           ("view", "items")):
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
