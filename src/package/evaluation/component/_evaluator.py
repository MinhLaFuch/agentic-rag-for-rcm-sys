"""Base evaluator interface for component-level benchmarking."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable
from collections import defaultdict
import numpy as np

from ._schema import BenchmarkCase, BenchmarkResult, BenchmarkSummary


class ComponentEvaluator(ABC):
    """Base class for component evaluators.

    Subclasses must implement:
    - run_component: Run the component with given input
    - score_component: Score the actual output against expected
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the evaluator.

        Args:
            config: Configuration dictionary for the evaluator
        """
        self.config = config or {}

    @abstractmethod
    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run the component with the given input.

        Args:
            case_input: Input data for the component

        Returns:
            Actual output from the component

        Raises:
            Exception: If the component fails to run
        """
        pass

    @abstractmethod
    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score the actual output against the expected/oracle.

        Args:
            actual_output: Actual output from the component
            expected: Expected output or oracle

        Returns:
            Dict of metric names to values (higher is better unless specified)
        """
        pass

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        """Run a single benchmark case.

        Args:
            case: BenchmarkCase to run

        Returns:
            BenchmarkResult with metrics and latency
        """
        start_time = time.perf_counter()
        actual_output = None
        success = False
        error = None
        metrics = {}

        try:
            actual_output = self.run_component(case.input)
            success = True
            metrics = self.score_component(actual_output, case.expected)
        except Exception as e:
            error = str(e)
            success = False

        latency_seconds = time.perf_counter() - start_time

        return BenchmarkResult(
            case_id=case.case_id,
            actual_output=actual_output,
            success=success,
            error=error,
            metrics=metrics,
            latency_seconds=latency_seconds,
        )

    def run_benchmark(
        self,
        cases: list[BenchmarkCase],
        runs: int = 1,
        component_name: str = "",
        git_sha: str = "",
    ) -> BenchmarkSummary:
        """Run the full benchmark on all cases.

        Args:
            cases: List of BenchmarkCase objects
            runs: Number of times to run each case (for averaging)
            component_name: Name of the component being benchmarked
            git_sha: Git commit SHA

        Returns:
            BenchmarkSummary with aggregated results
        """
        per_case_results: list[BenchmarkResult] = []

        # Run each case multiple times if requested
        for case in cases:
            case_results = []
            for _ in range(runs):
                result = self.run_case(case)
                case_results.append(result)

            # Average metrics across runs
            if runs > 1:
                averaged = self._average_results(case_results)
                averaged.case_id = case.case_id
                per_case_results.append(averaged)
            else:
                per_case_results.append(case_results[0])

        # Aggregate metrics
        metrics = self._aggregate_metrics(per_case_results)
        latency = self._aggregate_latency(per_case_results)
        tags_summary = self._aggregate_by_tags(per_case_results, cases)

        return BenchmarkSummary(
            component=component_name,
            config=self.config,
            run_count=runs,
            per_case_results=per_case_results,
            metrics=metrics,
            latency=latency,
            tags_summary=tags_summary,
            git_sha=git_sha,
        )

    def _average_results(self, results: list[BenchmarkResult]) -> BenchmarkResult:
        """Average metrics across multiple runs of the same case."""
        if not results:
            return BenchmarkResult(case_id="", actual_output=None, success=False)

        # Average numeric metrics
        averaged_metrics: dict[str, float] = {}
        metric_keys = set()
        for r in results:
            metric_keys.update(r.metrics.keys())

        for key in metric_keys:
            values = [r.metrics[key] for r in results if key in r.metrics]
            if values:
                averaged_metrics[key] = float(np.mean(values))

        # Average latency
        avg_latency = float(np.mean([r.latency_seconds for r in results]))

        # Use the last run's actual_output and success status
        last_result = results[-1]

        return BenchmarkResult(
            case_id=last_result.case_id,
            actual_output=last_result.actual_output,
            success=last_result.success,
            error=last_result.error,
            metrics=averaged_metrics,
            latency_seconds=avg_latency,
            token_usage=last_result.token_usage,
        )

    def _aggregate_metrics(self, results: list[BenchmarkResult]) -> dict[str, float]:
        """Aggregate metrics across all cases."""
        metric_keys = set()
        for r in results:
            metric_keys.update(r.metrics.keys())

        aggregated = {}
        for key in sorted(metric_keys):
            values = [r.metrics[key] for r in results if key in r.metrics]
            if values:
                aggregated[f"{key}_mean"] = float(np.mean(values))
                aggregated[f"{key}_std"] = float(np.std(values))
                aggregated[f"{key}_min"] = float(np.min(values))
                aggregated[f"{key}_max"] = float(np.max(values))

        # Overall success rate
        success_count = sum(1 for r in results if r.success)
        aggregated["success_rate"] = success_count / len(results) if results else 0.0

        return aggregated

    def _aggregate_latency(self, results: list[BenchmarkResult]) -> dict[str, float]:
        """Aggregate latency statistics."""
        latencies = [r.latency_seconds for r in results]
        if not latencies:
            return {}

        return {
            "mean": float(np.mean(latencies)),
            "std": float(np.std(latencies)),
            "min": float(np.min(latencies)),
            "max": float(np.max(latencies)),
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
            "p99": float(np.percentile(latencies, 99)),
        }

    def _aggregate_by_tags(
        self, results: list[BenchmarkResult], cases: list[BenchmarkCase]
    ) -> dict[str, dict[str, float]]:
        """Aggregate metrics by tags."""
        # Map case_id to tags
        case_to_tags = {case.case_id: case.tags for case in cases}

        # Group results by tags
        by_tag: dict[str, list[BenchmarkResult]] = defaultdict(list)
        for result in results:
            tags = case_to_tags.get(result.case_id, [])
            for tag in tags:
                by_tag[tag].append(result)

        # Aggregate per tag
        tag_summary: dict[str, dict[str, float]] = {}
        for tag, tag_results in by_tag.items():
            metrics = self._aggregate_metrics(tag_results)
            latency = self._aggregate_latency(tag_results)
            tag_summary[tag] = {**metrics, **latency}

        return tag_summary
