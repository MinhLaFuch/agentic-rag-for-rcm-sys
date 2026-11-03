"""Create traceback tool to attribute trajectory failures to specific components."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_traceback_tool(
    component_results: dict[str, str],
    e2e_failures: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """
    Create traceback tool to attribute trajectory failures to specific components.

    Args:
        component_results: Dict mapping component name to result JSON file path
        e2e_failures: List of failed trajectory cases
        output_path: Path to save traceback analysis
    """
    # Load component results
    component_data = {}
    for component, result_file in component_results.items():
        if result_file and Path(result_file).exists():
            with open(result_file, "r", encoding="utf-8") as f:
                component_data[component] = json.load(f)

    # Analyze failures
    traceback = {
        "total_failures": len(e2e_failures),
        "attributions": [],
    }

    # Ensure all components have an entry in attributions summary
    for component in component_data:
        traceback[component] = 0

    for failure in e2e_failures:
        request_id = failure.get("request_id", "unknown")
        error_type = failure.get("error_type", "unknown")

        # Simple attribution logic (placeholder)
        # In real usage, this would use component scores for this specific request
        attribution = {
            "request_id": request_id,
            "error_type": error_type,
            "likely_component": "unknown",
            "reason": "Insufficient data for attribution",
            "confidence": 0.0,
        }

        # Simple heuristic based on error type
        if "planner" in error_type.lower():
            attribution["likely_component"] = "planner"
            attribution["confidence"] = 0.5
        elif "executor" in error_type.lower():
            attribution["likely_component"] = "executor"
            attribution["confidence"] = 0.5
        elif "memory" in error_type.lower():
            attribution["likely_component"] = "memory"
            attribution["confidence"] = 0.5

        traceback["attributions"].append(attribution)

    # Save traceback
    output_path.write_text(json.dumps(traceback, indent=2), encoding="utf-8")
    print(f"Traceback analysis saved to: {output_path}")