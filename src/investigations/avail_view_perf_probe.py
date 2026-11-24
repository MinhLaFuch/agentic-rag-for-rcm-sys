"""Time representative exclusion queries against the eval items view with and
without availability_dates, on the real corpus. Reproduces the availability
exp_2 timeout spike (32/40 exclusion requests hit the 5s SQL budget vs ~8 in
prompt_fix exp_2) to confirm the OR-visibility predicate is the cause.

Run: PYTHONPATH=. python investigations/avail_view_perf_probe.py
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
    "not_exists": (
        "SELECT i.item_id, i.domain, i.title, i.store, i.price, "
        "i.average_rating, i.rating_number, i.main_category FROM items AS i "
        "WHERE i.item_id <> 'Electronics::B09S3N6X3L' "
        "AND COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND NOT EXISTS (SELECT 1 FROM item_categories AS c "
        "WHERE c.item_id = i.item_id AND c.category = 'Power Strips') "
        "ORDER BY i.rating_number DESC, i.item_id LIMIT 100"
    ),
    "light_filter": (
        "SELECT i.item_id, i.title, i.price, i.average_rating, i.rating_number "
        "FROM items AS i WHERE COALESCE(i.main_category, '') <> 'Power Strips' "
        "AND i.item_id <> 'Electronics::B09S3N6X3L' "
        "ORDER BY i.rating_number DESC, i.item_id LIMIT 100"
    ),
    "point_lookup": (
        "SELECT i.item_id, i.title FROM items AS i "
        "WHERE i.item_id = 'Electronics::B09S3N6X3L'"
    ),
    "count": "SELECT COUNT(*) FROM items",
}


def time_query(conn, label, sql):
    t0 = time.perf_counter()
    try:
        rows = conn.execute(sql).fetchall()
        dt = time.perf_counter() - t0
        print(f"    {label:14s} {dt:6.2f}s  rows={len(rows)}", flush=True)
        return dt
    except Exception as exc:  # noqa: BLE001
        dt = time.perf_counter() - t0
        print(f"    {label:14s} {dt:6.2f}s  ERROR {exc}", flush=True)
        return dt


def reset_temp(conn):
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

    corpus = types.SimpleNamespace(_conn=mem, _evaluation_metadata_policy=None)

    import pandas as pd
    av = pd.read_parquet(AVAIL)
    avail = {iid: int(ts) for iid, ts in zip(av["item_id"], av["avail_ts"])}

    for label, availability in (("baseline", None), ("availability", avail)):
        reset_temp(mem)
        t1 = time.perf_counter()
        apply_metadata_policy(
            corpus, "historical_static_catalog",
            as_of_timestamp=AS_OF, availability=availability,
        )
        corpus._evaluation_metadata_policy = None  # allow re-apply
        setup = time.perf_counter() - t1
        print(f"== {label} (setup {setup:.1f}s)", flush=True)
        for qlabel, sql in QUERIES.items():
            time_query(mem, qlabel, sql)

    print(f"total {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
