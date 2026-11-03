"""CLI entrypoint for regression comparison between two runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save comparison JSON (default: regression_<timestamp>.json)",
    )
    parser.add_argument(
        "--text-report",
        type=str,
        default=None,
        help="Path to save text report (optional)",
    )

    args = parser.parse_args()

    # Load baseline and candidate results
    with open(args.baseline, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    with open(args.candidate, "r", encoding="utf-8") as f:
        candidate = json.load(f)

    # Run comparison
    report = compare_benchmarks([baseline, candidate])

    # Save JSON report
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"regression_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Regression report saved to: {output_path}")

    # Save text report if requested
    if args.text_report:
        text_path = Path(args.text_report)
        text_report = format_regression_report(report)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_report)
        print(f"Text report saved to: {text_path}")
    else:
        # Print to console
        print("\n" + format_regression_report(report))