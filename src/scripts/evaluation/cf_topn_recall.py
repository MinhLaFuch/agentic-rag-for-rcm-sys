"""Measure recall of a hypothetical user-level CF top-N candidate source.

For every target in a run's scored.jsonl, compute the user's full CF score vector
(user_items[user] @ similarity, same math as BaselineScorer) over ALL core items,
then report at which rank each target would appear — i.e., the recall ceiling of
"top-N items for this user by CF" (Direction A item 4a), which no current tool
exposes (SimilarTool only unions seed-neighbor rows).

Also reports the same for non-core targets (expected: unreachable, cf == 0).

Usage (from src/):
    python scripts/evaluation/cf_topn_recall.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from package.config import load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.config import select_fit_target

KS = (10, 20, 50, 100, 500)


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def build_model():
    data_paths = resolve_bundle_paths()
    baselines = load_config("eval/baselines")["baselines"]
    knn_k = int(baselines["item_knn"]["k"])
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, _ = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    model = build_core_model(data_paths, "validation", knn_k, fit_df, user2id, item2id)
    return model, user2id, item2id


def cf_scores_for_user(model, user_idx: int):
    """Return (indices, scores) of nonzero CF scores for the user, sorted desc,
    with the user's seen items removed (mirrors RankTool exclude_seen)."""
    if user_idx is None or user_idx < 0 or user_idx >= model.user_items.shape[0]:
        return None
    row = model.user_items.getrow(user_idx)
    if row.nnz == 0 or getattr(model, "similarity", None) is None:
        return None
    seen = set(row.indices.tolist())
    cf = (row @ model.similarity).tocsr()
    cf.sum_duplicates()
    cf.eliminate_zeros()
    if cf.nnz == 0:
        return None
    keep = np.array([i not in seen for i in cf.indices], dtype=bool)
    indices, data = cf.indices[keep], cf.data[keep]
    if indices.size == 0:
        return None
    order = np.argsort(-data, kind="stable")
    return indices[order], data[order]


def report_run(run_dir: Path, model, user2id, item2id) -> dict:
    requests = {}
    req_path = run_dir / "requests.jsonl"
    for r in _load_jsonl(req_path):
        requests[r["request_id"]] = r

    # group targets by user to reuse the cf vector
    # target entries: scored.jsonl target_stage_detail keys are item idx (global)
    user_targets = defaultdict(list)   # user_idx -> [(target_idx, best_stage, kind)]
    n_targets = 0
    for row in _load_jsonl(run_dir / "scored.jsonl"):
        req = requests.get(row.get("request_id"), {})
        uidx = req.get("user_idx")
        if uidx is None:
            uid = req.get("user_id")
            uidx = user2id.get(uid, -1) if uid else -1
        kind = req.get("kind", "?")
        for t_str, info in (row.get("target_stage_detail") or {}).items():
            bs = info.get("best_stage")
            if not bs:
                continue
            try:
                tidx = int(t_str)
            except ValueError:
                continue
            user_targets[uidx].append((tidx, bs, kind))
            n_targets += 1

    rank_records = []  # (best_stage, kind, target_idx, cf_rank or None, cf_score)
    for uidx, targets in user_targets.items():
        cf = cf_scores_for_user(model, uidx)
        if cf is None:
            for tidx, bs, kind in targets:
                rank_records.append((bs, kind, tidx, None, 0.0))
            continue
        indices, scores = cf
        pos = {int(i): r + 1 for r, i in enumerate(indices)}  # 1-based rank among nonzero cf items
        score_of = {int(i): float(s) for i, s in zip(indices, scores)}
        for tidx, bs, kind in targets:
            rank_records.append((bs, kind, tidx, pos.get(tidx), score_of.get(tidx, 0.0)))

    # recall@k per best_stage bucket
    def recall_at(records, k):
        hit = sum(1 for r in records if r[3] is not None and r[3] <= k)
        return hit, len(records)

    out = {"run": str(run_dir), "n_targets": n_targets, "by_stage": {}, "by_kind": {}}
    stages = sorted({r[0] for r in rank_records})
    for st in stages:
        recs = [r for r in rank_records if r[0] == st]
        entry = {}
        for k in KS:
            hit, tot = recall_at(recs, k)
            entry[f"recall@{k}"] = round(hit / tot, 4) if tot else None
        ranks = [r[3] for r in recs if r[3] is not None]
        entry["n_with_cf_signal"] = len(ranks)
        entry["n_total"] = len(recs)
        entry["median_rank"] = float(np.median(ranks)) if ranks else None
        out["by_stage"][st] = entry

    kinds = sorted({r[1] for r in rank_records})
    for kd in kinds:
        recs = [r for r in rank_records if r[1] == kd]
        out["by_kind"][kd] = {f"recall@{k}": (lambda h, t: round(h / t, 4) if t else None)(
            *recall_at(recs, k)) for k in KS}
        out["by_kind"][kd]["n"] = len(recs)

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    model, user2id, item2id = build_model()
    print(f"model: num_items={model.num_items} users={model.user_items.shape[0]} "
          f"sim_nnz={model.similarity.nnz}", flush=True)

    reports = []
    for run_dir in args.run_dirs:
        rep = report_run(run_dir, model, user2id, item2id)
        reports.append(rep)
        print(json.dumps(rep, indent=2, ensure_ascii=False), flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
