"""CLI entrypoint for running component benchmarks."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from package.config import get_data_paths, load_config

from ._loader import load_cases, filter_cases_by_tag, filter_cases_by_metadata
from ._schema import BenchmarkSummary
from ._regression import compare_benchmarks, format_regression_report


def _get_evaluator(component: str, config: dict[str, Any]):
    """Import and instantiate the appropriate evaluator for the component."""
    if component == "memory":
        from .benchmarks.memory_correctness_evaluator import MemoryCorrectnessEvaluator
        from .benchmarks.memory_correctness_setup import create_test_interactions, create_test_meta, create_test_mappings

        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)

        return MemoryCorrectnessEvaluator(interactions, user2id, item2id, create_test_meta(), config)
    elif component == "memory_correctness":
        from .benchmarks.memory_correctness_evaluator import MemoryCorrectnessEvaluator
        from .benchmarks.memory_correctness_setup import create_test_interactions, create_test_meta, create_test_mappings

        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)

        return MemoryCorrectnessEvaluator(interactions, user2id, item2id, create_test_meta(), config)
    elif component == "planner":
        from .benchmarks.planner_benchmark import PlannerBenchmark
        return PlannerBenchmark(config)
    elif component == "executor":
        from .benchmarks.executor_benchmark import ExecutorBenchmark
        return ExecutorBenchmark(config)
    elif component == "grounding":
        from .benchmarks.grounding_benchmark import GroundingBenchmark
        return GroundingBenchmark(config)
    elif component == "integration":
        from .benchmarks.integration_benchmark import IntegrationBenchmark
        return IntegrationBenchmark(config)
    else:
        raise NotImplementedError(
            f"Evaluator for component '{component}' not yet implemented. "
            "Please implement a ComponentEvaluator subclass for this component."
        )

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
        "--git-sha",
        type=str,
        default=None,
        help="Git commit SHA (auto-detected if not provided)",
    )
    args = parser.parse_args()

    # Số lần lặp + config evaluator đọc từ configs/eval/component_benchmarks.yaml
    bench_cfg = load_config("eval/component_benchmarks")["component_benchmarks"]
    runs = int(bench_cfg["runs"])
    config: dict[str, Any] = dict(bench_cfg.get("configs", {}).get(args.component, {}))

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
                try:
                    metadata_filter[key] = json.loads(value)
                except json.JSONDecodeError:
                    metadata_filter[key] = value

        cases = filter_cases_by_metadata(cases, metadata_filter)
        print(f"Filtered to {len(cases)} cases by metadata: {metadata_filter}")

    if not cases:
        print("No cases remaining after filtering")
        return

    # Get git SHA
    git_sha = args.git_sha
    if git_sha is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_sha = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_sha = ""

    # Get evaluator
    evaluator = _get_evaluator(args.component, config)

    # Run benchmark — output dir comes from data_paths.outputs.component_benchmarks
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = str(
        get_data_paths().output_dir("component_benchmarks") / f"{args.component}_benchmark_{timestamp}.json"
    )

    print(f"Running {args.component} benchmark with {len(cases)} cases, {runs} runs each...")
    summary = evaluator.run_benchmark(cases, component_name=args.component, runs=runs)

    # Add metadata
    summary.metadata["git_sha"] = git_sha
    summary.metadata["config"] = config
    summary.metadata["dataset_path"] = args.dataset
    summary.metadata["tags_filter"] = args.tags
    summary.metadata["metadata_filter"] = args.metadata
    summary.metadata["runs"] = runs

    # Save results
    result_json = summary.to_json()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result_json)
    print(f"Results saved to: {output_path}")

    # Print summary
    print(f"\n--- {args.component.upper()} BENCHMARK SUMMARY ---")
    for metric, value in summary.metrics.items():
        print(f"  {metric}: {value:.4f}")
    passed = sum(1 for r in summary.per_case_results if r.success)
    print(f"Total cases: {len(summary.per_case_results)}, Passed: {passed}")

    # Regression report only when comparing two runs (not for single runs)
    # format_regression_report expects a RegressionReport object, not JSON
    # Skip regression report for single-run benchmarks
