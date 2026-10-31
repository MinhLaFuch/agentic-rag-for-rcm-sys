"""Tool to link component scores with end-to-end trajectory scores."""

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
        "confidence": "low",  # Without matching request IDs, confidence is low
    }
    
    # For each failure, try to attribute to a component
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


def main():
    """Main entry point for demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Link component results with end-to-end results")
    parser.add_argument("--component-dir", type=str, default=None, help="Directory with component results (defaults to configured evaluation artifacts)")
    parser.add_argument("--e2e-file", type=str, help="Path to end-to-end results JSON")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (defaults to configured evaluation artifacts)")
    args = parser.parse_args()

    default_dir = get_data_paths().experiments_dir / "agent_eval" / "component_benchmarks"
    if args.output_dir is None:
        output_dir = default_dir
    else:
        output_dir = Path(args.output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)

    # Default component dir
    if args.component_dir is None:
        component_dir = default_dir
    else:
        component_dir = Path(args.component_dir)

    # Mock component results (in real usage, load from files)
    component_results = {
        "memory": "memory_benchmark_20261027_084241.json",
        "planner": "planner_benchmark_20261027_084303.json",
        "executor": "executor_benchmark_20261027_084305.json",
        "grounding": "grounding_benchmark_20261027_084306.json",
    }

    # Mock e2e results (in real usage, load from file)
    e2e_results = {
        "metrics": {
            "overall_success_rate": 0.85,
            "user_satisfaction": 0.78,
        }
    }

    # Link analysis
    link_path = output_dir / "component_e2e_link.json"
    link_component_to_e2e(component_results, e2e_results, link_path)

    # Traceback (mock failures)
    e2e_failures = [
        {"request_id": "req_001", "error_type": "planner_error"},
        {"request_id": "req_002", "error_type": "executor_timeout"},
    ]
    traceback_path = output_dir / "traceback_analysis.json"
    create_traceback_tool(component_results, e2e_failures, traceback_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
