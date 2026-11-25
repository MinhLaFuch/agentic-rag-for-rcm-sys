"""Extract the 196 held-out targets of campaign_005/exp_5 + metadata + baseline request texts.

Outputs:
  targets.parquet      one row per (request_id, target item_idx): item_id, title, store,
                       main_category, categories, price, domain, rating_number, request kind/text
  target_item_ids.json sorted unique target item_id list (for query generation)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REQUESTS = (ROOT / "experiments/agent_eval/campaigns/campaign_005/"
            "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"


def main() -> None:
    item2id = {k: int(v) for k, v in json.loads(ITEM2ID.read_text()).items()}
    id2item = {v: k for k, v in item2id.items()}

    reqs = [json.loads(l) for l in REQUESTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for r in reqs:
        for idx in r.get("targets", []):
            rows.append({
                "request_id": r["request_id"], "kind": r["kind"], "segment": r["segment"],
                "request_text": r["text"], "item_idx": int(idx),
                "item_id": id2item.get(int(idx), ""),
            })
    df = pd.DataFrame(rows)
    print(f"target rows: {len(df)}  unique items: {df.item_id.nunique()}  "
          f"kinds: {df.kind.value_counts().to_dict()}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    meta = {}
    for iid in df["item_id"].unique():
        row = conn.execute(
            "SELECT item_id, domain, title, store, price, average_rating, rating_number, main_category "
            "FROM items WHERE item_id = ?", (iid,)).fetchone()
        if row is None:
            continue
        cats = [c for (c,) in conn.execute(
            "SELECT category FROM item_categories WHERE item_id = ? ORDER BY category", (iid,))]
        meta[iid] = {"domain": row[1], "title": row[2], "store": row[3], "price": row[4],
                     "avg_rating": row[5], "rating_number": row[6], "main_category": row[7],
                     "categories": cats}
    df = df.merge(pd.DataFrame.from_dict(meta, orient="index").rename_axis("item_id").reset_index(),
                  on="item_id", how="left")
    missing = df["title"].isna().sum()
    print(f"missing corpus metadata: {missing}", flush=True)

    df.to_parquet(OUT / "targets.parquet", index=False)
    (OUT / "target_item_ids.json").write_text(
        json.dumps(sorted(df["item_id"].dropna().unique().tolist())), encoding="utf-8")
    print(f"wrote {OUT/'targets.parquet'}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
