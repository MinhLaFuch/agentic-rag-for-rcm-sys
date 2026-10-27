"""Schema definitions for component-level evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
import hashlib
import json


COMPONENT_BENCHMARK_VERSION = "1.0.0"


@dataclass
class BenchmarkCase:
    """A single test case for component benchmarking.

    Attributes:
        case_id: Unique identifier for this test case
        input: Input data for the component (component-specific)
        expected: Expected output or oracle for scoring (component-specific)
        tags: Tags for categorization (normal, hard, ambiguous, negative, oracle, etc.)
        metadata: Additional metadata (description, difficulty, notes, etc.)
    """
    case_id: str
    input: dict[str, Any]
    expected: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "case_id": self.case_id,
            "input": self.input,
            "expected": self.expected,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkCase":
        """Create from dict."""
        return cls(
            case_id=data["case_id"],
            input=data["input"],
            expected=data["expected"],
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark case.

    Attributes:
        case_id: The case ID that was run
        actual_output: Actual output from the component
        success: Whether the component ran without errors
        error: Error message if success=False
        metrics: Dict of metric names to values (component-specific)
        latency_seconds: Time taken to run this case
        token_usage: Token usage if applicable (prompt_tokens, completion_tokens)
    """
    case_id: str
    actual_output: dict[str, Any] | None
    success: bool
    error: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    latency_seconds: float = 0.0
    token_usage: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "case_id": self.case_id,
            "actual_output": self.actual_output,
            "success": self.success,
            "error": self.error,
            "metrics": self.metrics,
            "latency_seconds": self.latency_seconds,
            "token_usage": self.token_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkResult":
        """Create from dict."""
        return cls(
            case_id=data["case_id"],
            actual_output=data.get("actual_output"),
            success=data["success"],
            error=data.get("error"),
            metrics=data.get("metrics", {}),
            latency_seconds=data.get("latency_seconds", 0.0),
            token_usage=data.get("token_usage"),
        )


@dataclass
class BenchmarkSummary:
    """Summary of a complete benchmark run.

    Attributes:
        benchmark_version: Version of the benchmark schema
        component: Name of the component being benchmarked
        config: Configuration used for the benchmark
        prompt_schema_hash: Hash of prompt/schema if applicable
        run_count: Number of times the benchmark was run (for averaging)
        per_case_results: List of individual case results
        metrics: Aggregated metrics (mean, std, etc.)
        latency: Latency statistics (mean, p50, p95, etc.)
        token_cost: Token usage statistics if applicable
        timestamp: ISO timestamp of when the benchmark was run
        git_sha: Git commit SHA at time of benchmark
        tags_summary: Metrics aggregated by tag
    """
    benchmark_version: str = COMPONENT_BENCHMARK_VERSION
    component: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    prompt_schema_hash: str | None = None
    run_count: int = 1
    per_case_results: list[BenchmarkResult] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    latency: dict[str, float] = field(default_factory=dict)
    token_cost: dict[str, float] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_sha: str = ""
    tags_summary: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "benchmark_version": self.benchmark_version,
            "component": self.component,
            "config": self.config,
            "prompt_schema_hash": self.prompt_schema_hash,
            "run_count": self.run_count,
            "per_case_results": [r.to_dict() for r in self.per_case_results],
            "metrics": self.metrics,
            "latency": self.latency,
            "token_cost": self.token_cost,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "tags_summary": self.tags_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkSummary":
        """Create from dict."""
        return cls(
            benchmark_version=data.get("benchmark_version", COMPONENT_BENCHMARK_VERSION),
            component=data.get("component", ""),
            config=data.get("config", {}),
            prompt_schema_hash=data.get("prompt_schema_hash"),
            run_count=data.get("run_count", 1),
            per_case_results=[BenchmarkResult.from_dict(r) for r in data.get("per_case_results", [])],
            metrics=data.get("metrics", {}),
            latency=data.get("latency", {}),
            token_cost=data.get("token_cost"),
            timestamp=data.get("timestamp"),
            git_sha=data.get("git_sha", ""),
            tags_summary=data.get("tags_summary", {}),
        )

    def compute_hash(self) -> str:
        """Compute a hash of the benchmark configuration for reproducibility."""
        hash_input = {
            "component": self.component,
            "config": self.config,
            "prompt_schema_hash": self.prompt_schema_hash,
            "benchmark_version": self.benchmark_version,
        }
        return hashlib.sha256(json.dumps(hash_input, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class RegressionReport:
    """Report comparing two benchmark runs.

    Attributes:
        baseline_summary: Baseline benchmark summary
        current_summary: Current benchmark summary
        metric_changes: Dict of metric name to change (delta, percent_change, significance)
        latency_changes: Latency statistics changes
        tag_changes: Changes aggregated by tag
        summary: Overall summary (improved, regressed, neutral)
        timestamp: ISO timestamp of when the report was generated
    """
    baseline_summary: BenchmarkSummary
    current_summary: BenchmarkSummary
    metric_changes: dict[str, dict[str, float]] = field(default_factory=dict)
    latency_changes: dict[str, dict[str, float]] = field(default_factory=dict)
    tag_changes: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    summary: str = "neutral"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "baseline_summary": self.baseline_summary.to_dict(),
            "current_summary": self.current_summary.to_dict(),
            "metric_changes": self.metric_changes,
            "latency_changes": self.latency_changes,
            "tag_changes": self.tag_changes,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegressionReport":
        """Create from dict."""
        return cls(
            baseline_summary=BenchmarkSummary.from_dict(data["baseline_summary"]),
            current_summary=BenchmarkSummary.from_dict(data["current_summary"]),
            metric_changes=data.get("metric_changes", {}),
            latency_changes=data.get("latency_changes", {}),
            tag_changes=data.get("tag_changes", {}),
            summary=data.get("summary", "neutral"),
            timestamp=data.get("timestamp"),
        )
