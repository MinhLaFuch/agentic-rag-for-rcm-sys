"""Step 2c-1: build the restricted retrieval universe + replica SQLite.

Universe = probe items (510) + 196 eval targets + >=300k random catalog items
+ same-category neighbors of probe items (capped). Restricted recall is
INFLATED in absolute terms — valid only for relative arm comparison.

Outputs:
  investigations/vi_retrieval/universe_item_ids.txt
  investigations/vi_retrieval/universe_items.parquet  (doc_text etc.)
  investigations/vi_retrieval/restricted_corpus.sqlite (items+categories+fts replica)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
N_RANDOM = 300_000
MAX_NEIGHBORS = 150_000
SEED = 42

sys.path.insert(0, str(ROOT))
from package.corpus._sql import (  # noqa: E402
    CATEGORIES_INDEXES, CATEGORIES_TABLE_SCHEMA, FTS_POPULATE_SQL,
    FTS_TABLE_SCHEMA, ITEMS_INDEXES, ITEMS_TABLE_SCHEMA,
)
from package.embeddings.format_catalog_text import format_catalog_text  # noqa: E402


def main() -> None:
    probe = pd.read_parquet(OUT / "probe_items.parquet")
    eq11 = json.loads((ROOT / "investigations/eq11_target_predictability.json").read_text(encoding="utf-8"))
    targets = sorted({t["target"] for t in eq11["per_target"]})
    probe_ids = set(probe["item_id"])
    print(f"probe={len(probe_ids)} targets={len(targets)}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    # same-category neighbors of probe items
    ph = ",".join("?" * len(probe_ids))
    neigh_cats = [r[0] for r in conn.execute(
        f"SELECT DISTINCT category FROM item_categories WHERE item_id IN ({ph})", list(probe_ids))]
    print(f"probe categories: {len(neigh_cats)}", flush=True)
    ch = ",".join("?" * len(neigh_cats))
    neigh = pd.read_sql_query(
        f"SELECT DISTINCT item_id FROM item_categories WHERE category IN ({ch})", conn, params=neigh_cats)
    neigh_ids = set(neigh["item_id"]) - probe_ids - set(targets)
    print(f"same-category neighbor pool: {len(neigh_ids)}", flush=True)

    all_ids = pd.read_sql_query("SELECT item_id FROM items", conn)["item_id"]
    rng = np.random.default_rng(SEED)
    random_ids = set(rng.choice(all_ids.to_numpy(), size=N_RANDOM, replace=False).tolist())
    random_ids -= probe_ids | set(targets)

    # neighbors: uniform sample up to MAX_NEIGHBORS
    neigh_list = np.array(sorted(neigh_ids))
    if len(neigh_list) > MAX_NEIGHBORS:
        neigh_sel = set(rng.choice(neigh_list, size=MAX_NEIGHBORS, replace=False).tolist())
    else:
        neigh_sel = set(neigh_list.tolist())

    universe = sorted(probe_ids | set(targets) | random_ids | neigh_sel)
    print(f"universe: {len(universe)} "
          f"(probe {len(probe_ids)} + targets {len(targets)} + random {len(random_ids)} + neighbors {len(neigh_sel)})",
          flush=True)
    (OUT / "universe_item_ids.txt").write_text("\n".join(universe), encoding="utf-8")

    # fetch universe rows + categories
    rows = []
    for i in range(0, len(universe), 900):
        chunk = universe[i:i + 900]
        marks = ",".join("?" * len(chunk))
        rows.append(pd.read_sql_query(
            f"SELECT item_id, domain, original_item_id, first_seen_ts, title, store, price, "
            f"average_rating, rating_number, main_category FROM items WHERE item_id IN ({marks})",
            conn, params=chunk))
    uitems = pd.concat(rows, ignore_index=True)
    cats = []
    for i in range(0, len(universe), 900):
        chunk = universe[i:i + 900]
        marks = ",".join("?" * len(chunk))
        cats.append(pd.read_sql_query(
            f"SELECT item_id, category FROM item_categories WHERE item_id IN ({marks})",
            conn, params=chunk))
    ucats = pd.concat(cats, ignore_index=True)
    conn.close()

    cat_map = ucats.groupby("item_id")["category"].apply(list).to_dict()
    uitems["categories"] = [cat_map.get(i, []) for i in uitems["item_id"]]
    uitems["doc_text"] = [
        format_catalog_text(t, s, m, c)
        for t, s, m, c in zip(uitems["title"], uitems["store"], uitems["main_category"], uitems["categories"])
    ]
    uitems.to_parquet(OUT / "universe_items.parquet", index=False)

    # restricted sqlite replica (same schemas + populate SQL)
    db_path = OUT / "restricted_corpus.sqlite"
    if db_path.exists():
        db_path.unlink()
    rconn = sqlite3.connect(db_path)
    rconn.executescript(
        ITEMS_TABLE_SCHEMA + ";\n" + CATEGORIES_TABLE_SCHEMA + ";\n" + FTS_TABLE_SCHEMA + ";\n"
    )
    for idx in ITEMS_INDEXES + CATEGORIES_INDEXES:
        rconn.execute(idx)
    uitems_sql = uitems.drop(columns=["categories", "doc_text"])
    uitems_sql.to_sql("items", rconn, index=False, if_exists="replace")
    ucats.to_sql("item_categories", rconn, index=False, if_exists="replace")
    rconn.executescript(FTS_POPULATE_SQL)
    rconn.commit()
    n = rconn.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0]
    print(f"restricted sqlite: {n} fts rows -> {db_path}", flush=True)
    rconn.close()


if __name__ == "__main__":
    main()
