"""CLI for linking component results with end-to-end results."""

from __future__ import annotations

import argparse
from pathlib import Path

from package.evaluation.component.create_traceback_tool import create_traceback_tool
from package.evaluation.component.link_component_to_e2e import link_component_to_e2e


def main() -> None:
    """Main entry point for demo."""
    parser = argparse.ArgumentParser(description="Link component results with end-to-end results")
    parser.add_argument("--component-dir", type=str, default=None, help="Directory with component results (default: get_data_paths().output_dir('component_benchmarks'))")
    parser.add_argument("--e2e-file", type=str, help="Path to end-to-end results JSON")
    args = parser.parse_args()

    from package.config import get_data_paths

    output_dir = get_data_paths().output_dir("component_benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    component_dir = Path(args.component_dir) if args.component_dir else output_dir

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
