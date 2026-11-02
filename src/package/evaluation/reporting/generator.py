"""Report generation for evaluation results.

Generates Markdown reports, CSV exports, and provides
failure diagnosis with trace references.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List
from datetime import datetime, timezone
import csv

from package.evaluation.statistics import (
    bootstrap_confidence_interval,
    paired_bootstrap_difference,
    aggregate_metrics,
    compute_percentiles,
)


def generate_markdown_report(
    results: dict[str, Any],
    output_path: Path,
    include_confidence_intervals: bool = True,
    confidence_level: float = 0.95,
) -> None:
    """Generate comprehensive Markdown report from evaluation results.

    Args:
        results: Dictionary containing evaluation results
        output_path: Path to save the report
        include_confidence_intervals: Whether to include CI calculations
        confidence_level: Confidence level for CIs
    """
    lines = [
        "# Agent Evaluation Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    # Executive Summary
    if "summary" in results:
        lines.append("## Executive Summary")
        lines.append("")
        for key, value in results["summary"].items():
            if isinstance(value, float):
                lines.append(f"- **{key}**: {value:.4f}")
            else:
                lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Layer Analysis
    if "layers" in results:
        lines.append("## Layer Analysis")
        lines.append("")
        lines.append("| Layer | Metric | Mean | Std | Min | Max |")
        lines.append("|-------|--------|------|-----|-----|-----|")
        for layer_data in results["layers"]:
            layer = layer_data.get("layer", "unknown")
            for metric, stats in layer_data.get("metrics", {}).items():
                lines.append(
                    f"| {layer} | {metric} | {stats.get('mean', 0):.4f} | {stats.get('std', 0):.4f} | {stats.get('min', 0):.4f} | {stats.get('max', 0):.4f} |"
                )
        lines.append("")

    # Request Kind Analysis
    if "request_kinds" in results:
        lines.append("## Request Kind Analysis")
        lines.append("")
        lines.append("| Request Kind | Metric | Mean | Std |")
        lines.append("|--------------|--------|------|-----|")
        for kind_data in results["request_kinds"]:
            kind = kind_data.get("kind", "unknown")
            for metric, stats in kind_data.get("metrics", {}).items():
                lines.append(
                    f"| {kind} | {metric} | {stats.get('mean', 0):.4f} | {stats.get('std', 0):.4f} |"
                )
        lines.append("")

    # Component Analysis
    if "components" in results:
        lines.append("## Component Analysis")
        lines.append("")
        lines.append("| Component | Success Rate | Mean Latency (s) |")
        lines.append("|-----------|--------------|------------------|")
        for comp_name, comp_data in results["components"].items():
            success_rate = comp_data.get("success_rate", 0)
            latency = comp_data.get("latency", {}).get("mean", 0)
            lines.append(f"| {comp_name} | {success_rate:.2%} | {latency:.4f} |")
        lines.append("")

    # Multi-turn Analysis
    if "multi_turn" in results:
        lines.append("## Multi-turn Analysis")
        lines.append("")
        mt_data = results["multi_turn"]
        lines.append(f"- **Turn Success Rate**: {mt_data.get('turn_success_rate', 0):.2%}")
        lines.append(f"- **Conversation Success Rate**: {mt_data.get('conversation_success_rate', 0):.2%}")
        lines.append(f"- **Context Retention**: {mt_data.get('context_retention', 0):.4f}")
        lines.append("")

    # Confidence Intervals
    if include_confidence_intervals and "metric_values" in results:
        lines.append("## Confidence Intervals")
        lines.append("")
        lines.append(f"Confidence Level: {confidence_level * 100}%")
        lines.append("")
        lines.append("| Metric | Mean | Lower CI | Upper CI |")
        lines.append("|--------|------|----------|----------|")
        for metric, values in results["metric_values"].items():
            mean, lower, upper = bootstrap_confidence_interval(
                values, confidence_level=confidence_level
            )
            lines.append(f"| {metric} | {mean:.4f} | {lower:.4f} | {upper:.4f} |")
        lines.append("")

    # Failure Analysis
    if "failures" in results and results["failures"]:
        lines.append("## Failure Analysis")
        lines.append("")
        lines.append(f"**Total Failures**: {len(results['failures'])}")
        lines.append("")
        for failure in results["failures"][:10]:  # Show first 10
            lines.append(f"- **{failure.get('case_id', 'unknown')}**: {failure.get('error', 'Unknown error')}")
        if len(results["failures"]) > 10:
            lines.append(f"- ... and {len(results['failures']) - 10} more failures")
        lines.append("")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def generate_csv_export(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate CSV export of evaluation results.

    Args:
        results: Dictionary containing evaluation results
        output_path: Path to save the CSV
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write summary section
        if "summary" in results:
            writer.writerow(["Summary"])
            for key, value in results["summary"].items():
                writer.writerow([key, value])
            writer.writerow([])

        # Write layer metrics
        if "layers" in results:
            writer.writerow(["Layer Metrics"])
            writer.writerow(["Layer", "Metric", "Mean", "Std", "Min", "Max"])
            for layer_data in results["layers"]:
                layer = layer_data.get("layer", "unknown")
                for metric, stats in layer_data.get("metrics", {}).items():
                    writer.writerow([
                        layer,
                        metric,
                        stats.get("mean", 0),
                        stats.get("std", 0),
                        stats.get("min", 0),
                        stats.get("max", 0),
                    ])
            writer.writerow([])

        # Write request kind metrics
        if "request_kinds" in results:
            writer.writerow(["Request Kind Metrics"])
            writer.writerow(["Request Kind", "Metric", "Mean", "Std"])
            for kind_data in results["request_kinds"]:
                kind = kind_data.get("kind", "unknown")
                for metric, stats in kind_data.get("metrics", {}).items():
                    writer.writerow([
                        kind,
                        metric,
                        stats.get("mean", 0),
                        stats.get("std", 0),
                    ])
            writer.writerow([])


def generate_failure_report(
    failures: List[dict[str, Any]],
    output_path: Path,
) -> None:
    """Generate focused failure report with trace references.

    Args:
        failures: List of failure records
        output_path: Path to save the report
    """
    lines = [
        "# Failure Analysis Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"**Total Failures**: {len(failures)}",
        "",
        "## Failures by Stage",
        "",
    ]

    # Group failures by stage
    by_stage: dict[str, List[dict]] = {}
    for failure in failures:
        stage = failure.get("failure_stage", "unknown")
        if stage not in by_stage:
            by_stage[stage] = []
        by_stage[stage].append(failure)

    for stage, stage_failures in sorted(by_stage.items()):
        lines.append(f"### {stage}")
        lines.append(f"**Count**: {len(stage_failures)}")
        lines.append("")

        for failure in stage_failures[:5]:  # Show first 5 per stage
            case_id = failure.get("case_id", "unknown")
            error = failure.get("error", "Unknown error")
            trace_ref = failure.get("trace_file", "")

            lines.append(f"**{case_id}**")
            lines.append(f"- Error: {error}")
            if trace_ref:
                lines.append(f"- Trace: `{trace_ref}`")
            lines.append("")

        if len(stage_failures) > 5:
            lines.append(f"... and {len(stage_failures) - 5} more failures in this stage")
            lines.append("")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def generate_comparison_report(
    comparison: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate comparison report between two experiments.

    Args:
        comparison: Comparison results
        output_path: Path to save the report
    """
    lines = [
        "# Experiment Comparison Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"**Experiment A**: {comparison.get('experiment_a', 'N/A')}",
        f"**Experiment B**: {comparison.get('experiment_b', 'N/A')}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | A | B | Delta | Relative Delta |",
        "|--------|---|---|-------|----------------|",
    ]

    for metric, delta_data in comparison.get("deltas", {}).items():
        val_a = delta_data.get("a", 0)
        val_b = delta_data.get("b", 0)
        delta = delta_data.get("delta", 0)
        rel_delta = delta_data.get("relative_delta", 0)

        lines.append(
            f"| {metric} | {val_a:.4f} | {val_b:.4f} | {delta:.4f} | {rel_delta:.2%} |"
        )

    # Statistical significance
    if "significance" in comparison:
        sig = comparison["significance"]
        lines.append("")
        lines.append("## Statistical Significance")
        lines.append("")
        lines.append(f"- **Test Type**: {sig.get('test_type', 'N/A')}")
        lines.append(f"- **P-value**: {sig.get('p_value', 'N/A')}")
        lines.append(f"- **Significant**: {'Yes' if sig.get('significant', False) else 'No'}")
        lines.append(f"- **Alpha**: {sig.get('alpha', 0.05)}")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
