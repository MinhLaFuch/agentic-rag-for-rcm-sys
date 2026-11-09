"""Example complete campaign report generation.

SYNTHETIC DEMO ONLY — `example_results`/`example_comparison` are hardcoded
fabricated numbers, not real evaluation output. This script is not wired into
any pipeline; it exists to demonstrate the reporting API surface. Output goes
to data_paths.outputs.example_report and must not be cited as results.
"""

from pathlib import Path
from package.evaluation.reporting import (
    generate_markdown_report,
    generate_csv_export,
    generate_failure_report,
    generate_comparison_report,
    generate_all_charts,
)

# Example evaluation results
example_results = {
    "summary": {
        "total_requests": 100,
        "task_success_rate": 0.85,
        "grounded_answer_rate": 0.90,
        "constraint_satisfaction": 0.82,
        "avg_latency": 1.5,
        "p95_latency": 2.8,
    },
    "layers": [
        {
            "layer": "L1",
            "metrics": {
                "precision_at_10": {"mean": 0.75, "std": 0.05, "min": 0.65, "max": 0.85},
                "recall_at_10": {"mean": 0.80, "std": 0.06, "min": 0.70, "max": 0.90},
            },
        },
        {
            "layer": "L2",
            "metrics": {
                "task_success": {"mean": 0.85, "std": 0.04, "min": 0.78, "max": 0.92},
                "constraint_ok": {"mean": 0.82, "std": 0.07, "min": 0.70, "max": 0.94},
            },
        },
    ],
    "request_kinds": [
        {
            "kind": "similar",
            "metrics": {
                "task_success": {"mean": 0.90, "std": 0.03},
                "grounded_answer": {"mean": 0.92, "std": 0.04},
            },
        },
        {
            "kind": "personalized",
            "metrics": {
                "task_success": {"mean": 0.88, "std": 0.05},
                "grounded_answer": {"mean": 0.91, "std": 0.05},
            },
        },
    ],
    "components": {
        "planner": {"success_rate": 0.95, "latency": {"mean": 0.5}},
        "executor": {"success_rate": 0.92, "latency": {"mean": 0.8}},
        "memory": {"success_rate": 0.98, "latency": {"mean": 0.3}},
    },
    "multi_turn": {
        "turn_success_rate": 0.93,
        "conversation_success_rate": 0.88,
        "context_retention": 0.95,
    },
    "metric_values": {
        "task_success": [0.82, 0.85, 0.88, 0.84, 0.86, 0.89, 0.83, 0.87, 0.85, 0.88],
        "grounded_answer": [0.88, 0.91, 0.89, 0.90, 0.92, 0.87, 0.90, 0.93, 0.89, 0.91],
    },
    "failures": [
        {"case_id": "req_001", "failure_stage": "L2", "error": "Constraint violation", "trace_file": "traces/req_001.json"},
        {"case_id": "req_005", "failure_stage": "L3", "error": "Retrieval timeout", "trace_file": "traces/req_005.json"},
        {"case_id": "req_012", "failure_stage": "L4", "error": "Tool execution error", "trace_file": "traces/req_012.json"},
    ],
}

# Example comparison
example_comparison = {
    "experiment_a": "baseline",
    "experiment_b": "improved",
    "deltas": {
        "task_success": {"a": 0.82, "b": 0.88, "delta": 0.06, "relative_delta": 0.073},
        "grounded_answer": {"a": 0.88, "b": 0.91, "delta": 0.03, "relative_delta": 0.034},
    },
    "significance": {
        "test_type": "wilcoxon_paired",
        "p_value": 0.03,
        "significant": True,
        "alpha": 0.05,
        "mean_difference": 0.06,
    },
}

# Generate reports
from package.config import get_data_paths

output_dir = get_data_paths().output_dir("example_report")
output_dir.mkdir(parents=True, exist_ok=True)

# Markdown report
md_path = output_dir / "evaluation_report.md"
generate_markdown_report(example_results, md_path, include_confidence_intervals=True)
print(f"Markdown report: {md_path}")

# CSV export
csv_path = output_dir / "evaluation_data.csv"
generate_csv_export(example_results, csv_path)
print(f"CSV export: {csv_path}")

# Failure report
failure_path = output_dir / "failure_report.md"
generate_failure_report(example_results["failures"], failure_path)
print(f"Failure report: {failure_path}")

# Comparison report
comp_path = output_dir / "comparison_report.md"
generate_comparison_report(example_comparison, comp_path)
print(f"Comparison report: {comp_path}")

# Charts
charts = generate_all_charts(example_results, output_dir / "charts")
print(f"Charts generated: {len(charts)}")
for name, path in charts.items():
    print(f"  - {name}: {path}")

print("\nExample complete campaign report generated successfully!")
