"""Tests for statistical analysis utilities."""

import pytest
import numpy as np

from package.evaluation.statistics import (
    bootstrap_confidence_interval,
    paired_bootstrap_difference,
    aggregate_metrics,
    compute_percentiles,
    significance_test,
)


def test_bootstrap_confidence_interval():
    """Test bootstrap confidence interval computation."""
    values = [0.8, 0.85, 0.9, 0.82, 0.88]

    mean, lower, upper = bootstrap_confidence_interval(
        values, confidence_level=0.95, n_bootstrap=100, random_seed=42
    )

    assert 0 < mean < 1
    assert lower <= mean <= upper
    assert lower < upper


def test_bootstrap_confidence_interval_empty():
    """Test bootstrap CI with empty values."""
    mean, lower, upper = bootstrap_confidence_interval([])

    assert mean == 0.0
    assert lower == 0.0
    assert upper == 0.0


def test_paired_bootstrap_difference():
    """Test paired bootstrap difference."""
    values_a = [0.8, 0.85, 0.9, 0.82, 0.88]
    values_b = [0.85, 0.9, 0.95, 0.87, 0.93]

    mean_diff, lower, upper, p_value = paired_bootstrap_difference(
        values_a, values_b, confidence_level=0.95, n_bootstrap=100, random_seed=42
    )

    assert mean_diff > 0  # B is higher than A
    assert lower <= mean_diff <= upper
    assert 0 <= p_value <= 1


def test_paired_bootstrap_difference_mismatched_length():
    """Test paired bootstrap with mismatched lengths."""
    values_a = [0.8, 0.85, 0.9]
    values_b = [0.85, 0.9]

    with pytest.raises(ValueError):
        paired_bootstrap_difference(values_a, values_b)


def test_paired_bootstrap_difference_empty():
    """Test paired bootstrap with empty values."""
    mean_diff, lower, upper, p_value = paired_bootstrap_difference([], [])

    assert mean_diff == 0.0
    assert lower == 0.0
    assert upper == 0.0
    assert p_value == 1.0


def test_aggregate_metrics():
    """Test metrics aggregation."""
    metrics_list = [
        {"task_success": 0.8, "latency": 1.0},
        {"task_success": 0.85, "latency": 1.1},
        {"task_success": 0.9, "latency": 0.9},
    ]

    aggregated = aggregate_metrics(metrics_list)

    assert "task_success" in aggregated
    assert "latency" in aggregated
    assert pytest.approx(aggregated["task_success"]["mean"]) == 0.85
    assert pytest.approx(aggregated["latency"]["mean"]) == 1.0
    assert aggregated["task_success"]["count"] == 3


def test_aggregate_metrics_empty():
    """Test metrics aggregation with empty list."""
    aggregated = aggregate_metrics([])

    assert aggregated == {}


def test_compute_percentiles():
    """Test percentile computation."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

    percentiles = compute_percentiles(values, percentiles=[50, 95, 99])

    assert "p50" in percentiles
    assert "p95" in percentiles
    assert "p99" in percentiles
    assert percentiles["p50"] == 5.5  # Median of 1-10


def test_compute_percentiles_empty():
    """Test percentile computation with empty values."""
    percentiles = compute_percentiles([])

    assert percentiles == {}


def test_significance_test_paired():
    """Test paired significance test."""
    values_a = [0.8, 0.85, 0.9, 0.82, 0.88]
    values_b = [0.85, 0.9, 0.95, 0.87, 0.93]

    result = significance_test(values_a, values_b, test_type="paired", alpha=0.05)

    assert result["test_type"] == "wilcoxon_paired"
    assert "p_value" in result
    assert "significant" in result
    assert "mean_difference" in result


def test_significance_test_independent():
    """Test independent significance test."""
    values_a = [0.8, 0.85, 0.9]
    values_b = [0.6, 0.65, 0.7]

    result = significance_test(values_a, values_b, test_type="independent", alpha=0.05)

    assert result["test_type"] == "mannwhitney_u"
    assert "p_value" in result
    assert "significant" in result
    assert "mean_a" in result
    assert "mean_b" in result


def test_significance_test_paired_mismatched():
    """Test paired test with mismatched lengths."""
    values_a = [0.8, 0.85]
    values_b = [0.85, 0.9, 0.95]

    with pytest.raises(ValueError):
        significance_test(values_a, values_b, test_type="paired")
