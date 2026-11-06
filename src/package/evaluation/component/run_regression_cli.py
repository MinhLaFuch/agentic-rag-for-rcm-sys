"""CLI entrypoint for regression comparison between two runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from ._regression import compare_benchmarks, format_regression_report


def run_regression_cli() -> None:
    """CLI entrypoint for regression comparison between two runs."""
    parser = argparse.ArgumentParser(
        description="Compare two benchmark runs for regression analysis",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Path to baseline benchmark results JSON",
    )
    parser.add_argument(
        "--candidate",
        type=str,
        required=True,
        help="Path to candidate benchmark results JSON",
    )

    args = parser.parse_args()

    # Load baseline and candidate results
    with open(args.baseline, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    with open(args.candidate, "r", encoding="utf-8") as f:
        candidate = json.load(f)

    # Run comparison
    report = compare_benchmarks([baseline, candidate])

    # Save JSON report under the configured component_benchmarks output dir
    from package.config import get_data_paths

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = get_data_paths().output_dir("component_benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"regression_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Regression report saved to: {output_path}")

    print("\n" + format_regression_report(report))