"""
Run a full evaluation campaign from a YAML configuration.

This script uses CampaignRunner to execute multiple experiments defined in a campaign YAML,
automatically comparing results between experiments.

Usage:
    PYTHONPATH=. python scripts/evaluation/run_campaign.py

The campaign config defaults to configs/evaluation/campaign.yaml.
Use --campaign-config to point at a different campaign YAML.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from package.evaluation.campaign import CampaignConfig, CampaignRunner

# Default campaign config path (anchored to repo root, not CWD)
DEFAULT_CAMPAIGN_CONFIG = str(ROOT / "configs" / "evaluation" / "campaign.yaml")


def get_git_sha() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run a full evaluation campaign from YAML configuration"
    )
    ap.add_argument(
        "--campaign-config",
        type=str,
        default=DEFAULT_CAMPAIGN_CONFIG,
        help=f"Path to campaign YAML configuration file (default: {DEFAULT_CAMPAIGN_CONFIG})",
    )
    ap.add_argument(
        "--git-sha",
        type=str,
        default="",
        help="Git commit SHA for reproducibility (auto-detected if not provided)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without actually executing",
    )
    args = ap.parse_args()

    # Load campaign configuration
    campaign_path = Path(args.campaign_config)
    if not campaign_path.exists():
        raise SystemExit(f"Campaign config not found: {campaign_path}")

    campaign = CampaignConfig.from_yaml(campaign_path)

    # Expand parameter grid to get actual experiments
    experiments = campaign.expand_parameter_grid()

    # Get git SHA if not provided
    git_sha = args.git_sha or get_git_sha()

    print(f"Campaign ID: {campaign.campaign_id}")
    print(f"Description: {campaign.description}")
    print(f"Output directory: {campaign.output_dir}")
    print(f"Total experiments: {len(experiments)}")
    print(f"Comparison pairs: {len(campaign.comparison_pairs)}")
    print(f"Git SHA: {git_sha}")

    if args.dry_run:
        print("\n=== DRY RUN - Would execute the following ===")
        for exp in experiments:
            print(f"  - {exp.name}: {exp.description}")
            print(f"    Repetitions: {exp.repetition_count}")
            print(f"    Agents: {exp.agent_config.get('agents', 'default')}")
            print(f"    Inference mode: {exp.agent_config.get('inference_mode', 'default')}")
            print(f"    Reflect rounds: {exp.agent_config.get('reflect_rounds', 0)}")
        print("\n=== DRY RUN COMPLETE ===")
        return

    # Run the campaign
    print("\n=== Starting Campaign Execution ===")
    runner = CampaignRunner(campaign, git_sha=git_sha)
    result = runner.run_campaign()

    # Print summary
    print("\n=== Campaign Summary ===")
    print(f"Total runs: {result.summary['total_runs']}")
    print(f"Successful: {result.summary['successful_runs']}")
    print(f"Failed: {result.summary['failed_runs']}")
    print(f"Success rate: {result.summary['success_rate']:.2%}")
    print(f"Average duration: {result.summary['average_duration_seconds']:.2f}s")

    print("\n=== Experiment Statistics ===")
    for exp_name, stats in result.summary["experiment_stats"].items():
        print(f"  {exp_name}:")
        print(f"    Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")

    print("\n=== Comparisons ===")
    for comp_name, comp_result in result.comparisons.items():
        print(f"  {comp_name}:")
        if comp_result.get("status") == "success":
            print(f"    Experiment A: {comp_result['experiment_a']}")
            print(f"    Experiment B: {comp_result['experiment_b']}")
            print(f"    Runs A: {comp_result['runs_a']}, Runs B: {comp_result['runs_b']}")
            for metric, delta in comp_result["deltas"].items():
                print(f"      {metric}: {delta['a']:.4f} -> {delta['b']:.4f} (delta: {delta['delta']:+.4f})")
        else:
            print(f"    Status: {comp_result.get('status')}")
            print(f"    Reason: {comp_result.get('reason')}")

    print(f"\n=== Results saved to {campaign.output_dir}/campaign_result.json ===")


if __name__ == "__main__":
    main()
