"""Q6 v4: scorer comparison across the two post-F2 filter_ab runs.

Pools feature parquets produced by q6_scorer_comparison_v3.py (one per run),
recomputes the HONEST learned scorer (features [pop, cf, cat_match] only —
retrieval-leg features are structurally zero for injected targets) with
5-fold CV by request_id across the pooled rows, then reports rescue@k per
run for every variant.

Usage:
  q6_scorer_comparison_v4.py <feat1.parquet> <inj1.json> <idx1> <label1> \
                            <feat2.parquet> <inj2.json> <idx2> <label2>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "q6_scorer_comparison_v4.json"


def rescue(df: pd.DataFrame, score_col: str, eligible: set[tuple[str, str]]) -> dict:
    df = df.copy()
    df["_order"] = np.arange(len(df))
    hits = {k: 0 for k in (1, 5, 10, 20, 50, 100)}
    ranks = []
    # rank of every candidate within its request; look up target positions
    rank_of = (df.sort_values([score_col, "_order"], ascending=[False, True])
               .groupby("request_id")["item_id"]
               .apply(lambda s: {iid: r for r, iid in enumerate(s, 1)}))
    for rid, t in eligible:
        rk = rank_of.get(rid, {}).get(t)
        if rk is not None:
            ranks.append(rk)
            for k in hits:
                hits[k] += rk <= k
    n = len(eligible)
    return {f"rescue@{k}": f"{hits[k]}/{n} = {hits[k]/n:.4f}" for k in hits} | {
        "median_rank": float(np.median(ranks)) if ranks else None}


def main() -> None:
    feat1, inj1, idx1, label1, feat2, inj2, idx2, label2 = sys.argv[1:9]
    runs = [(feat1, inj1, int(idx1), label1), (feat2, inj2, int(idx2), label2)]

    dfs = []
    elig_by_run = {}
    for feat, inj, idx, label in runs:
        d = pd.read_parquet(feat)
        d["run"] = label
        dfs.append(d)
        rep = json.loads(Path(inj).read_text(encoding="utf-8"))[idx]
        inj_by_req = {r["request_id"]: r for r in rep["per_request"]}
        # eligible = targets whose fate was 'ranked' in the real-scorer probe
        elig = set()
        for rid, ireq in inj_by_req.items():
            for t in (ireq.get("target_ranks") or {}):
                elig.add((rid, t))
        # condition on requests with real competition (>=1 non-target row)
        comp = {rid for rid, g in d.groupby("request_id") if (~g.is_target).any()}
        elig_by_run[label] = {(r, t) for r, t in elig if r in comp}
        print(f"{label}: rows={len(d)} eligible={len(elig_by_run[label])}", flush=True)

    df = pd.concat(dfs, ignore_index=True)

    # honest v5: [pop, cf, cat_match] only, 5-fold CV by request_id on the pool
    feat_cols = ["pop", "cf", "cat_match"]
    X = df[feat_cols].to_numpy(np.float64)
    y = df["is_target"].to_numpy(np.float64)
    uniq = np.array(sorted(set(df.request_id)))
    rng = np.random.default_rng(42)
    fold_map = {r: i % 5 for i, r in enumerate(rng.permutation(uniq))}
    folds = np.array([fold_map[r] for r in df.request_id])
    pred = np.zeros(len(df))
    for fold in range(5):
        tr = folds != fold
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Xs = (X - mu) / sd
        Xb = np.hstack([Xs, np.ones((len(Xs), 1))])
        w = np.zeros(X.shape[1] + 1)
        yt = y[tr]
        pw = (1 - yt).sum() / max(yt.sum(), 1)
        for _ in range(500):
            z = np.clip(Xb[tr] @ w, -30, 30)
            p = 1 / (1 + np.exp(-z))
            wt = np.where(yt > 0, pw, 1.0)
            grad = (Xb[tr].T @ ((p - yt) * wt)) / wt.sum() + 1e-3 * w
            w -= 0.5 * grad
        pred[~tr] = 1 / (1 + np.exp(-np.clip(Xb[~tr] @ w, -30, 30)))
    df["v5_honest"] = pred
    print("v5_honest trained on pooled rows", flush=True)

    variants = ["v1a", "v1b", "v2", "v3", "v4", "v5", "v5_honest"]
    out = {"conditioning": "requests with >=1 non-target retrieved candidate",
           "runs": {}}
    for label in elig_by_run:
        sub = df[df.run == label].copy()
        # NOTE: variant columns v1a..v4/v5 live in the per-run parquet;
        # v5_honest was trained on the pool (out-of-fold predictions).
        out["runs"][label] = {"n_eligible": len(elig_by_run[label]),
                              "variants": {}}
        for v in variants:
            if v not in sub.columns:
                continue
            out["runs"][label]["variants"][v] = rescue(sub, v, elig_by_run[label])
            print(label, v, out["runs"][label]["variants"][v]["rescue@10"], flush=True)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
