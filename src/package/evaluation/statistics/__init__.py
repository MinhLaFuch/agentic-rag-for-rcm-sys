"""Statistical analysis package."""

from .bootstrap import (
    bootstrap_confidence_interval,
    paired_bootstrap_difference,
    aggregate_metrics,
    compute_percentiles,
    significance_test,
)

__all__ = [
    "bootstrap_confidence_interval",
    "paired_bootstrap_difference",
    "aggregate_metrics",
    "compute_percentiles",
    "significance_test",
]
