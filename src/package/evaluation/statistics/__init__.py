"""Statistical analysis package."""

from ._bootstrap import (
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
