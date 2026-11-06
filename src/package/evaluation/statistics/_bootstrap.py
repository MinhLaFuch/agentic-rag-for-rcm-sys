"""Statistical analysis utilities for evaluation results.

Implements bootstrap confidence intervals, paired comparisons, and
statistical aggregation for experiment results.
"""

from __future__ import annotations

import numpy as np
from typing import Any, List, Tuple
import random


def bootstrap_confidence_interval(
    values: List[float],
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    random_seed: int | None = None,
) -> Tuple[float, float, float]:
    """Compute bootstrap confidence interval for a metric.

    Args:
        values: List of observed values
        confidence_level: Confidence level (0-1)
        n_bootstrap: Number of bootstrap samples
        random_seed: Random seed for reproducibility

    Returns:
        Tuple of (mean, lower_bound, upper_bound)
    """
    if not values:
        return 0.0, 0.0, 0.0

    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    values = np.array(values)
    n = len(values)

    # Bootstrap sampling
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(values, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    bootstrap_means = np.array(bootstrap_means)

    # Compute confidence interval
    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    lower_bound = np.percentile(bootstrap_means, lower_percentile)
    upper_bound = np.percentile(bootstrap_means, upper_percentile)
    mean = np.mean(values)

    return float(mean), float(lower_bound), float(upper_bound)


def paired_bootstrap_difference(
    values_a: List[float],
    values_b: List[float],
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    random_seed: int | None = None,
) -> Tuple[float, float, float, float]:
    """Compute bootstrap confidence interval for paired difference.

    Args:
        values_a: Values from experiment A
        values_b: Values from experiment B (same cases, paired)
        confidence_level: Confidence level (0-1)
        n_bootstrap: Number of bootstrap samples
        random_seed: Random seed for reproducibility

    Returns:
        Tuple of (mean_diff, lower_bound, upper_bound, p_value)
    """
    if len(values_a) != len(values_b):
        raise ValueError("Values must be paired (same length)")

    if not values_a:
        return 0.0, 0.0, 0.0, 1.0

    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    values_a = np.array(values_a)
    values_b = np.array(values_b)
    n = len(values_a)

    # Compute observed differences
    observed_diff = np.mean(values_b - values_a)

    # Bootstrap sampling of differences
    bootstrap_diffs = []
    for _ in range(n_bootstrap):
        # Sample pairs together (paired bootstrap)
        indices = np.random.choice(n, size=n, replace=True)
        sample_a = values_a[indices]
        sample_b = values_b[indices]
        bootstrap_diffs.append(np.mean(sample_b - sample_a))

    bootstrap_diffs = np.array(bootstrap_diffs)

    # Compute confidence interval
    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    lower_bound = np.percentile(bootstrap_diffs, lower_percentile)
    upper_bound = np.percentile(bootstrap_diffs, upper_percentile)

    # Compute p-value (proportion of bootstrap samples with opposite sign)
    if observed_diff > 0:
        p_value = np.mean(bootstrap_diffs <= 0)
    elif observed_diff < 0:
        p_value = np.mean(bootstrap_diffs >= 0)
    else:
        p_value = 1.0

    return float(observed_diff), float(lower_bound), float(upper_bound), float(p_value)


def aggregate_metrics(
    metrics_list: List[dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Aggregate metrics across multiple runs.

    Args:
        metrics_list: List of metric dictionaries

    Returns:
        Dict mapping metric names to aggregated statistics (mean, std, min, max)
    """
    if not metrics_list:
        return {}

    # Collect all metric keys
    metric_keys = set()
    for metrics in metrics_list:
        metric_keys.update(metrics.keys())

    aggregated = {}
    for key in sorted(metric_keys):
        values = [m.get(key, 0) for m in metrics_list if key in m]
        if values:
            values_arr = np.array(values)
            aggregated[key] = {
                "mean": float(np.mean(values_arr)),
                "std": float(np.std(values_arr)),
                "min": float(np.min(values_arr)),
                "max": float(np.max(values_arr)),
                "count": len(values),
            }

    return aggregated


def compute_percentiles(
    values: List[float],
    percentiles: List[float] = [50, 95, 99],
) -> dict[str, float]:
    """Compute percentiles for a list of values.

    Args:
        values: List of values
        percentiles: List of percentiles to compute (0-100)

    Returns:
        Dict mapping percentile names to values
    """
    if not values:
        return {}

    values_arr = np.array(values)
    result = {}
    for p in percentiles:
        result[f"p{p}"] = float(np.percentile(values_arr, p))

    return result


def significance_test(
    values_a: List[float],
    values_b: List[float],
    test_type: str = "paired",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Perform statistical significance test.

    Args:
        values_a: Values from experiment A
        values_b: Values from experiment B
        test_type: Type of test ("paired" or "independent")
        alpha: Significance level

    Returns:
        Dict with test results
    """
    if test_type == "paired":
        if len(values_a) != len(values_b):
            raise ValueError("Paired test requires equal length arrays")

        # Paired t-test (or bootstrap if non-normal)
        from scipy import stats as scipy_stats

        # Use Wilcoxon signed-rank test (non-parametric paired test)
        statistic, p_value = scipy_stats.wilcoxon(values_a, values_b, alternative="two-sided")

        mean_diff = np.mean(np.array(values_b) - np.array(values_a))

        return {
            "test_type": "wilcoxon_paired",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "significant": p_value < alpha,
            "alpha": alpha,
            "mean_difference": float(mean_diff),
        }
    else:
        # Independent samples t-test (or Mann-Whitney U if non-normal)
        from scipy import stats as scipy_stats

        # Use Mann-Whitney U test (non-parametric independent test)
        statistic, p_value = scipy_stats.mannwhitneyu(values_a, values_b, alternative="two-sided")

        mean_a = np.mean(values_a)
        mean_b = np.mean(values_b)

        return {
            "test_type": "mannwhitney_u",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "significant": p_value < alpha,
            "alpha": alpha,
            "mean_a": float(mean_a),
            "mean_b": float(mean_b),
        }
