"""Step 2a: stratified probe set — >=500 catalog items by domain x popularity decile.

Popularity = train-interaction count per item (causal, pre-validation).
Strata: 3 domains x 10 popularity deciles -> ~17 items/cell -> ~510 items.
Includes zero-interaction (long-tail) items on purpose: held-out targets are
mid/long-tail.

Outputs: investigations/vi_retrieval/probe_items.parquet
         (item_id, domain, title, store, main_category, categories, doc_text,
          popularity_count, popularity_decile)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
TRAIN = ROOT / "resource/splits/multi_domain/train.parquet"
N_PER_CELL = 17
SEED = 42

sys.path.insert(0, str(ROOT))
from package.embeddings.format_catalog_text import format_catalog_text  # noqa: E402


def main() -> None:
    print("loading corpus items ...", flush=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    items = pd.read_sql_query("SELECT item_id, domain, title, store, main_category FROM items", conn)
    cats = pd.read_sql_query("SELECT item_id, category FROM item_categories", conn)
    conn.close()
    cat_map = cats.groupby("item_id")["category"].apply(list).to_dict()
    print(f"items={len(items)} categorized={len(cat_map)}", flush=True)

    print("counting train interactions ...", flush=True)
    train = pd.read_parquet(TRAIN, columns=["parent_asin"])
    counts = train["parent_asin"].value_counts()
    items["popularity_count"] = items["item_id"].map(counts).fillna(0).astype(np.int64)
    del train

    # fixed count bands per domain (long-tail heavy, matches target population)
    BANDS = [(0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 20),
             (21, 50), (51, 100), (101, 500), (501, 10**12)]
    rng = np.random.default_rng(SEED)
    picks = []
    for domain, g in items.groupby("domain"):
        c = g["popularity_count"].to_numpy()
        dec = np.full(len(g), -1, dtype=int)
        for d, (lo, hi) in enumerate(BANDS):
            dec[(c >= lo) & (c <= hi)] = d
        g = g.assign(_dec=dec)
        for d in range(10):
            cell = g[g["_dec"] == d]
            if cell.empty:
                continue
            k = min(N_PER_CELL, len(cell))
            sel = cell.sample(n=k, random_state=int(rng.integers(0, 2**31)))
            picks.append(sel)
            print(f"  {domain} band {d} ({BANDS[d]}): pool={len(cell)} picked={k} "
                  f"count_range=({cell['popularity_count'].min()},{cell['popularity_count'].max()})", flush=True)
    probe = pd.concat(picks)
    probe["categories"] = [cat_map.get(i, []) for i in probe["item_id"]]
    probe["doc_text"] = [
        format_catalog_text(t, s, m, c)
        for t, s, m, c in zip(probe["title"], probe["store"], probe["main_category"], probe["categories"])
    ]
    probe = probe.drop(columns=["_dec"]).reset_index(drop=True)
    probe.to_parquet(OUT / "probe_items.parquet", index=False)
    print(f"\nprobe set: {len(probe)} items -> {OUT / 'probe_items.parquet'}", flush=True)
    print(probe.groupby("domain").size())


if __name__ == "__main__":
    main()
