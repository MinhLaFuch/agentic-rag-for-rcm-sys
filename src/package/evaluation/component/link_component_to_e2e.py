"""Link component benchmark results with end-to-end trajectory results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from package.config import get_data_paths


def link_component_to_e2e(
    component_results: dict[str, str],
    e2e_results: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Link component benchmark results with end-to-end trajectory results.

    Args:
        component_results: Dict mapping component name to result JSON file path
        e2e_results: End-to-end trajectory results (from layer1-layer5)
        output_path: Path to save linked analysis
    """
    # Load component results
    component_data = {}
    for component, result_file in component_results.items():
        if result_file and Path(result_file).exists():
            with open(result_file, "r", encoding="utf-8") as f:
                component_data[component] = json.load(f)

    # Calculate component correlation with e2e
    analysis = {
        "component_scores": {},
        "e2e_scores": e2e_results.get("metrics", {}),
        "correlation": {},
        "analysis": {},
    }

    # Extract mean scores per component
    for component, data in component_data.items():
        if "per_case_results" in data:
            all_metrics = {}
            for case in data["per_case_results"]:
                for metric, value in case.get("metrics", {}).items():
                    if metric not in all_metrics:
                        all_metrics[metric] = []
                    all_metrics[metric].append(value)

            mean_metrics = {}
            for metric, values in all_metrics.items():
                mean_metrics[metric] = sum(values) / len(values) if values else 0.0

            analysis["component_scores"][component] = mean_metrics

    # Simple correlation analysis (placeholder)
    # In real usage, this would use statistical correlation
    analysis["correlation"] = {
        "note": "Correlation analysis requires matching request IDs between component and e2e results",
        "method": "Pearson correlation on matched request IDs",
    }

    analysis["analysis"] = {
        "summary": "Component scores extracted. Full correlation analysis requires matching request IDs.",
        "recommendation": "Ensure component and e2e benchmarks use same request IDs for correlation.",
    }

    # Save analysis
    output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"Link analysis saved to: {output_path}")