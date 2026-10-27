"""Regression analysis for comparing benchmark runs."""

from __future__ import annotations

from typing import Any
import numpy as np

from ._schema import BenchmarkSummary, RegressionReport


def compare_benchmarks(
    baseline: BenchmarkSummary,
    current: BenchmarkSummary,
    metric_threshold: float = 0.05,
    latency_threshold: float = 0.1,
) -> RegressionReport:
    """Compare two benchmark runs and generate a regression report.

    Args:
        baseline: Baseline benchmark summary
        current: Current benchmark summary
        metric_threshold: Threshold for significant metric change (5% default)
        latency_threshold: Threshold for significant latency change (10% default)

    Returns:
        RegressionReport with detailed comparison
    """
    # Compare metrics
    metric_changes = _compare_metrics(baseline.metrics, current.metrics, metric_threshold)

    # Compare latency
    latency_changes = _compare_latency(baseline.latency, current.latency, latency_threshold)

    # Compare by tags
    tag_changes = _compare_tags(baseline.tags_summary, current.tags_summary, metric_threshold, latency_threshold)

    # Determine overall summary
    summary = _determine_summary(metric_changes, latency_changes, tag_changes)

    return RegressionReport(
        baseline_summary=baseline,
        current_summary=current,
        metric_changes=metric_changes,
        latency_changes=latency_changes,
        tag_changes=tag_changes,
        summary=summary,
    )


def _compare_metrics(
    baseline_metrics: dict[str, float],
    current_metrics: dict[str, float],
    threshold: float,
) -> dict[str, dict[str, float]]:
    """Compare metrics between baseline and current."""
    changes = {}

    # Compare mean metrics
    for key in baseline_metrics:
        if not key.endswith("_mean"):
            continue

        base_name = key[:-5]  # Remove "_mean"
        baseline_value = baseline_metrics[key]
        current_value = current_metrics.get(key)

        if current_value is None:
            changes[base_name] = {
                "baseline": baseline_value,
                "current": None,
                "delta": None,
                "percent_change": None,
                "significant": None,
            }
            continue

        delta = current_value - baseline_value
        percent_change = (delta / baseline_value * 100) if baseline_value != 0 else float("inf")
        significant = abs(percent_change) > threshold if baseline_value != 0 else False

        changes[base_name] = {
            "baseline": baseline_value,
            "current": current_value,
            "delta": delta,
            "percent_change": percent_change,
            "significant": significant,
        }

    return changes


def _compare_latency(
    baseline_latency: dict[str, float],
    current_latency: dict[str, float],
    threshold: float,
) -> dict[str, dict[str, float]]:
    """Compare latency statistics."""
    changes = {}

    for key in baseline_latency:
        baseline_value = baseline_latency[key]
        current_value = current_latency.get(key)

        if current_value is None:
            changes[key] = {
                "baseline": baseline_value,
                "current": None,
                "delta": None,
                "percent_change": None,
                "significant": None,
            }
            continue

        delta = current_value - baseline_value
        percent_change = (delta / baseline_value * 100) if baseline_value != 0 else float("inf")
        significant = abs(percent_change) > threshold if baseline_value != 0 else False

        changes[key] = {
            "baseline": baseline_value,
            "current": current_value,
            "delta": delta,
            "percent_change": percent_change,
            "significant": significant,
        }

    return changes


def _compare_tags(
    baseline_tags: dict[str, dict[str, float]],
    current_tags: dict[str, dict[str, float]],
    metric_threshold: float,
    latency_threshold: float,
) -> dict[str, dict[str, dict[str, float]]]:
    """Compare metrics by tags."""
    changes = {}

    all_tags = set(baseline_tags.keys()) | set(current_tags.keys())

    for tag in all_tags:
        baseline_data = baseline_tags.get(tag, {})
        current_data = current_tags.get(tag, {})

        # Compare metrics
        metric_changes = _compare_metrics(baseline_data, current_data, metric_threshold)

        # Compare latency
        latency_changes = _compare_latency(baseline_data, current_data, latency_threshold)

        changes[tag] = {**metric_changes, **latency_changes}

    return changes


def _determine_summary(
    metric_changes: dict[str, dict[str, float]],
    latency_changes: dict[str, dict[str, float]],
    tag_changes: dict[str, dict[str, dict[str, float]]],
) -> str:
    """Determine overall summary (improved, regressed, neutral)."""
    regression_count = 0
    improvement_count = 0

    # Check metric changes
    for key, change in metric_changes.items():
        if change.get("significant"):
            if change.get("delta", 0) < 0 and key.startswith("success_rate"):
                # Lower success rate = regression
                regression_count += 1
            elif change.get("delta", 0) > 0 and key.startswith("success_rate"):
                # Higher success rate = improvement
                improvement_count += 1
            elif change.get("delta", 0) > 0 and "error" in key.lower():
                # Higher error rate = regression
                regression_count += 1
            elif change.get("delta", 0) < 0 and "error" in key.lower():
                # Lower error rate = improvement
                improvement_count += 1

    # Check latency changes
    for key, change in latency_changes.items():
        if change.get("significant"):
            if change.get("delta", 0) > 0:
                # Higher latency = regression
                regression_count += 1
            else:
                # Lower latency = improvement
                improvement_count += 1

    # Check tag changes
    for tag, changes in tag_changes.items():
        for key, change in changes.items():
            if change.get("significant"):
                if change.get("delta", 0) < 0 and key.startswith("success_rate"):
                    regression_count += 1
                elif change.get("delta", 0) > 0 and key.startswith("success_rate"):
                    improvement_count += 1

    if regression_count > improvement_count:
        return "regressed"
    elif improvement_count > regression_count:
        return "improved"
    else:
        return "neutral"


def format_regression_report(report: RegressionReport) -> str:
    """Format a regression report as human-readable text.

    Args:
        report: RegressionReport to format

    Returns:
        Formatted text report
    """
    lines = [
        f"# Regression Report",
        f"",
        f"Component: {report.current_summary.component}",
        f"Baseline: {report.baseline_summary.timestamp}",
        f"Current: {report.current_summary.timestamp}",
        f"Summary: {report.summary.upper()}",
        f"",
        f"## Metric Changes",
    ]

    for metric, change in report.metric_changes.items():
        baseline = change.get("baseline")
        current = change.get("current")
        delta = change.get("delta")
        percent = change.get("percent_change")
        significant = change.get("significant")

        if current is None:
            lines.append(f"- {metric}: {baseline:.4f} -> MISSING")
        else:
            status = "⚠️ SIGNIFICANT" if significant else "✓ OK"
            lines.append(f"- {metric}: {baseline:.4f} -> {current:.4f} (Δ={delta:+.4f}, {percent:+.1f}%) {status}")

    lines.append("")
    lines.append("## Latency Changes")

    for stat, change in report.latency_changes.items():
        baseline = change.get("baseline")
        current = change.get("current")
        delta = change.get("delta")
        percent = change.get("percent_change")
        significant = change.get("significant")

        if current is None:
            lines.append(f"- {stat}: {baseline:.4f}s -> MISSING")
        else:
            status = "⚠️ SIGNIFICANT" if significant else "✓ OK"
            lines.append(f"- {stat}: {baseline:.4f}s -> {current:.4f}s (Δ={delta:+.4f}s, {percent:+.1f}%) {status}")

    lines.append("")
    lines.append("## Tag-Based Changes")

    for tag, changes in report.tag_changes.items():
        lines.append(f"### Tag: {tag}")
        for metric, change in changes.items():
            if not change.get("significant"):
                continue
            baseline = change.get("baseline")
            current = change.get("current")
            delta = change.get("delta")
            percent = change.get("percent_change")
            lines.append(f"- {metric}: {baseline:.4f} -> {current:.4f} (Δ={delta:+.4f}, {percent:+.1f}%)")

    return "\n".join(lines)
