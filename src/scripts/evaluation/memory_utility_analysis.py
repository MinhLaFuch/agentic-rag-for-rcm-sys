"""CLI script for Memory UTILITY analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package.evaluation.ablation._loader import check_compatibility, load_config_data, load_scored_data
from package.evaluation.component.benchmarks import (
    analyze,
    default_metrics,
    render_markdown,
)


def _load_runs(dirs: list[str]) -> tuple[list[list[dict]], list[dict]]:
    scored, cfgs = [], []
    for d in dirs:
        p = Path(d)
        scored.append(load_scored_data(p))
        try:
            cfgs.append(load_config_data(p))
        except Exception:  # config optional for analysis; compatibility check is skipped
            pass
    return scored, cfgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Memory UTILITY analysis: paired, multi-run comparison planner vs planner_memory",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dirs", nargs="+", help="experiment dirs; each holds BOTH agents (one run per dir)")
    ap.add_argument("--baseline-dirs", nargs="+", help="override: dirs for the baseline agent")
    ap.add_argument("--memory-dirs", nargs="+", help="override: dirs for the memory agent")
    ap.add_argument("--baseline-agent", default="planner")
    ap.add_argument("--memory-agent", default="planner_memory")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--metrics", nargs="*")
    ap.add_argument("--resamples", type=int, default=5000)
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args(argv)

    a_dirs = args.baseline_dirs or args.dirs
    b_dirs = args.memory_dirs or args.dirs
    if not a_dirs or not b_dirs:
        ap.error("give --dirs, or both --baseline-dirs and --memory-dirs")
    runs_a, cfg_a = _load_runs(a_dirs)
    runs_b, cfg_b = _load_runs(b_dirs)

    compat: list[str] = []
    ref = (cfg_a or cfg_b or [None])[0]
    if ref is not None:
        for i, c in enumerate(cfg_a + cfg_b):
            ok, why = check_compatibility(ref, c)
            if not ok:
                compat.append(f"run #{i} incompatible with first run: {why}")

    metrics = args.metrics or default_metrics(args.k)
    kw = dict(resamples=args.resamples, confidence=args.confidence, seed=args.seed, min_n=args.min_n)
    result = analyze(runs_a, runs_b, args.baseline_agent, args.memory_agent, metrics, **kw)
    meta = {"agent_a": args.baseline_agent, "agent_b": args.memory_agent, "runs_a": len(runs_a),
            "runs_b": len(runs_b), "compat_warnings": compat, "dirs_a": a_dirs, "dirs_b": b_dirs, **kw}

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory_utility.json").write_text(json.dumps({"meta": meta, "result": result}, indent=2), encoding="utf-8")
    md = render_markdown(result, meta)
    (out / "memory_utility.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())