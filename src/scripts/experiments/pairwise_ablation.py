"""Pairwise ablation analysis giữa hai scored.jsonl (None-aware).

Dùng khi metric có giá trị undefined (vd planner không memory trả
task_success=None cho personalized): các cặp None bị loại khỏi effective n
và báo cáo rõ, thay vì bị tính như False như compare_experiments.py.

Cách chạy:
    PYTHONPATH=. python scripts/experiments/pairwise_ablation.py \
        --a experiments/agent_eval/campaigns/campaign_001/exp_6_.../run_1/scored.jsonl --a-agent planner \
        --b experiments/agent_eval/campaigns/campaign_001/exp_10_.../run_1/scored.jsonl --b-agent planner_memory \
        --out experiments/agent_eval/ablation/pairwise_memory_effect.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from package.evaluation.ablation import (
    get_ablation_limits,
    pairwise_report,
    render_pairwise_markdown,
)
from package.utils import ensure_utf8_stdout


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pairwise (None-aware) ablation comparison")
    p.add_argument("--a", required=True, help="scored.jsonl của phía A")
    p.add_argument("--a-agent", required=True, help="giá trị cột 'agent' của phía A")
    p.add_argument("--b", required=True, help="scored.jsonl của phía B")
    p.add_argument("--b-agent", required=True, help="giá trị cột 'agent' của phía B")
    p.add_argument("--kinds", default=None, help="csv các kind cần so (mặc định: tất cả)")
    p.add_argument("--out", default=None, help="ghi markdown ra file (mặc định: stdout)")
    p.add_argument("--json-out", default=None, help="ghi report JSON ra file")
    return p.parse_args()


def main() -> None:
    ensure_utf8_stdout()
    args = parse_args()
    limits = get_ablation_limits()

    scored_a = _load_file(args.a)
    scored_b = _load_file(args.b)

    kinds = [k.strip() for k in args.kinds.split(",")] if args.kinds else None
    title = f"{args.a_agent} vs {args.b_agent}"
    report = pairwise_report(
        scored_a,
        args.a_agent,
        scored_b,
        args.b_agent,
        kinds=kinds,
        confidence=limits.confidence,
        bootstrap_resamples=limits.bootstrap_resamples,
        seed=limits.seed,
    )
    report["title"] = title
    report["source"] = {"a": args.a, "b": args.b}

    md = render_pairwise_markdown(report, title=title)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Saved: {args.out}")
    else:
        print(md)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved JSON: {args.json_out}")


def _load_file(path: str) -> list[dict]:
    import json as _json

    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(_json.loads(line))
    return rows


if __name__ == "__main__":
    main()
