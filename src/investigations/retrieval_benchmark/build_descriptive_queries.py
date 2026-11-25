"""Build descriptive_queries.jsonl — {item_idx, query} for the `descriptive` request kind.\n
Joins target_queries.jsonl (LLM VI descriptions per item_id) with targets.parquet
(item_id -> item_idx). build_requests resolves user/segment from item_idx via
target_by_user/seg_of, so only the mapping is needed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"


def main() -> None:
    item2id = {k: int(v) for k, v in json.loads(ITEM2ID.read_text()).items()}
    vi = {json.loads(l)["item_id"]: json.loads(l)["vi_query"]
          for l in (OUT / "target_queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    tgt = pd.read_parquet(OUT / "targets.parquet")[["item_id", "item_idx"]].drop_duplicates("item_id")

    rows = []
    for r in tgt.itertuples(index=False):
        q = vi.get(r.item_id)
        if not q:
            continue
        idx = item2id.get(r.item_id, r.item_idx)
        rows.append({"item_idx": int(idx), "query": q})
    # deterministic order
    rows.sort(key=lambda r: r["item_idx"])
    out = OUT / "descriptive_queries.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} queries -> {out}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
