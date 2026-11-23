"""ItemKNN structural probe: could ANY kNN variant surface the held-out targets?

ItemKNN similarity = binary cosine over train_core users, top-k=20 neighbours
kept per item (baseline_item_knn_recommender.py). cf_topn_recall already showed
0/163 targets get nonzero CF — i.e. no target sits in any history item's stored
top-20. This probe answers the deeper question:

  For each (request user, held-out target) pair, compute the EXACT cosine
  sim(h, t) = |U_h ∩ U_t| / sqrt(|U_h|·|U_t|) over train_core for every history
  item h, and compare against h's stored top-20 similarity threshold.

Outputs per target:
  - n_cooc:        # history items sharing >=1 train_core user with the target
  - max_ratio:     max over h of sim(h,t) / top20_threshold(h)
                   (>1.0 would mean the target SHOULD have been in h's top-20 —
                   a sanity check against the cf=0 finding; <<1 means even a
                   much larger k is needed)
  - entered_k20:   # of h where sim(h,t) exceeds h's top-20 threshold

If max_ratio is tiny for almost all targets, ItemKNN is structurally hopeless
for this eval regardless of k or train size — the co-occurrence signal itself
is absent, not just truncated.

Usage (from src/):
    python scripts/evaluation/itemknn_cooccurrence_probe.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.evaluation.recommender.analysis.core_inputs import core_inputs
from ranktool_score_audit import build_scorer, _load_jsonl


def build_item_user_matrix(paths) -> tuple[sparse.csr_matrix, np.ndarray, dict, dict, np.ndarray]:
    """A[core_item, core_user] = 1 for each train_core pair; returns (A, item_norms, users, items, core_to_global)."""
    users, items = __import__("package.data.mapping", fromlist=["load_mappings"]).load_mappings(
        paths.mapped_dir / "fit_core")
    pairs = pd.read_parquet(paths.splits_dir / "train_core.parquet",
                            columns=["user_idx", "item_idx"])
    n_items, n_users = len(items), len(users)
    A = sparse.csr_matrix(
        (np.ones(len(pairs), dtype=np.float32),
         (pairs["item_idx"].to_numpy(), pairs["user_idx"].to_numpy())),
        shape=(n_items, n_users))
    A.sum_duplicates()
    A.data[:] = 1.0  # binarize: cosine uses presence, not counts
    norms = np.sqrt(A.getnnz(axis=1)).astype(np.float64)
    norms[norms == 0] = 1.0
    # core item idx -> global item2id idx
    global_item2id = json.loads((paths.mapped_dir / "item2id.json").read_text(encoding="utf-8"))
    core_to_global = np.empty(n_items, dtype=np.int64)
    for key, cidx in items.items():
        core_to_global[cidx] = global_item2id[key]
    return A, norms, users, items, core_to_global


def row_min_thresholds(similarity: sparse.csr_matrix) -> np.ndarray:
    """Per-row minimum stored similarity = the top-k cutoff value (inf if row empty)."""
    indptr, data = similarity.indptr, similarity.data
    out = np.full(similarity.shape[0], np.inf, dtype=np.float64)
    nnz = np.diff(indptr)
    rows = np.nonzero(nnz)[0]
    # vectorized min per nonempty row via reduceat on sorted data
    starts = indptr[:-1][nnz > 0]
    mins = np.minimum.reduceat(data, starts)
    out[rows] = mins
    return out


def probe_run(run_dir: Path, scorer, user2id, item2id, A, item_norms,
              core_to_global, thresh_global) -> dict:
    requests = {r["request_id"]: r for r in _load_jsonl(run_dir / "requests.jsonl")}
    traj_path = run_dir / "trajectories.jsonl"
    if not traj_path.exists():
        cands = list(run_dir.glob("*trajectories.jsonl"))
        if not cands:
            return {"run": str(run_dir), "error": "no trajectories file"}
        traj_path = cands[0]

    # global item idx -> core item idx (-1 if not in fit core)
    n_global = len(item2id)
    global_to_core = np.full(n_global, -1, dtype=np.int64)
    global_to_core[core_to_global] = np.arange(len(core_to_global))

    per_target = []
    for row in _load_jsonl(traj_path):
        req = requests.get(row.get("request_id"))
        if req is None:
            continue
        user_idx = req.get("user_idx")
        if user_idx is None:
            continue
        # history = scorer.user_items row (all pre-target interactions, global space)
        hist_global = scorer.user_items.getrow(user_idx).indices
        hist_core = global_to_core[hist_global]
        hist_core = hist_core[hist_core >= 0]
        if hist_core.size == 0:
            continue
        hist_global_core = core_to_global[hist_core]  # back to global for thresholds
        thr = thresh_global[hist_global_core]
        hist_norms = item_norms[hist_core]

        for t_global in req.get("targets", []):
            t_core = global_to_core[t_global] if 0 <= t_global < n_global else -1
            rec = {"request_id": row.get("request_id"), "kind": req.get("kind"),
                   "target_global": int(t_global), "in_core": bool(t_core >= 0)}
            if t_core < 0:
                rec.update(n_cooc=0, max_ratio=0.0, max_sim=0.0, entered_k20=0,
                           best_hist_global=None)
                per_target.append(rec)
                continue

            v = A.getrow(t_core)  # users who touched target in train_core
            if v.nnz == 0:
                rec.update(n_cooc=0, max_ratio=0.0, max_sim=0.0, entered_k20=0,
                           best_hist_global=None)
                per_target.append(rec)
                continue

            co = (A[hist_core] @ v.T).toarray().ravel()  # |U_h ∩ U_t| per history item
            nz = co > 0
            rec["n_cooc"] = int(nz.sum())
            if not nz.any():
                rec.update(max_ratio=0.0, max_sim=0.0, entered_k20=0,
                           best_hist_global=None)
                per_target.append(rec)
                continue

            t_norm = item_norms[t_core]
            sim = co[nz] / (hist_norms[nz] * t_norm)
            thr_nz = thr[nz]
            valid = np.isfinite(thr_nz) & (thr_nz > 0)
            ratio = np.where(valid, sim / np.where(valid, thr_nz, 1.0), 0.0)
            best = int(np.argmax(ratio))
            rec.update(
                max_ratio=float(ratio[best]),
                max_sim=float(sim[best]),
                cooc_at_best=int(co[nz][best]),
                entered_k20=int((sim > thr_nz).sum()),
                best_hist_global=int(hist_global_core[nz][best]),
            )
            per_target.append(rec)

    n = len(per_target)
    in_core = [r for r in per_target if r["in_core"]]
    with_cooc = [r for r in in_core if r["n_cooc"] > 0]
    ratios = np.array([r["max_ratio"] for r in in_core])
    sims = np.array([r["max_sim"] for r in in_core])

    def q(a, p):
        return float(np.percentile(a, p)) if a.size else None

    return {
        "run": str(run_dir),
        "n_targets": n,
        "n_in_core": len(in_core),
        "n_with_cooc": len(with_cooc),
        "frac_in_core": len(in_core) / n if n else None,
        "frac_with_cooc_of_core": len(with_cooc) / len(in_core) if in_core else None,
        "frac_with_cooc_of_all": len(with_cooc) / n if n else None,
        "entered_k20_total": int(sum(r["entered_k20"] for r in per_target)),
        "max_ratio": {
            "median": float(np.median(ratios)) if ratios.size else None,
            "p90": q(ratios, 90), "p99": q(ratios, 99), "max": float(ratios.max()) if ratios.size else None,
            "frac_gt_1": float((ratios > 1).mean()) if ratios.size else None,
            "frac_gt_0_5": float((ratios > 0.5).mean()) if ratios.size else None,
            "frac_gt_0_1": float((ratios > 0.1).mean()) if ratios.size else None,
        },
        "max_sim": {
            "median": float(np.median(sims)) if sims.size else None,
            "p90": q(sims, 90), "max": float(sims.max()) if sims.size else None,
        },
        "per_target": per_target,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    scorer, user2id, item2id, mode = build_scorer(args.eval_on)
    print(f"  scorer mode={mode}", flush=True)

    paths = resolve_bundle_paths()
    print("  building item-user matrix from train_core...", flush=True)
    A, item_norms, users, items, core_to_global = build_item_user_matrix(paths)
    print(f"  A: {A.shape} nnz={A.nnz}; core items={len(items)}", flush=True)

    thresh_global = row_min_thresholds(scorer.similarity)
    print("  top-20 thresholds computed", flush=True)

    reports = []
    for run_dir in args.run_dirs:
        print(f"== {run_dir}", flush=True)
        rep = probe_run(run_dir, scorer, user2id, item2id, A, item_norms,
                        core_to_global, thresh_global)
        reports.append(rep)
        if "error" in rep:
            print(f"   ERROR: {rep['error']}", flush=True)
            continue
        print(f"   targets={rep['n_targets']} in_core={rep['n_in_core']} "
              f"with_cooc={rep['n_with_cooc']} entered_k20={rep['entered_k20_total']}", flush=True)
        print(f"   max_ratio={rep['max_ratio']}", flush=True)
        print(f"   max_sim={rep['max_sim']}", flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
