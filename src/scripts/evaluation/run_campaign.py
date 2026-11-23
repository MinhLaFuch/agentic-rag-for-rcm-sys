"""
Run a full evaluation campaign from a YAML configuration.

This script uses CampaignRunner to execute multiple experiments defined in a campaign YAML,
automatically comparing results between experiments.

Usage:
    PYTHONPATH=. python scripts/evaluation/run_campaign.py

The campaign config defaults to configs/eval/campaign.yaml.
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
DEFAULT_CAMPAIGN_CONFIG = str(ROOT / "configs" / "eval" / "campaign.yaml")


def _auto_next_campaign_version(campaign: CampaignConfig) -> CampaignConfig:
    """Bump campaign_id/output_dir to one past the highest existing campaign_NNN.

    Scans sibling dirs of the configured output_dir (under experiments_dir for
    relative paths) for ``campaign_<digits>`` names AND the shared trajectory
    log dir for ``campaign_<digits>_*_trajectories.jsonl`` files — trajectory
    logs outlive campaign output dirs, so a deleted campaign's id must still
    count as used or its filenames collide on the next auto-versioned run.
    Never downgrades: the YAML's own number is the floor. Configs without a
    digit group are returned unchanged.
    """
    import re

    from package.config import get_data_paths

    m = re.search(r"\d+", campaign.campaign_id)
    if m is None:
        return campaign
    yaml_num = int(m.group(0))

    data_paths = get_data_paths()
    out = Path(campaign.output_dir)
    root = out.parent if out.is_absolute() else data_paths.experiments_dir / out.parent
    existing = [
        int(mm.group(1))
        for p in root.glob("campaign_*")
        if p.is_dir() and (mm := re.fullmatch(r"campaign_(\d+).*", p.name))
    ]
    if data_paths.log_dir.is_dir():
        existing += [
            int(mm.group(1))
            for p in data_paths.log_dir.glob("campaign_*_trajectories.jsonl")
            if (mm := re.fullmatch(r"campaign_(\d+)_.*", p.name))
        ]
    target = max(existing + [yaml_num - 1]) + 1
    if target <= yaml_num:
        return campaign
    bumped = campaign.next_version(times=target - yaml_num)
    print(
        f"auto-version: highest existing campaign_NNN={max(existing) if existing else 'none'} "
        f"-> {bumped.campaign_id} ({bumped.output_dir})"
    )
    return bumped


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
    ap.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated experiment selectors (e.g. 7,8,11,12 or exp_7,exp_8); "
             "runs ONLY those experiments and merges into the existing campaign_result.json",
    )
    args = ap.parse_args()

    only = None
    if args.only:
        only = [t.strip() for t in args.only.split(",") if t.strip()]
        if not only:
            raise SystemExit("--only given but empty")

    # Load campaign configuration
    campaign_path = Path(args.campaign_config)
    if not campaign_path.exists():
        raise SystemExit(f"Campaign config not found: {campaign_path}")

    campaign = CampaignConfig.from_yaml(campaign_path)

    # Full runs auto-version like run_agent_eval's exp_NNN: scan existing
    # campaign dirs and take max+1. --only reruns must keep the existing
    # campaign identity so results merge into the right output_dir.
    if only is None:
        campaign = _auto_next_campaign_version(campaign)

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
        # Resolve --only against the expanded grid so IDs are shown, not renumbered
        if only is not None:
            try:
                selected, skipped = CampaignRunner._select_experiments(experiments, only)
            except ValueError as exc:
                raise SystemExit(str(exc))
        else:
            selected, skipped = experiments, []
        print("\n=== DRY RUN - Would execute the following ===")
        for exp in selected:
            print(f"  - {exp.name}: {exp.description}")
            print(f"    Repetitions: {exp.repetition_count}")
            print(f"    Agents: {exp.agent_config.get('agents', 'default')}")
            print(f"    Inference mode: {exp.agent_config.get('inference_mode', 'default')}")
            print(f"    Reflect rounds: {exp.agent_config.get('reflect_rounds', 0)}")
        for name in skipped:
            print(f"  - SKIPPED {name}")
        print("\n=== DRY RUN COMPLETE ===")
        return

    # Run the campaign
    print("\n=== Starting Campaign Execution ===")
    runner = CampaignRunner(campaign, git_sha=git_sha)
    try:
        result = runner.run_campaign(only=only)
    except ValueError as exc:
        raise SystemExit(str(exc))

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
