"""Analyze all metrics for memory utility comparison."""

from __future__ import annotations

from typing import Any

from .analyze_metric import analyze_metric
from .default_metrics import default_metrics


def analyze(
    runs_a: list[list[dict]], runs_b: list[list[dict]], agent_a: str, agent_b: str, metrics: list[str],
    **kw,
) -> dict[str, dict[str, Any]]:
    """Analyze all metrics, return {metric: {group: stats}}."""
    result: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        result[metric] = analyze_metric(runs_a, runs_b, agent_a, agent_b, metric, **kw)
    return result