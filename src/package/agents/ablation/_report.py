"""Sinh báo cáo từ kết quả so sánh."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from package.agents.evaluation import ORACLE_KINDS


def render_markdown_report(
    results: dict[str, Any],
    contrast_name: str,
    agent_a: str,
    agent_b: str,
    group_a: str,
    group_b: str,
    limits: Any,
    k: int,
    missing_columns: list[str],
) -> str:
    """Render báo cáo markdown."""
    lines = []
    
    lines.append(f"# Ablation Comparison: {contrast_name}")
    lines.append("")
    lines.append(f"**Agent A:** {agent_a} (group: {group_a})")
    lines.append(f"**Agent B:** {agent_b} (group: {group_b})")
    lines.append(f"**Bootstrap resamples:** {limits.bootstrap_resamples}")
    lines.append(f"**Confidence level:** {limits.confidence * 100}%")
    lines.append(f"**k:** {k}")
    lines.append("")
    
    if "error" in results:
        lines.append(f"**ERROR:** {results['error']}")
        lines.append("")
        return "\n".join(lines)
    
    n_pairs = results.get("n_pairs", 0)
    lines.append(f"**Number of paired requests:** {n_pairs}")
    
    if n_pairs < limits.min_n_warn:
        lines.append(f"⚠️ **WARNING:** n = {n_pairs} < {limits.min_n_warn} (results may be unreliable)")
    lines.append("")
    
    # Variance info
    variance = results.get("variance", {})
    if "note" in variance:
        lines.append(f"**Variance:** {variance['note']}")
    else:
        if "group_a_runs" in variance:
            lines.append(f"**Group A runs:** {variance['group_a_runs']}")
        if "group_b_runs" in variance:
            lines.append(f"**Group B runs:** {variance['group_b_runs']}")
    lines.append("")
    
    # Results by kind (aggregated across segments)
    lines.append("## Results by Kind (aggregated across segments)")
    lines.append("")
    
    all_kinds = results.get("all_kinds", {})
    for kind in sorted(all_kinds.keys()):
        lines.append(f"### Kind: {kind}")
        
        if kind in ORACLE_KINDS:
            lines.append("⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)")
        lines.append("")
        
        kind_metrics = all_kinds[kind]
        
        # Table header
        lines.append("| Metric | Mean A | Mean B | Diff (B-A) | {0}% CI | n |".format(int(limits.confidence * 100)))
        lines.append("|--------|--------|--------|-----------|--------|---|")
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            if metric_formatted not in kind_metrics:
                continue
            
            metric_data = kind_metrics[metric_formatted]
            n = metric_data.get("n", 0)
            
            if n == 0:
                lines.append(f"| {metric_formatted} | — | — | — | — | 0 |")
                continue
            
            mean_a = metric_data.get("mean_a", 0)
            mean_b = metric_data.get("mean_b", 0)
            diff = metric_data.get("diff", 0)
            ci_lower = metric_data.get("ci_lower", 0)
            ci_upper = metric_data.get("ci_upper", 0)
            
            lines.append(f"| {metric_formatted} | {mean_a:.4f} | {mean_b:.4f} | {diff:+.4f} | [{ci_lower:.4f}, {ci_upper:.4f}] | {n} |")
            
            # McNemar for binary metrics
            if "mcnemar" in metric_data:
                mcnemar = metric_data["mcnemar"]
                lines.append(f"|  | McNemar: b={mcnemar['b']}, c={mcnemar['c']}, p={mcnemar['p']:.3f} | | | | |")
        
        lines.append("")
    
    # Results by kind × segment
    lines.append("## Results by Kind × Segment")
    lines.append("")
    
    for key in sorted(results.keys()):
        if key in ["all_kinds", "variance", "n_pairs", "error"]:
            continue
        
        kind, segment = key.split("/")
        lines.append(f"### {kind} / {segment}")
        
        if kind in ORACLE_KINDS:
            lines.append("⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)")
        lines.append("")
        
        kind_segment_metrics = results[key]
        
        lines.append("| Metric | Mean A | Mean B | Diff (B-A) | {0}% CI | n |".format(int(limits.confidence * 100)))
        lines.append("|--------|--------|--------|-----------|--------|---|")
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            if metric_formatted not in kind_segment_metrics:
                continue
            
            metric_data = kind_segment_metrics[metric_formatted]
            n = metric_data.get("n", 0)
            
            if n == 0:
                lines.append(f"| {metric_formatted} | — | — | — | — | 0 |")
                continue
            
            mean_a = metric_data.get("mean_a", 0)
            mean_b = metric_data.get("mean_b", 0)
            diff = metric_data.get("diff", 0)
            ci_lower = metric_data.get("ci_lower", 0)
            ci_upper = metric_data.get("ci_upper", 0)
            
            lines.append(f"| {metric_formatted} | {mean_a:.4f} | {mean_b:.4f} | {diff:+.4f} | [{ci_lower:.4f}, {ci_upper:.4f}] | {n} |")
            
            if "mcnemar" in metric_data:
                mcnemar = metric_data["mcnemar"]
                lines.append(f"|  | McNemar: b={mcnemar['b']}, c={mcnemar['c']}, p={mcnemar['p']:.3f} | | | | |")
        
        lines.append("")
    
    # Missing columns
    if missing_columns:
        lines.append("## Missing Columns")
        lines.append("")
        lines.append("The following columns were not found in the data and were skipped:")
        for col in missing_columns:
            lines.append(f"- {col}")
        lines.append("")
    
    return "\n".join(lines)


def write_csv(
    results: dict[str, Any],
    contrast_name: str,
    agent_a: str,
    agent_b: str,
    group_a: str,
    group_b: str,
    limits: Any,
    k: int,
    output_path: Path,
) -> None:
    """Write CSV file for plotting."""
    rows = []
    
    # Write aggregated by kind
    all_kinds = results.get("all_kinds", {})
    for kind in sorted(all_kinds.keys()):
        kind_metrics = all_kinds[kind]
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            if metric_formatted not in kind_metrics:
                continue
            
            metric_data = kind_metrics[metric_formatted]
            n = metric_data.get("n", 0)
            
            if n == 0:
                continue
            
            rows.append({
                "contrast": contrast_name,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "group_a": group_a,
                "group_b": group_b,
                "kind": kind,
                "segment": "all",
                "metric": metric_formatted,
                "mean_a": metric_data.get("mean_a"),
                "mean_b": metric_data.get("mean_b"),
                "diff": metric_data.get("diff"),
                "ci_lower": metric_data.get("ci_lower"),
                "ci_upper": metric_data.get("ci_upper"),
                "n": n,
                "is_oracle": kind in ORACLE_KINDS,
            })
    
    # Write by kind × segment
    for key in sorted(results.keys()):
        if key in ["all_kinds", "variance", "n_pairs", "error"]:
            continue
        
        kind, segment = key.split("/")
        kind_segment_metrics = results[key]
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            if metric_formatted not in kind_segment_metrics:
                continue
            
            metric_data = kind_segment_metrics[metric_formatted]
            n = metric_data.get("n", 0)
            
            if n == 0:
                continue
            
            rows.append({
                "contrast": contrast_name,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "group_a": group_a,
                "group_b": group_b,
                "kind": kind,
                "segment": segment,
                "metric": metric_formatted,
                "mean_a": metric_data.get("mean_a"),
                "mean_b": metric_data.get("mean_b"),
                "diff": metric_data.get("diff"),
                "ci_lower": metric_data.get("ci_lower"),
                "ci_upper": metric_data.get("ci_upper"),
                "n": n,
                "is_oracle": kind in ORACLE_KINDS,
            })
    
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "contrast", "agent_a", "agent_b", "group_a", "group_b",
            "kind", "segment", "metric",
            "mean_a", "mean_b", "diff", "ci_lower", "ci_upper", "n", "is_oracle",
        ])
        writer.writeheader()
        writer.writerows(rows)


def write_json(
    results: dict[str, Any],
    contrast_name: str,
    agent_a: str,
    agent_b: str,
    group_a: str,
    group_b: str,
    limits: Any,
    k: int,
    output_path: Path,
) -> None:
    """Write JSON file."""
    output = {
        "contrast": contrast_name,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "group_a": group_a,
        "group_b": group_b,
        "k": k,
        "bootstrap_resamples": limits.bootstrap_resamples,
        "confidence": limits.confidence,
        "results": results,
    }
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def write_disagreements(
    disagreements: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Write disagreements.jsonl."""
    with output_path.open("w", encoding="utf-8") as f:
        for d in disagreements:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
