"""Q17 + Q20: split/leakage/segment audits on the fixed multi_domain bundle.

Read-only. Uses resource/splits/multi_domain/*.parquet (global user_idx/item_idx)
and evaluation_cohort.parquet (segment definitions).

Pairs are packed into uint64 keys: key = user_idx * 2**22 + item_idx
(item_idx < 2**22 = 4,194,304; user_idx < 2**25) so set ops stay in numpy.

Q17 checks:
  a) duplicate (user_idx,item_idx) pairs inside train.parquet
  b) timestamp sanity: max(train.ts) <= cutoff_1 < min(validation.ts) <= cutoff_2 < min(test.ts)
  c) (user,item) pairs appearing in BOTH train and validation/test
  d) eval cohort segments vs actual train history (train-only?)

Q20 checks:
  a) evaluation_cohort.history_size vs actual train-interaction count per user
  b) segment boundaries: cold=0, sparse<=4 (sparse_max_history=4), warm>4?
  c) per-domain timestamp ranges in validation/test (global vs per-domain cutoffs)

Outputs: investigations/q17_q20_splits.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SPLITS = Path("resource/splits/multi_domain")
OUT = Path(__file__).parent / "q17_q20_splits.json"
CUTOFF_1 = 1617737606134
CUTOFF_2 = 1651701127817
ITEM_BITS = 22  # item_idx < 4,194,304


def pair_keys(df: pd.DataFrame) -> np.ndarray:
    return (df["user_idx"].to_numpy(np.uint64) << ITEM_BITS) | df["item_idx"].to_numpy(np.uint64)


def uniq_keys(keys: np.ndarray) -> np.ndarray:
    return np.unique(keys)


def main() -> None:
    report: dict = {"cutoffs": {"cutoff_1": CUTOFF_1, "cutoff_2": CUTOFF_2}}

    cols = ["user_id", "user_idx", "item_idx", "timestamp", "domain"]
    train = pd.read_parquet(SPLITS / "train.parquet", columns=cols)
    val = pd.read_parquet(SPLITS / "validation.parquet", columns=cols)
    test = pd.read_parquet(SPLITS / "test.parquet", columns=cols)

    # ---- timestamp sanity ----
    report["timestamps"] = {
        "train": {"min": int(train.timestamp.min()), "max": int(train.timestamp.max()), "n": len(train)},
        "validation": {"min": int(val.timestamp.min()), "max": int(val.timestamp.max()), "n": len(val)},
        "test": {"min": int(test.timestamp.min()), "max": int(test.timestamp.max()), "n": len(test)},
        "train_le_cutoff1": bool((train.timestamp <= CUTOFF_1).all()),
        "train_gt_cutoff1_rows": int((train.timestamp > CUTOFF_1).sum()),
        "val_within_cutoffs": bool(((val.timestamp > CUTOFF_1) & (val.timestamp <= CUTOFF_2)).all()),
        "val_outside_rows": int(((val.timestamp <= CUTOFF_1) | (val.timestamp > CUTOFF_2)).sum()),
        "test_gt_cutoff2": bool((test.timestamp > CUTOFF_2).all()),
        "test_le_cutoff2_rows": int((test.timestamp <= CUTOFF_2).sum()),
    }

    # ---- duplicates in train ----
    tk = pair_keys(train)
    tu = uniq_keys(tk)
    report["train_dup_pairs"] = {
        "rows": int(len(train)), "unique_pairs": int(len(tu)),
        "dup_rows": int(len(train) - len(tu)),
    }
    # example duplicate pairs (up to 5)
    vc = pd.Series(tk).value_counts()
    dup_keys = vc[vc > 1].head(5)
    report["train_dup_examples"] = [
        {"user_idx": int(k >> ITEM_BITS), "item_idx": int(k & ((1 << ITEM_BITS) - 1)), "count": int(c)}
        for k, c in dup_keys.items()
    ]

    # ---- pair overlap train vs val/test ----
    vk = uniq_keys(pair_keys(val))
    xk = uniq_keys(pair_keys(test))
    inter_v = np.intersect1d(tu, vk, assume_unique=True)
    inter_t = np.intersect1d(tu, xk, assume_unique=True)
    report["pair_overlap"] = {
        "train_unique_pairs": int(len(tu)),
        "val_unique_pairs": int(len(vk)), "test_unique_pairs": int(len(xk)),
        "train_val_shared_pairs": int(len(inter_v)),
        "train_test_shared_pairs": int(len(inter_t)),
        "shared_examples_val": [
            {"user_idx": int(k >> ITEM_BITS), "item_idx": int(k & ((1 << ITEM_BITS) - 1))}
            for k in inter_v[:5]
        ],
    }
    del tk, tu, vk, xk, inter_v, inter_t, vc, dup_keys

    # ---- per-domain timestamp ranges ----
    report["per_domain_ts"] = {
        split: {d: {"min": int(g.timestamp.min()), "max": int(g.timestamp.max()), "n": len(g)}
                for d, g in df.groupby("domain")}
        for split, df in (("validation", val), ("test", test))
    }

    # ---- cohort segments vs train-only history ----
    cohort = pd.read_parquet(SPLITS / "evaluation_cohort.parquet")
    report["cohort"] = {
        "rows": len(cohort),
        "segments": cohort["segment"].value_counts().to_dict(),
        "eval_on": cohort["eval_on"].value_counts().to_dict(),
        "history_size_stats": {
            "min": int(cohort.history_size.min()), "max": int(cohort.history_size.max()),
            "p50": float(cohort.history_size.median()),
        },
    }
    sample_users = cohort["user_id"].drop_duplicates().sample(
        n=min(3000, cohort.user_id.nunique()), random_state=42)
    train_u = train[["user_id", "user_idx"]].drop_duplicates()
    uid2idx = dict(zip(train_u.user_id, train_u.user_idx))
    cohort_map = cohort.drop_duplicates("user_id").set_index("user_id")
    train_counts = train.groupby("user_idx").size()
    checks = []
    for uid in sample_users:
        uidx = uid2idx.get(uid)
        if uidx is None:
            continue
        actual = int(train_counts.get(uidx, 0))
        recorded = int(cohort_map.loc[uid, "history_size"])
        checks.append((uid, actual, recorded))
    if checks:
        arr = np.array([(a, r) for _, a, r in checks], dtype=np.int64)
        report["cohort_history_vs_train"] = {
            "n_checked": len(checks),
            "exact_match": int((arr[:, 0] == arr[:, 1]).sum()),
            "train_ge_recorded": int((arr[:, 0] >= arr[:, 1]).sum()),
            "recorded_gt_train": int((arr[:, 0] < arr[:, 1]).sum()),
            "mean_train": float(arr[:, 0].mean()), "mean_recorded": float(arr[:, 1].mean()),
            "examples": [{"user_id": u, "train_pairs": int(a), "cohort_history_size": int(r)}
                         for u, a, r in checks[:10]],
        }
    seg = cohort.drop_duplicates("user_id")
    report["segment_boundaries"] = {
        "cold_hist_max": int(seg.loc[seg.segment == "cold", "history_size"].max())
            if (seg.segment == "cold").any() else None,
        "sparse_hist_min": int(seg.loc[seg.segment == "sparse", "history_size"].min())
            if (seg.segment == "sparse").any() else None,
        "sparse_hist_max": int(seg.loc[seg.segment == "sparse", "history_size"].max())
            if (seg.segment == "sparse").any() else None,
        "warm_hist_min": int(seg.loc[seg.segment == "warm", "history_size"].min())
            if (seg.segment == "warm").any() else None,
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    slim = {k: v for k, v in report.items() if k != "per_domain_ts"}
    print(json.dumps(slim, ensure_ascii=False, indent=2, default=str)[:5000])
    print("per_domain_ts:", json.dumps(report["per_domain_ts"], indent=1)[:1500])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
