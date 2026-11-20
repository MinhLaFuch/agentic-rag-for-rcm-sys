"""Cross-tabulate per-target loss stage x ItemKNN core membership.

For each target in a run's scored.jsonl, join requests.jsonl (numeric item idx
targets) with the train_core ItemKNN model and report, per best_stage:

  - core:     item has >=1 similarity neighbor (CF path exists)
  - non_core: no neighbors (SimilarTool/CF can never surface it)

Answers: of the "retrieve"-stage losses (catalog-visible but missed), how many
are structurally unreachable by the CF path vs reachable-but-missed?

Usage (from src/):
    python scripts/evaluation/target_core_coverage.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse

from package.config import load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.config import select_fit_target


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def core_item_set() -> tuple[sparse.csr_matrix, int]:
    data_paths = resolve_bundle_paths()
    baselines = load_config("eval/baselines")["baselines"]
    knn_k = int(baselines["item_knn"]["k"])
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, _ = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    model = build_core_model(data_paths, "validation", knn_k, fit_df, user2id, item2id)
    sim = model.similarity.tocsr()
    # item is "core" if it has at least one neighbor (column nnz > 0)
    col_nnz = np.asarray(sim.getnnz(axis=0)).ravel()
    core_mask = col_nnz > 0
    return core_mask, int(sim.shape[0])


def report_run(run_dir: Path, core_mask: np.ndarray) -> dict:
    req_path = run_dir / "requests.jsonl"
    scored_path = run_dir / "scored.jsonl"
    if not scored_path.exists():
        return {"run": str(run_dir), "error": "no scored.jsonl"}
    requests = {}
    if req_path.exists():
        for r in _load_jsonl(req_path):
            requests[r["request_id"]] = r

    # stage x core crosstab; stage x kind x core
    crosstab = Counter()
    kind_crosstab = defaultdict(Counter)
    n_targets = 0
    unmapped = 0
    for row in _load_jsonl(scored_path):
        req = requests.get(row.get("request_id"), {})
        kind = req.get("kind", "?")
        detail = row.get("target_stage_detail") or {}
        for t_str, info in detail.items():
            bs = info.get("best_stage")
            if not bs:
                continue
            n_targets += 1
            try:
                idx = int(t_str)
            except ValueError:
                unmapped += 1
                continue
            core = bool(core_mask[idx]) if 0 <= idx < core_mask.size else False
            crosstab[(bs, "core" if core else "non_core")] += 1
            kind_crosstab[kind][(bs, "core" if core else "non_core")] += 1

    by_stage = defaultdict(Counter)
    for (stage, core), c in crosstab.items():
        by_stage[stage][core] += c

    return {
        "run": str(run_dir),
        "n_targets": n_targets,
        "unmapped_targets": unmapped,
        "stage_x_core": {s: dict(c) for s, c in by_stage.items()},
        "kind_stage_x_core": {k: {f"{s}|{core}": c for (s, core), c in cnt.items()}
                              for k, cnt in kind_crosstab.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    core_mask, n_items = core_item_set()
    print(f"core items (col nnz>0): {int(core_mask.sum())} / {n_items}", flush=True)

    reports = []
    for run_dir in args.run_dirs:
        rep = report_run(run_dir, core_mask)
        reports.append(rep)
        print(json.dumps(rep, indent=2, ensure_ascii=False), flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
