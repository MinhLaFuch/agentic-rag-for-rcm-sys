"""Q6 fix-up: recompute rescue@10 with (a) proper conditioning and (b) honest v5.

Issues fixed vs q6_scorer_comparison.py:
  1. Conditioning: §6.7 reported rescue conditioned on requests with NON-EMPTY
     retrieval unions (real competition). v1a reproduced 46% on all 160 ranked
     targets; restrict to requests having >=1 non-target candidate.
  2. v5 leakage: leg_count/retr/rrf are structurally 0 for injected targets
     (they were never retrieved) -> the model learned "injected => target".
     Honest feature set = signals available regardless of provenance:
     [pop, cf, cat_match]. Rerun 5-fold CV by request.

Reads q6_scorer_comparison.features.parquet + ranktool_injection_exp5.json.
Output: investigations/q6_scorer_comparison_v2.json
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
FEAT = Path(__file__).parent / "q6_scorer_comparison.features.parquet"
INJ = ROOT / "investigations" / "ranktool_injection_exp5.json"
OUT = Path(__file__).parent / "q6_scorer_comparison_v2.json"


def rescue(df: pd.DataFrame, score_col: str, eligible: set[tuple[str, str]]) -> dict:
    df = df.copy()
    df["_order"] = np.arange(len(df))
    hits10 = hits20 = 0
    ranks = []
    for rid, sub in df.groupby("request_id"):
        order = sub.sort_values([score_col, "_order"], ascending=[False, True])
        rank_of = {iid: r for r, iid in enumerate(order.item_id, 1)}
        for t in [t for rr, t in eligible if rr == rid]:
            rk = rank_of.get(t)
            if rk is not None:
                ranks.append(rk)
                hits10 += rk <= 10
                hits20 += rk <= 20
    n = len(eligible)
    return {"rescue@10": f"{hits10}/{n} = {hits10/n:.4f}" if n else None,
            "rescue@20": f"{hits20}/{n} = {hits20/n:.4f}" if n else None,
            "median_rank": float(np.median(ranks)) if ranks else None}


def main() -> None:
    df = pd.read_parquet(FEAT)
    inj = json.loads(INJ.read_text(encoding="utf-8"))[0]
    inj_by_req = {r["request_id"]: r for r in inj["per_request"]}

    # requests with real competition = has >=1 non-target candidate row
    comp_reqs = {rid for rid, g in df.groupby("request_id") if (~g.is_target).any()}
    # eligible targets = 'ranked' fate in injection probe
    eligible_all = set()
    for rid, ireq in inj_by_req.items():
        for t, rk in (ireq.get("target_ranks") or {}).items():
            eligible_all.add((rid, t))
    eligible_comp = {(r, t) for r, t in eligible_all if r in comp_reqs}

    print(f"eligible_all={len(eligible_all)} eligible_with_competition={len(eligible_comp)}")

    # honest v5: [pop, cf, cat_match] only
    feat = ["pop", "cf", "cat_match"]
    X = df[feat].to_numpy(np.float64)
    y = df["is_target"].to_numpy(np.float64)
    req_ids = df["request_id"].to_numpy()
    uniq = np.array(sorted(set(req_ids)))
    rng = np.random.default_rng(42)
    fold_map = {r: i % 5 for i, r in enumerate(rng.permutation(uniq))}
    folds = np.array([fold_map[r] for r in req_ids])
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
    # also v5 with ALL features for reference (leaky, kept for comparison)
    df["v5_all"] = pd.read_parquet(FEAT)["v5"].to_numpy() if "v5" in df.columns else np.nan

    out = {"conditioning": "requests with >=1 non-target retrieved candidate",
           "n_eligible": len(eligible_comp),
           "variants": {}}
    for v in ["v1a", "v1b", "v2", "v3", "v4", "v5_honest"]:
        if v in df.columns:
            out["variants"][v] = rescue(df, v, eligible_comp)
        print(v, out["variants"].get(v), flush=True)

    # per-kind for v1a and v5_honest
    kind_of = {}
    for rid, ireq in inj_by_req.items():
        kind_of[rid] = ireq.get("kind")
    for v in ["v1a", "v5_honest"]:
        pk = defaultdict(lambda: [0, 0])
        df2 = df.copy(); df2["_o"] = np.arange(len(df2))
        for rid, sub in df2.groupby("request_id"):
            order = sub.sort_values([v, "_o"], ascending=[False, True])
            rank_of = {iid: r for r, iid in enumerate(order.item_id, 1)}
            for t in [t for rr, t in eligible_comp if rr == rid]:
                rk = rank_of.get(t)
                k = kind_of.get(rid, "?")
                pk[k][1] += 1
                pk[k][0] += (rk is not None and rk <= 10)
        out.setdefault("per_kind", {})[v] = {k: f"{a}/{b}" for k, (a, b) in pk.items()}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["variants"], indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
