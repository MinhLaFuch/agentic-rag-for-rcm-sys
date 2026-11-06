"""Report generator for multi-turn conversation evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._schema import ConversationSummary, ConversationResult


def generate_markdown_report(
    summary: ConversationSummary,
    results: list[ConversationResult] | None = None,
    output_path: Path | None = None,
) -> str:
    """Generate a Markdown report for multi-turn conversation evaluation.

    Args:
        summary: ConversationSummary with aggregated metrics
        results: Optional list of individual ConversationResult for detailed reporting
        output_path: Optional path to save the report

    Returns:
        Markdown report as string
    """
    lines = [
        "# Multi-Turn Conversation Evaluation Report",
        "",
        f"**Generated**: {summary.timestamp}",
        f"**Multi-Turn Version**: {summary.multi_turn_version}",
        f"**Git SHA**: {summary.git_sha or 'N/A'}",
        "",
        "## Executive Summary",
        "",
        f"- **Total Conversations**: {summary.total_conversations}",
        f"- **Turn Success Rate**: {summary.turn_success_rate:.2%}",
        f"- **Conversation Success Rate**: {summary.conversation_success_rate:.2%}",
        f"- **Mean Latency**: {summary.latency['mean']:.4f}s",
        f"- **P95 Latency**: {summary.latency.get('p95', 'N/A')}",
        "",
        "## Conversation-Level Metrics",
        "",
    ]

    # Aggregated metrics
    if summary.metrics:
        lines.append("| Metric | Mean | Std | Min | Max |")
        lines.append("|--------|------|-----|-----|-----|")
        for key in sorted(summary.metrics.keys()):
            if key.endswith("_mean"):
                base_key = key[:-5]
                mean_val = summary.metrics[key]
                std_val = summary.metrics.get(f"{base_key}_std", 0.0)
                min_val = summary.metrics.get(f"{base_key}_min", 0.0)
                max_val = summary.metrics.get(f"{base_key}_max", 0.0)
                lines.append(f"| {base_key} | {mean_val:.4f} | {std_val:.4f} | {min_val:.4f} | {max_val:.4f} |")
        lines.append("")

    # Context retention metrics
    if summary.context_retention_metrics:
        lines.append("## Context Retention and Update Metrics")
        lines.append("")
        for key, value in summary.context_retention_metrics.items():
            lines.append(f"- **{key}**: {value:.4f}")
        lines.append("")

    # Failure distribution
    if summary.failure_distribution:
        lines.append("## Failure Distribution")
        lines.append("")
        for stage, count in sorted(summary.failure_distribution.items()):
            lines.append(f"- **{stage}**: {count} failures")
        lines.append("")

    # Detailed conversation results
    if results:
        lines.append("## Detailed Conversation Results")
        lines.append("")

        for result in results:
            lines.append(f"### Conversation: {result.conversation_id}")
            lines.append("")
            lines.append(f"- **Success**: {'✅ Yes' if result.conversation_success else '❌ No'}")
            lines.append(f"- **Turns**: {len(result.turn_results)}")
            lines.append(f"- **Latency**: {result.latency_seconds:.4f}s")
            if result.failure_stage:
                lines.append(f"- **Failure Stage**: {result.failure_stage}")
            if result.error:
                lines.append(f"- **Error**: {result.error}")
            lines.append("")

            # Turn-level breakdown
            lines.append("**Turn Results:**")
            lines.append("")
            lines.append("| Turn | Success | Item Match | Exclusion Compliance | Latency (s) |")
            lines.append("|------|---------|-----------|---------------------|------------|")
            for turn_result in result.turn_results:
                item_match = turn_result.metrics.get("item_match_rate", 0.0)
                exclusion_comp = turn_result.metrics.get("exclusion_compliance", 0.0)
                lines.append(
                    f"| {turn_result.turn_id} | {'✅' if turn_result.success else '❌'} | {item_match:.2%} | {exclusion_comp:.2%} | {turn_result.latency_seconds:.4f} |"
                )
            lines.append("")

            # Conversation-level metrics
            if result.metrics:
                lines.append("**Conversation Metrics:**")
                lines.append("")
                for key, value in sorted(result.metrics.items()):
                    lines.append(f"- {key}: {value:.4f}")
                lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    return report


def generate_csv_export(
    results: list[ConversationResult],
    output_path: Path,
) -> None:
    """Generate a CSV export of turn-level results.

    Args:
        results: List of ConversationResult
        output_path: Path to save the CSV
    """
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "conversation_id",
            "turn_id",
            "position",
            "success",
            "error",
            "item_match_rate",
            "exclusion_compliance",
            "reference_correctness",
            "latency_seconds",
            "conversation_success",
        ])

        # Rows
        for result in results:
            for turn_result in result.turn_results:
                writer.writerow([
                    result.conversation_id,
                    turn_result.turn_id,
                    result.turn_results.index(turn_result),
                    turn_result.success,
                    turn_result.error or "",
                    turn_result.metrics.get("item_match_rate", 0.0),
                    turn_result.metrics.get("exclusion_compliance", 0.0),
                    turn_result.metrics.get("reference_correctness", 0.0),
                    turn_result.latency_seconds,
                    result.conversation_success,
                ])


def generate_failure_report(
    results: list[ConversationResult],
    output_path: Path,
) -> None:
    """Generate a focused report on failed conversations.

    Args:
        results: List of ConversationResult
        output_path: Path to save the report
    """
    failures = [r for r in results if not r.conversation_success]

    lines = [
        "# Multi-Turn Conversation Failure Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"**Total Conversations**: {len(results)}",
        f"**Failed Conversations**: {len(failures)}",
        f"**Failure Rate**: {len(failures) / len(results):.2%}" if results else "**Failure Rate**: N/A",
        "",
        "## Failed Conversations",
        "",
    ]

    for result in failures:
        lines.append(f"### {result.conversation_id}")
        lines.append("")
        lines.append(f"- **Failure Stage**: {result.failure_stage}")
        lines.append(f"- **Error**: {result.error}")
        lines.append(f"- **Turns Completed**: {len(result.turn_results)}")
        lines.append("")

        # Show turn results
        lines.append("**Turn Results:**")
        lines.append("")
        for turn_result in result.turn_results:
            status = "✅ Success" if turn_result.success else f"❌ Failed: {turn_result.error}"
            lines.append(f"- {turn_result.turn_id}: {status}")
        lines.append("")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
