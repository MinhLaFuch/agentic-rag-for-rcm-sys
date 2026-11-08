"""CLI for linking component results with end-to-end results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from package.evaluation.component.create_traceback_tool import create_traceback_tool
from package.evaluation.component.link_component_to_e2e import link_component_to_e2e
from scripts._mock_helper import add_mock_argument


def main() -> None:
    """Main entry point for demo."""
    parser = argparse.ArgumentParser(description="Link component results with end-to-end results")
    parser.add_argument("--component-dir", type=str, default=None, help="Directory with component results (default: get_data_paths().output_dir('component_benchmarks'))")
    parser.add_argument("--e2e-file", type=str, help="Path to end-to-end results JSON")
    add_mock_argument(parser)
    args = parser.parse_args()

    from package.config import get_data_paths

    output_dir = get_data_paths().output_dir("component_benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    component_dir = Path(args.component_dir) if args.component_dir else output_dir

    if args.mock:
        print("⚠️  MOCK MODE - Using hardcoded mock data")
        # Mock component results
        component_results = {
            "memory": "memory_benchmark_20261027_084241.json",
            "planner": "planner_benchmark_20261027_084303.json",
            "executor": "executor_benchmark_20261027_084305.json",
            "grounding": "grounding_benchmark_20261027_084306.json",
        }

        # Mock e2e results
        e2e_results = {
            "metrics": {
                "overall_success_rate": 0.85,
                "user_satisfaction": 0.78,
            }
        }
    else:
        print("✓ REAL MODE - Loading from files")
        # Load component results from directory
        component_results = {}
        for result_file in component_dir.glob("*_benchmark_*.json"):
            component = result_file.stem.split("_benchmark_")[0]
            component_results[component] = result_file.name

        # Load e2e results from file
        if args.e2e_file:
            e2e_path = Path(args.e2e_file)
            if not e2e_path.exists():
                raise FileNotFoundError(f"E2E results file not found: {e2e_path}")
            with open(e2e_path) as f:
                e2e_results = json.load(f)
        else:
            raise ValueError("--e2e-file required in real mode")

    # Link analysis
    link_path = output_dir / "component_e2e_link.json"
    link_component_to_e2e(component_results, e2e_results, link_path)

    # Traceback (mock failures in mock mode, load from file in real mode)
    if args.mock:
        e2e_failures = [
            {"request_id": "req_001", "error_type": "planner_error"},
            {"request_id": "req_002", "error_type": "executor_timeout"},
        ]
    else:
        # In real mode, would load failures from e2e results
        e2e_failures = e2e_results.get("failures", [])

    traceback_path = output_dir / "traceback_analysis.json"
    create_traceback_tool(component_results, e2e_failures, traceback_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
