"""Q13 recheck part 2: decompose the ~18% hidden targets — proxy error vs true
cold-start — instead of reporting one number.

For each of the 196 campaign_005 exp_5 targets:
  - target timestamp = validation row (user_idx,item_idx) timestamp
  - first_seen_ts from corpus items table
  - hidden under eval as_of=1617737606549  (first_seen NULL or > as_of)

Decomposition:
  a) months between cutoff_1 (1617737606134) and target timestamp, bucketed;
     hidden-rate per bucket.
  b) among hidden: share whose first_seen is within 30/90 days AFTER cutoff_1
     (item likely existed pre-cutoff, just first reviewed later -> proxy error)
     vs first_seen far after cutoff / after target ts (true late launch).
  c) hidden where first_seen == target timestamp (item's FIRST-EVER interaction
     is the held-out target -> invisible even under per-target rewind).

Output: investigations/q13c_hidden_decomp.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQS = Path("experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
SPLITS = Path("resource/splits/multi_domain")
ITEM2ID = Path("resource/mapped/multi_domain/item2id.json")
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
AS_OF = 1617737606549
CUTOFF_1 = 1617737606134
OUT = Path(__file__).parent / "q13c_hidden_decomp.json"

MONTH = 30.44 * 86400000.0
DAY = 86400000.0


def main() -> None:
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    requests = [json.loads(l) for l in open(REQS, encoding="utf-8")]
    pairs = sorted({(r["user_idx"], t) for r in requests for t in r.get("targets", [])})
    print(f"target pairs: {len(pairs)}", flush=True)

    val = pd.read_parquet(SPLITS / "validation.parquet",
                          columns=["user_idx", "item_idx", "timestamp"])
    key = val.groupby(["user_idx", "item_idx"])["timestamp"].min()
    rows = []
    missing = 0
    for u, i in pairs:
        try:
            ts = int(key.loc[(u, i)])
        except KeyError:
            missing += 1
            continue
        rows.append((u, i, ts))
    tdf = pd.DataFrame(rows, columns=["user_idx", "item_idx", "target_ts"])
    print(f"matched {len(tdf)}, missing {missing}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    fs = pd.DataFrame(conn.execute(
        "SELECT item_id, domain, first_seen_ts FROM items").fetchall(),
        columns=["item_id", "domain", "first_seen_ts"])
    fs_map = fs.set_index("item_id")
    tdf["item_id"] = tdf["item_idx"].map(lambda i: id2item.get(i))
    tdf = tdf[tdf.item_id.notna()]
    tdf["domain"] = tdf.item_id.map(fs_map["domain"])
    tdf["first_seen_ts"] = tdf.item_id.map(fs_map["first_seen_ts"])
    tdf["hidden"] = tdf.first_seen_ts.isna() | (tdf.first_seen_ts > AS_OF)
    tdf["months_after_c1"] = (tdf.target_ts - CUTOFF_1) / MONTH
    tdf["days_fs_minus_c1"] = (tdf.first_seen_ts - CUTOFF_1) / DAY

    report = {"method": "targets = requests.jsonl targets joined to validation "
              "timestamps; hidden = first_seen NULL or > as_of=1617737606549; "
              "months bucket = (target_ts - cutoff_1)/30.44d",
              "n_target_pairs": int(len(pairs)), "n_matched": int(len(tdf)),
              "n_missing_val_row": int(missing),
              "n_unique_items": int(tdf.item_id.nunique())}

    # (a) hidden-rate by months-between-cutoff-and-target
    bins = [-np.inf, 1, 3, 6, 12, np.inf]
    labels = ["<1mo", "1-3mo", "3-6mo", "6-12mo", ">12mo"]
    tdf["bucket"] = pd.cut(tdf.months_after_c1, bins=bins, labels=labels)
    by_bucket = {}
    for b, g in tdf.groupby("bucket", observed=True):
        by_bucket[str(b)] = {"n": int(len(g)),
                             "hidden": int(g.hidden.sum()),
                             "hidden_pct": round(100 * g.hidden.mean(), 2)}
    report["hidden_rate_by_months_cutoff_to_target"] = by_bucket

    # (b) decompose hidden
    hid = tdf[tdf.hidden].copy()
    fs_gap = hid.days_fs_minus_c1  # first_seen - cutoff_1, in days
    report["hidden_decomposition"] = {
        "n_hidden": int(len(hid)),
        "pct_of_targets": round(100 * len(hid) / len(tdf), 2),
        "first_seen_null": int(hid.first_seen_ts.isna().sum()),
        "first_seen_within_30d_after_c1": int((fs_gap <= 30).sum()),
        "first_seen_within_90d_after_c1": int((fs_gap <= 90).sum()),
        "first_seen_>90d_after_c1": int((fs_gap > 90).sum()),
        "first_seen_before_or_at_c1_but_still_hidden": int(
            ((hid.first_seen_ts.notna()) & (hid.first_seen_ts <= CUTOFF_1)).sum()),
        "first_seen_equals_target_ts": int((hid.first_seen_ts == hid.target_ts).sum()),
        "first_seen_after_target_ts": int((hid.first_seen_ts > hid.target_ts).sum()),
        "by_domain": hid.groupby("domain").size().to_dict(),
        "examples": [{"item_id": r.item_id, "domain": r.domain,
                      "target_ts": int(r.target_ts),
                      "first_seen_ts": None if pd.isna(r.first_seen_ts) else int(r.first_seen_ts),
                      "fs_minus_c1_days": None if pd.isna(r.first_seen_ts) else round(float(r.days_fs_minus_c1), 1)}
                     for r in hid.head(8).itertuples()],
    }
    # visible targets' fs proximity for contrast
    vis = tdf[~tdf.hidden]
    report["visible_first_seen_proximity"] = {
        "n": int(len(vis)),
        "pct_first_seen_within_30d_before_c1": round(
            100 * ((CUTOFF_1 - vis.first_seen_ts) / DAY <= 30).mean(), 2),
    }
    tdf.drop(columns=["bucket"]).to_parquet(
        Path(__file__).parent / "q13c_targets.parquet", index=False)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print("wrote", OUT, flush=True)
    print(json.dumps(report["hidden_decomposition"], indent=1, default=str)[:2000])


if __name__ == "__main__":
    main()
