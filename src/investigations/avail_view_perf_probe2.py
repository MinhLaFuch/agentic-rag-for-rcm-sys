"""Confirm availability-view perf regression on the real corpus, faithfully:
in-memory backup + apply_metadata_policy (both arms) + the SAME 5s progress-
handler budget the eval enforces. Reports per-query elapsed/timeout and the
query plan for the failing exclusion pattern.

Run: PYTHONPATH=. python investigations/avail_view_perf_probe2.py
"""
from __future__ import annotations

import sqlite3
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.corpus.apply_metadata_policy import apply_metadata_policy  # noqa: E402

CORPUS = Path("resource/corpus/multi_domain/corpus_multi_domain.sqlite")
AVAIL = Path("resource/corpus/multi_domain/item_availability.parquet")
AS_OF = 1617737606549
BUDGET_S = 5.0

QUERIES = {
    "count_items": "SELECT COUNT(*) FROM items",
    "light_filter": (
        "SELECT i.item_id, i.title, i.price, i.average_rating, i.rating_number "
        "FROM items AS i WHERE COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND i.item_id <> 'Electronics::B09S3N6X3L' "
        "ORDER BY i.rating_number DESC, i.item_id LIMIT 100"
    ),
    "cat_join": (
        "SELECT DISTINCT i.item_id FROM items AS i "
        "LEFT JOIN item_categories AS c ON c.item_id = i.item_id "
        "WHERE COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND (c.category IS NULL OR c.category <> 'Power Strips') "
        "LIMIT 100"
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


def timed(conn, sql, budget=BUDGET_S):
    deadline = time.monotonic() + budget
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    t0 = time.perf_counter()
    try:
        rows = conn.execute(sql).fetchall()
        return time.perf_counter() - t0, f"rows={len(rows)}"
    except sqlite3.Error as exc:
        return time.perf_counter() - t0, f"TIMEOUT/ERR {str(exc)[:80]}"
    finally:
        conn.set_progress_handler(None, 0)


def reset_temp(conn):
    conn.set_authorizer(None)  # policy-installed authorizer blocks PRAGMA query_only
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
    conn.execute("PRAGMA query_only = ON")


def main():
    t0 = time.perf_counter()
    file_conn = sqlite3.connect(CORPUS.resolve().as_uri() + "?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:", check_same_thread=False)
    file_conn.backup(mem)
    file_conn.close()
    mem.commit()
    print(f"backup {time.perf_counter()-t0:.1f}s", flush=True)

    import pandas as pd
    av = pd.read_parquet(AVAIL)
    avail = {iid: int(ts) for iid, ts in zip(av["item_id"], av["avail_ts"])}

    corpus = types.SimpleNamespace(_conn=mem, _evaluation_metadata_policy=None)
    for label, availability in (("availability", avail),):
        reset_temp(mem)
        t1 = time.perf_counter()
        apply_metadata_policy(
            corpus, "historical_static_catalog",
            as_of_timestamp=AS_OF, availability=availability,
        )
        corpus._evaluation_metadata_policy = None
        print(f"== {label} setup {time.perf_counter()-t1:.1f}s", flush=True)
        for qlabel, sql in QUERIES.items():
            dt, res = timed(mem, sql)
            print(f"    {qlabel:14s} {dt:6.2f}s  {res}", flush=True)
        if label == "availability":
            print("    -- plan for not_exists:", flush=True)
            for r in mem.execute("EXPLAIN QUERY PLAN " + QUERIES["not_exists"]):
                print("      ", r, flush=True)
    print(f"total {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
