"""Lightweight variant of avail_view_perf_probe: runs directly on the corpus
sqlite FILE (read-only, temp tables only) instead of a full :memory: backup.
Disk/page-cache bound but no multi-GB commit charge — relative baseline-vs-
availability timing is still the signal we need.

Run: PYTHONPATH=. python investigations/avail_view_perf_probe_file.py
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CORPUS = Path("resource/corpus/multi_domain/corpus_multi_domain.sqlite")
AVAIL = Path("resource/corpus/multi_domain/item_availability.parquet")
AS_OF = 1617737606549

QUERIES = {
    "count_items": "SELECT COUNT(*) FROM items",
    "light_filter": (
        "SELECT i.item_id, i.title, i.price, i.average_rating, i.rating_number "
        "FROM items AS i WHERE COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND i.item_id <> 'Electronics::B09S3N6X3L' "
        "ORDER BY i.rating_number DESC, i.item_id LIMIT 100"
    ),
    "not_exists": (
        "SELECT i.item_id, i.domain, i.title, i.store, i.price, "
        "i.average_rating, i.rating_number, i.main_category FROM items AS i "
        "WHERE i.item_id <> 'Electronics::B09S3N6X3L' "
        "AND COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND NOT EXISTS (SELECT 1 FROM item_categories AS c "
        "WHERE c.item_id = i.item_id AND c.category = 'Power Strips') "
        "ORDER BY i.rating_number DESC, i.item_id LIMIT 100"
    ),
}


def build_avail_extra(conn) -> int:
    """Replicates apply_metadata_policy's avail_extra on temp tables."""
    import pandas as pd
    av = pd.read_parquet(AVAIL)
    conn.execute("PRAGMA query_only = OFF")
    conn.execute("CREATE TEMP TABLE item_availability (item_id TEXT PRIMARY KEY, avail_ts INTEGER)")
    conn.executemany(
        "INSERT INTO item_availability VALUES (?, ?)",
        ((iid, int(ts)) for iid, ts in zip(av["item_id"], av["avail_ts"])),
    )
    conn.execute("CREATE TEMP TABLE avail_extra (item_id TEXT PRIMARY KEY)")
    conn.execute(
        "INSERT INTO avail_extra(item_id) "
        "SELECT a.item_id FROM temp.item_availability AS a "
        "JOIN main.items AS i ON i.item_id = a.item_id "
        "WHERE a.avail_ts >= 788918400000 "
        f"AND a.avail_ts <= {AS_OF} "
        "AND (i.first_seen_ts IS NULL OR i.first_seen_ts > "
        f"{AS_OF}) "
        "AND (i.first_seen_ts IS NULL OR a.avail_ts <= i.first_seen_ts)"
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM avail_extra").fetchone()[0]
    print(f"avail_extra={n}", flush=True)
    return n


def make_view(conn, with_avail: bool):
    conn.execute("PRAGMA query_only = OFF")
    conn.execute("DROP VIEW IF EXISTS temp.items")
    if with_avail:
        conn.execute(
            "CREATE TEMP VIEW items AS "
            "SELECT i.rowid AS rowid, i.* FROM main.items AS i "
            f"WHERE (i.first_seen_ts IS NOT NULL AND i.first_seen_ts <= {AS_OF}"
            " OR i.item_id IN (SELECT item_id FROM temp.avail_extra))"
        )
    else:
        conn.execute(
            "CREATE TEMP VIEW items AS "
            "SELECT rowid AS rowid, * FROM main.items "
            f"WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= {AS_OF}"
        )
    # temp item_categories over visible set (as policy does)
    conn.execute("DROP TABLE IF EXISTS temp.item_categories")
    conn.execute(
        "CREATE TEMP TABLE item_categories AS "
        "SELECT c.rowid AS rowid, c.item_id, c.category FROM main.item_categories AS c "
        "JOIN temp.items AS i ON i.item_id = c.item_id"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tc_item ON item_categories(item_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tc_cat ON item_categories(category)")
    conn.commit()
    conn.execute("PRAGMA query_only = ON")


def main():
    conn = sqlite3.connect(
        CORPUS.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False
    )
    t0 = time.perf_counter()
    build_avail_extra(conn)
    print(f"avail_extra build {time.perf_counter()-t0:.1f}s", flush=True)

    for label, with_avail in (("baseline", False), ("availability", True)):
        t1 = time.perf_counter()
        make_view(conn, with_avail)
        print(f"== {label} view+cats {time.perf_counter()-t1:.1f}s", flush=True)
        for qlabel, sql in QUERIES.items():
            t = time.perf_counter()
            try:
                rows = conn.execute(sql).fetchall()
                print(f"    {qlabel:14s} {time.perf_counter()-t:6.2f}s rows={len(rows)}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"    {qlabel:14s} {time.perf_counter()-t:6.2f}s ERR {exc}", flush=True)
    print(f"total {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
