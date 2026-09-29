"""Data classes for evaluation results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluationResult:
    overall: dict[str, float]
    by_segment: dict[str, dict[str, float]]
    num_users: dict[str, int]
    catalog_coverage: dict[str, float]
    target_item_seen_ratio: float
