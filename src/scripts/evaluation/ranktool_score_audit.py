"""Audit RankTool candidate scoring on recorded trajectories.

For every ok RankTool step in a run's trajectories.jsonl, re-scores the recorded
`candidate_item_ids` with the SAME scorer the eval used (Baseline or Hybrid per
configs/agent/scoring.yaml, ItemKNN train_core model, full pre-target popularity)
and reports:

  - cf_zero_frac:   candidates whose collaborative term is exactly 0
                    (non-core items / no neighbor overlap -> pure popularity tiebreak)
  - score stats:    min/median/max of the final score, and of the CF term alone
  - top1_cf_zero:   fraction of RankTool calls whose rank-1 item has cf == 0
                    (i.e., the recommendation was decided by popularity/tiebreak,
                    not by any personalized signal)

Usage (from src/):
    python scripts/evaluation/ranktool_score_audit.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from package.config import get_data_paths, load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.config import select_fit_target
from package.tools import BaselineScorer, HybridScorer


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def build_scorer(eval_on: str = "validation"):
    """Rebuild the exact scorer run_agent_eval used (mode from configs/agent/scoring.yaml)."""
    data_paths = resolve_bundle_paths()
    baselines = load_config("eval/baselines")["baselines"]
    scoring = load_config("agent/scoring")["scoring"]
    knn_k = int(baselines["item_knn"]["k"])

    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, _ = select_fit_target(train, val, test, eval_on)
    user2id, item2id = load_mappings(data_paths.mapped_dir)

    core_knn = build_core_model(data_paths, eval_on, knn_k, fit_df, user2id, item2id)
    if core_knn is None:
        raise RuntimeError("build_core_model returned None (legacy tag?)")
    print(f"  ItemKNN core model: status={core_knn._evaluation_artifact_status}", flush=True)

    mode = scoring["mode"]
    weight = float(scoring.get("hybrid_popularity_weight", 4.0))
    scorer = HybridScorer(core_knn, weight) if mode == "hybrid" else BaselineScorer(core_knn)
    return scorer, user2id, item2id, mode


def audit_run(run_dir: Path, scorer, user2id, item2id) -> dict:
    traj_path = run_dir / "trajectories.jsonl"
    if not traj_path.exists():
        # campaign metric-fixes runs may use a custom trajectory_file name
        cands = list(run_dir.glob("*trajectories.jsonl"))
        if not cands:
            return {"run": str(run_dir), "error": "no trajectories file"}
        traj_path = cands[0]

    stats = Counter()
    score_samples = []
    cf_samples = []
    per_kind = {}

    for row in _load_jsonl(traj_path):
        kind = row.get("kind") or row.get("request", {}).get("kind") or "?"
        pk = per_kind.setdefault(kind, Counter())
        user_id = None
        # user_id lives in RankTool args (resolved); grab from requests if absent
        for step in row.get("steps", []):
            if step.get("tool") != "RankTool" or not step.get("ok"):
                continue
            data = step.get("data") or {}
            cids = data.get("candidate_item_ids") or []
            ranked = data.get("ranked") or []
            args = step.get("args") or {}
            uid = args.get("user_id") or user_id
            if not uid:
                stats["ranktool_no_user_id"] += 1
                continue
            user_idx = user2id.get(uid, -1)
            idxs = np.array([item2id[i] for i in cids if i in item2id], dtype=np.int64)
            if idxs.size == 0:
                stats["ranktool_no_mapped_candidates"] += 1
                continue

            scores = np.asarray(scorer.score(user_idx, idxs), dtype=np.float64)

            # CF term alone: recompute the personalized component the scorer added
            cf = np.zeros(idxs.shape, dtype=np.float64)
            if scorer.similarity is not None and scorer.is_known_user(user_idx):
                cf_row = (scorer.user_items.getrow(user_idx) @ scorer.similarity).tocsr()
                cf = cf_row[:, idxs].toarray().ravel().astype(np.float64)

            n = idxs.size
            stats["ranktool_steps"] += 1
            stats["candidates"] += n
            stats["cf_zero"] += int((cf == 0).sum())
            stats["cf_nonzero"] += int((cf > 0).sum())
            pk["candidates"] += n
            pk["cf_zero"] += int((cf == 0).sum())

            score_samples.extend(scores.tolist())
            cf_samples.extend(cf.tolist())

            # rank-1 item: cf value of the top-ranked candidate (mapped candidates only)
            if ranked:
                top_id = ranked[0].get("item_id")
                # cf[] aligns with idxs[] = mapped candidates in cids order
                mapped_ids = [cid for cid in cids if cid in item2id]
                cf_by_id = {cid: float(cf[j]) for j, cid in enumerate(mapped_ids)}
                if top_id in cf_by_id:
                    if cf_by_id[top_id] == 0:
                        stats["top1_cf_zero"] += 1
                        pk["top1_cf_zero"] += 1
                    else:
                        stats["top1_cf_nonzero"] += 1
                        pk["top1_cf_nonzero"] += 1
                else:
                    stats["top1_unmapped_or_absent"] += 1
            else:
                stats["ranktool_empty_ranked"] += 1

    def dist(vals):
        if not vals:
            return None
        a = np.asarray(vals)
        return {
            "n": int(a.size),
            "zero_frac": float((a == 0).mean()),
            "min": float(a.min()), "p50": float(np.median(a)),
            "p90": float(np.percentile(a, 90)), "max": float(a.max()),
        }

    out = {
        "run": str(run_dir),
        "trajectory_file": traj_path.name,
        "scorer_mode": getattr(scorer, "name", type(scorer).__name__),
        "stats": dict(stats),
        "score_dist": dist(score_samples),
        "cf_term_dist": dist(cf_samples),
        "cf_zero_frac": (stats["cf_zero"] / stats["candidates"]) if stats["candidates"] else None,
        "top1_cf_zero_frac": (stats["top1_cf_zero"] / (stats["top1_cf_zero"] + stats["top1_cf_nonzero"]))
            if (stats["top1_cf_zero"] + stats["top1_cf_nonzero"]) else None,
        "per_kind": {k: dict(v) for k, v in per_kind.items()},
    }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    scorer, user2id, item2id, mode = build_scorer(args.eval_on)
    print(f"  scorer mode={mode} name={scorer.name}", flush=True)

    reports = []
    for run_dir in args.run_dirs:
        print(f"== {run_dir}", flush=True)
        rep = audit_run(run_dir, scorer, user2id, item2id)
        reports.append(rep)
        if "error" in rep:
            print(f"   ERROR: {rep['error']}", flush=True)
            continue
        s = rep["stats"]
        print(f"   ranktool_steps={s.get('ranktool_steps',0)} candidates={s.get('candidates',0)} "
              f"cf_zero_frac={rep['cf_zero_frac']}", flush=True)
        print(f"   top1_cf_zero_frac={rep['top1_cf_zero_frac']} score_dist={rep['score_dist']}", flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
