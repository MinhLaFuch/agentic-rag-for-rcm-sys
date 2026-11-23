"""Q12: k-core K sweep {2,3,5,10} on train pairs + co-occurrence for fixed targets.

Replicates the streaming stage-3 fit-core filter EXACTLY in semantics:
iterative bipartite k-core on UNIQUE (user_idx,item_idx) train pairs until
convergence (k_core_filter / _streaming_temporal_stage3.py), min_user=min_item=K.
K=none = all unique train pairs (upper bound).

Per K reports:
  - surviving pair count, core users/items
  - attrition per domain (pairs before/after)
  - for the SAME fixed eval targets (campaign_005 exp_5 + union run_1 requests):
    in_core fraction, n_cooc>0 fraction, max cosine sim distribution
    (top-20-threshold comparison omitted except K=5 known =0; see note)

History = unique train items per user_idx (same content as scorer.user_items
for validation eval). Read-only. Output: investigations/q12_kcore_sweep.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPLITS = Path("resource/splits/multi_domain")
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"
RUNS = [
    ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1",
    ROOT / "experiments/agent_eval/union_ab/exp_1_union_prompt/run_1",
]
OUT = Path(__file__).parent / "q12_kcore_sweep.json"
KS = [2, 3, 5, 10]


def kcore_mask(u: np.ndarray, i: np.ndarray, k: int,
               n_users: int, n_items: int) -> np.ndarray:
    """Iterative bipartite k-core; returns boolean mask over pairs."""
    active = np.ones(len(u), dtype=bool)
    for _ in range(20):
        ua = u[active]; ia = i[active]
        ud = np.bincount(ua, minlength=n_users)
        idg = np.bincount(ia, minlength=n_items)
        keep = (ud >= k)[u] & (idg >= k)[i] & active
        if keep.sum() == active.sum():
            return keep
        active = keep
    raise RuntimeError("k-core did not converge in 20 iterations")


def main() -> None:
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    item_domain = {idx: nm.split("::", 1)[0] for idx, nm in id2item.items()}

    train = pd.read_parquet(SPLITS / "train.parquet", columns=["user_idx", "item_idx"])
    # unique pairs, same as stage-3 train_pairs
    key = train["user_idx"].to_numpy(np.int64) * (1 << 22) + train["item_idx"].to_numpy(np.int64)
    key = np.unique(key)
    u = (key >> 22).astype(np.int64)
    i = (key & ((1 << 22) - 1)).astype(np.int64)
    n_users = int(u.max()) + 1
    n_items = int(i.max()) + 1
    del train, key
    print(f"unique train pairs={len(u):,} users={n_users:,} items={n_items:,}", flush=True)

    # eval targets + history per user (unique train items)
    eval_pairs = []  # (run, request_id, kind, user_idx, target_idx)
    hist_map: dict[int, np.ndarray] = {}
    for run in RUNS:
        reqs = {r["request_id"]: r for r in
                (json.loads(l) for l in open(run / "requests.jsonl", encoding="utf-8"))}
        for r in reqs.values():
            uidx = r.get("user_idx")
            if uidx is None:
                continue
            for t in r.get("targets", []):
                if 0 <= t < n_items:
                    eval_pairs.append((str(run.name), r["request_id"], r.get("kind"), int(uidx), int(t)))
    # history = all train items per eval user
    need_users = sorted({p[3] for p in eval_pairs})
    tr = pd.read_parquet(SPLITS / "train.parquet", columns=["user_idx", "item_idx"])
    sub = tr[tr.user_idx.isin(need_users)]
    for uidx, grp in sub.groupby("user_idx"):
        hist_map[int(uidx)] = np.unique(grp.item_idx.to_numpy())
    del tr, sub
    print(f"eval targets={len(eval_pairs)} users_with_history={len(hist_map)}", flush=True)

    # item -> domain array for attrition
    i_dom = np.array([item_domain.get(x, "?") for x in range(n_items)])

    report = {"method": "iterative bipartite k-core on unique train pairs (min_user=min_item=K), "
                        "converged <=20 iters; cooc = exact cosine over filtered pairs; "
                        "history = unique train items per user; targets = exp_5+union requests",
              "n_unique_train_pairs": int(len(u)), "Ks": {}}

    for K in [None] + KS:
        if K is None:
            mask = np.ones(len(u), dtype=bool)
        else:
            mask = kcore_mask(u, i, K, n_users, n_items)
        uf, iff = u[mask], i[mask]
        core_users = np.unique(uf)
        core_items = np.unique(iff)
        # attrition per domain
        dom_before = Counter()
        dom_after = Counter()
        # domain of a pair = domain of its item (namespaced)
        pair_dom = i_dom[i]
        for d in np.unique(pair_dom):
            dom_before[str(d)] = int((pair_dom == d).sum())
        pair_dom_f = i_dom[iff]
        for d in np.unique(pair_dom_f):
            dom_after[str(d)] = int((pair_dom_f == d).sum())
        attrition = {d: {"before": int(dom_before.get(d, 0)),
                         "after": int(dom_after.get(d, 0)),
                         "kept_pct": round(100 * dom_after.get(d, 0) / max(1, dom_before.get(d, 0)), 2)}
                     for d in sorted(set(dom_before) | set(dom_after))}

        # co-occurrence for eval targets within this core
        A = sp.csr_matrix(
            (np.ones(len(uf), dtype=np.float32), (iff, uf)),
            shape=(n_items, n_users))
        A.sum_duplicates(); A.data[:] = 1.0
        norms = np.sqrt(np.asarray(A.getnnz(axis=1))).ravel().astype(np.float64)
        norms[norms == 0] = 1.0

        per_target = []
        for run_name, rid, kind, uidx, t in eval_pairs:
            hist = hist_map.get(uidx)
            rec = {"request_id": rid, "kind": kind, "user_idx": uidx, "target": t}
            if A.indptr[t + 1] - A.indptr[t] == 0 or hist is None or len(hist) == 0:
                rec.update(in_core=False, n_cooc=0, max_sim=0.0)
                per_target.append(rec); continue
            rec["in_core"] = True
            v = A.getrow(t)
            hv = A[hist]
            co = (hv @ v.T).toarray().ravel()
            nz = co > 0
            rec["n_cooc"] = int(nz.sum())
            if nz.any():
                hnorms = norms[hist[nz]]
                sim = co[nz] / (hnorms * norms[t])
                rec["max_sim"] = float(sim.max())
            else:
                rec["max_sim"] = 0.0
            per_target.append(rec)

        n = len(per_target)
        in_core = [r for r in per_target if r["in_core"]]
        with_cooc = [r for r in in_core if r["n_cooc"] > 0]
        sims = np.array([r["max_sim"] for r in in_core])
        key = "none" if K is None else str(K)
        report["Ks"][key] = {
            "surviving_pairs": int(len(uf)),
            "core_users": int(len(core_users)), "core_items": int(len(core_items)),
            "attrition_by_domain": attrition,
            "targets": {
                "n": n, "in_core": len(in_core),
                "in_core_frac": round(len(in_core) / n, 4) if n else None,
                "with_cooc": len(with_cooc),
                "with_cooc_frac_of_core": round(len(with_cooc) / len(in_core), 4) if in_core else None,
                "max_sim_median": float(np.median(sims)) if sims.size else None,
                "max_sim_p90": float(np.percentile(sims, 90)) if sims.size else None,
                "max_sim_max": float(sims.max()) if sims.size else None,
                "frac_max_sim_gt_0": round(float((sims > 0).mean()), 4) if sims.size else None,
            },
            "note": "top-20 threshold comparison not recomputed per K; K=5 baseline entered_k20=0 (probe §6.8)",
        }
        print(f"K={key}: pairs={len(uf):,} core_items={len(core_items):,} "
              f"in_core={len(in_core)}/{n} cooc={len(with_cooc)}", flush=True)
        del A, uf, iff, mask

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
