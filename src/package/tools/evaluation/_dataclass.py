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

    def to_metrics(self, fit_seconds: float) -> dict:
        """Dạng dict ghi vào metrics.json (dùng chung cho run_baselines / tune_baselines)."""
        return {
            "overall": self.overall,
            "by_segment": self.by_segment,
            "num_users": self.num_users,
            "catalog_coverage": self.catalog_coverage,
            "target_item_seen_ratio": self.target_item_seen_ratio,
            "fit_seconds": round(fit_seconds, 2),
        }
