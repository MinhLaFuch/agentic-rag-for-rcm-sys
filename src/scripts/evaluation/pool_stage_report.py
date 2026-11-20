"""Summarize per-target loss-stage funnel from scored.jsonl + requests.jsonl.

Answers: "where do held-out targets die?" — pool (not in visible catalog),
retrieve (tool candidate lists missed them), rank_* (reached RankTool but
lost), final/survived.

Usage (from src/):
    python scripts/evaluation/pool_stage_report.py <run_dir> [<run_dir> ...]
    # run_dir = experiments/agent_eval/campaigns/<campaign>/<exp>/run_<N>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE_ORDER = ["pool", "retrieve", "rank_input", "rank_unscored",
               "rank_excluded_seen", "rank_topk", "final", "survived"]


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def report_run(run_dir: Path) -> dict:
    requests = {}
    req_path = run_dir / "requests.jsonl"
    if req_path.exists():
        for r in _load_jsonl(req_path):
            requests[r["request_id"]] = r

    scored_path = run_dir / "scored.jsonl"
    if not scored_path.exists():
        return {"run": str(run_dir), "error": "no scored.jsonl"}

    # best_stage per target + per-path stage_lost + per-kind recall
    best = Counter()
    path_lost = Counter()
    kind_best = defaultdict(Counter)
    kind_recall = defaultdict(list)
    n_scored = 0
    for row in _load_jsonl(scored_path):
        n_scored += 1
        kind = requests.get(row.get("request_id"), {}).get("kind", "?")
        detail = row.get("target_stage_detail") or {}
        for _t, info in detail.items():
            bs = info.get("best_stage")
            if bs:
                best[bs] += 1
                kind_best[kind][bs] += 1
        for _t, info in detail.items():
            for path, pe in (info.get("paths") or {}).items():
                rl = pe.get("stage_lost")
                if rl:
                    path_lost[(path, rl)] += 1
        for k in ("recall@10", "hit_rate@10"):
            v = row.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                kind_recall[(kind, k)].append(v)

    return {
        "run": str(run_dir),
        "n_scored": n_scored,
        "best_stage": dict(best),
        "path_stage_lost": {f"{p}:{s}": c for (p, s), c in path_lost.items()},
        "kind_best_stage": {k: dict(c) for k, c in kind_best.items()},
        "kind_recall": {
            f"{k}:{m}": round(sum(v) / len(v), 4) if v else None
            for (k, m), v in kind_recall.items()
        },
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for arg in sys.argv[1:]:
        result = report_run(Path(arg))
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
