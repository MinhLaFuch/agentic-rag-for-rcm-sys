"""CLI runner for component-level benchmarks."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._loader import load_cases, filter_cases_by_tag, filter_cases_by_metadata
from ._schema import BenchmarkSummary
from ._regression import compare_benchmarks, format_regression_report


def get_git_sha() -> str:
    """Get the current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def run_benchmark_cli() -> None:
    """CLI entrypoint for running component benchmarks."""
    parser = argparse.ArgumentParser(
        description="Run component-level benchmarks for individual components",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--component",
        type=str,
        required=True,
        help="Name of the component to benchmark (e.g., memory, planner, executor, reflection, inference, grounding)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the benchmark dataset file (JSON or JSONL)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to run each case (for averaging)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save the benchmark results JSON (default: <component>_benchmark_<timestamp>.json)",
    )
    parser.add_argument(
        "--tags",
        type=str,
        nargs="*",
        default=None,
        help="Filter cases by tags (OR logic: return cases with ANY of these tags)",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        nargs="*",
        default=None,
        help="Filter cases by metadata (format: key=value, multiple allowed, AND logic)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file for the evaluator",
    )
    parser.add_argument(
        "--git-sha",
        type=str,
        default=None,
        help="Git commit SHA (auto-detected if not provided)",
    )

    args = parser.parse_args()

    # Load dataset
    print(f"Loading dataset from {args.dataset}...")
    cases = load_cases(args.dataset)
    print(f"Loaded {len(cases)} cases")

    # Filter by tags
    if args.tags:
        cases = filter_cases_by_tag(cases, args.tags)
        print(f"Filtered to {len(cases)} cases by tags: {args.tags}")

    # Filter by metadata
    if args.metadata:
        metadata_filter: dict[str, Any] = {}
        for item in args.metadata:
            if "=" in item:
                key, value = item.split("=", 1)
                # Try to parse as JSON for complex values
                try:
                    metadata_filter[key] = json.loads(value)
                except json.JSONDecodeError:
                    metadata_filter[key] = value
        cases = filter_cases_by_metadata(cases, metadata_filter)
        print(f"Filtered to {len(cases)} cases by metadata: {metadata_filter}")

    if not cases:
        print("No cases to run after filtering")
        return

    # Load config
    config: dict[str, Any] = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"Loaded config from {args.config}")

    # Get git SHA
    git_sha = args.git_sha if args.git_sha else get_git_sha()
    print(f"Git SHA: {git_sha}")

    # Import and instantiate the appropriate evaluator
    print(f"Instantiating evaluator for component: {args.component}")
    evaluator = _get_evaluator(args.component, config)

    # Run benchmark
    print(f"Running benchmark with {args.runs} run(s) per case...")
    summary = evaluator.run_benchmark(
        cases=cases,
        runs=args.runs,
        component_name=args.component,
        git_sha=git_sha,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"{args.component}_benchmark_{timestamp}.json")

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\nBenchmark complete!")
    print(f"Results saved to: {output_path}")
    print(f"\nSummary:")
    print(f"  Component: {summary.component}")
    print(f"  Cases run: {len(summary.per_case_results)}")
    print(f"  Success rate (ran without exception, NOT correctness): {summary.metrics.get('success_rate', 0):.2%}")
    quality = {k: v for k, v in summary.metrics.items() if k.endswith("_mean")}
    if quality:
        print("  Quality metrics (mean over cases):")
        for k, v in sorted(quality.items()):
            print(f"    {k[:-5]}: {v:.3f}")
    print(f"  Mean latency: {summary.latency.get('mean', 0):.4f}s")
    print(f"  P95 latency: {summary.latency.get('p95', 0):.4f}s")


def run_regression_cli() -> None:
    """CLI entrypoint for comparing benchmark runs."""
    parser = argparse.ArgumentParser(
        description="Compare two benchmark runs and generate a regression report",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Path to the baseline benchmark results JSON",
    )
    parser.add_argument(
        "--current",
        type=str,
        required=True,
        help="Path to the current benchmark results JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save the regression report JSON (default: regression_report_<timestamp>.json)",
    )
    parser.add_argument(
        "--metric-threshold",
        type=float,
        default=0.05,
        help="Threshold for significant metric change (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--latency-threshold",
        type=float,
        default=0.1,
        help="Threshold for significant latency change (default: 0.1 = 10%%)",
    )
    parser.add_argument(
        "--text-report",
        type=str,
        default=None,
        help="Path to save the human-readable text report (optional)",
    )

    args = parser.parse_args()

    # Load baseline and current
    print(f"Loading baseline from {args.baseline}...")
    with open(args.baseline, "r", encoding="utf-8") as f:
        baseline = BenchmarkSummary.from_dict(json.load(f))

    print(f"Loading current from {args.current}...")
    with open(args.current, "r", encoding="utf-8") as f:
        current = BenchmarkSummary.from_dict(json.load(f))

    # Compare
    print("Comparing benchmarks...")
    report = compare_benchmarks(
        baseline=baseline,
        current=current,
        metric_threshold=args.metric_threshold,
        latency_threshold=args.latency_threshold,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"regression_report_{timestamp}.json")

    # Save JSON report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\nRegression analysis complete!")
    print(f"JSON report saved to: {output_path}")
    print(f"Summary: {report.summary.upper()}")

    # Save text report if requested
    if args.text_report:
        text_path = Path(args.text_report)
        text_report = format_regression_report(report)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_report)
        print(f"Text report saved to: {text_path}")
    else:
        # Print to console
        print("\n" + format_regression_report(report))


def _get_evaluator(component: str, config: dict[str, Any]):
    """Import and instantiate the appropriate evaluator for the component."""
    if component == "memory":
        from .benchmarks.memory_benchmark import MemoryEvaluator
        from package.tools.corpus import ItemCorpus
        import pandas as pd

        # For the dummy benchmark, create synthetic data
        # In real usage, this would come from config or actual data files
        meta = pd.DataFrame({
            "parent_asin": ["vg_a", "vg_b", "vg_c"],
            "domain": ["Video_Games"] * 3,
            "title": ["Game A", "Game B", "Game C"],
            "store": ["StoreA", "StoreB", "StoreC"],
            "price": [300.0, 1.0, 150.0],
            "average_rating": [4.5, 3.5, 4.0],
            "rating_number": [100, 50, 75],
            "main_category": ["Action", "Puzzle", "RPG"],
            "categories": [["Action"], ["Puzzle"], ["RPG"]],
        })
        corpus = ItemCorpus.from_dataframe(meta)

        interactions = pd.DataFrame({
            "user_id": ["u1"] * 3,
            "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c"],
            "user_idx": [0] * 3,
            "item_idx": [0, 1, 2],
            "rating": [5, 4, 5],
            "timestamp": [0, 1, 2],
        })
        user2id = {"u1": 0, "u0": 1, "unknown_user": 2}
        item2id = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2}

        return MemoryEvaluator(interactions, user2id, item2id, corpus, config)
    elif component == "memory_correctness":
        from .benchmarks.memory_correctness_evaluator import MemoryCorrectnessEvaluator
        from .benchmarks.memory_correctness_setup import create_test_interactions, create_test_meta, create_test_mappings

        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)

        return MemoryCorrectnessEvaluator(interactions, user2id, item2id, create_test_meta(), config)
    elif component == "planner":
        from .benchmarks.planner_benchmark import PlannerBenchmark

        return PlannerBenchmark(config)
    else:
        raise NotImplementedError(
            f"Evaluator for component '{component}' not yet implemented. "
            "Please implement a ComponentEvaluator subclass for this component."
        )


if __name__ == "__main__":
    # Dispatch to appropriate subcommand
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "regress":
        # Remove "regress" from args before parsing
        sys.argv.pop(1)
        run_regression_cli()
    else:
        run_benchmark_cli()
