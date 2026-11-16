"""
Re-run selected experiments of an existing campaign (--only subset merge).

Unlike run_campaign.py (which launches a whole campaign from a YAML path),
this script is the quick path for topping up a campaign: point it at a
campaign_id and the experiment selectors; it locates the matching
configs/eval/*.yaml, loads it, and runs CampaignRunner.run_campaign(only=...)
which merges results into that campaign's existing output_dir.

Usage:
    PYTHONPATH=. python scripts/evaluation/rerun_campaign.py --campaign campaign_002_metric_fixes --only 7,8
    PYTHONPATH=. python scripts/evaluation/rerun_campaign.py --campaign-config configs/eval/campaign.yaml --only exp_7
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from package.evaluation.campaign import CampaignConfig, CampaignRunner

EVAL_CONFIGS_DIR = ROOT / "configs" / "eval"


def get_git_sha() -> str:
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


def find_campaign_config(campaign_id: str) -> Path:
    """Locate the configs/eval/*.yaml whose campaign_id matches."""
    matches: list[Path] = []
    for path in sorted(EVAL_CONFIGS_DIR.glob("*.yaml")):
        try:
            cfg = CampaignConfig.from_yaml(path)
        except Exception:
            continue
        if cfg.campaign_id == campaign_id:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            f"No campaign config with campaign_id={campaign_id!r} under {EVAL_CONFIGS_DIR}"
        )
    raise SystemExit(
        f"Multiple configs match campaign_id={campaign_id!r}: "
        + ", ".join(str(p) for p in matches)
        + " — use --campaign-config to disambiguate"
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Re-run selected experiments of an existing campaign (subset merge)"
    )
    ap.add_argument(
        "--campaign",
        type=str,
        default=None,
        help="campaign_id to look up under configs/eval/ (e.g. campaign_002_metric_fixes)",
    )
    ap.add_argument(
        "--campaign-config",
        type=str,
        default=None,
        help="Explicit campaign YAML path (overrides --campaign lookup)",
    )
    ap.add_argument(
        "--only",
        type=str,
        required=True,
        help="Comma-separated experiment selectors (e.g. 7,8,11,12 or exp_7,exp_8)",
    )
    ap.add_argument("--git-sha", type=str, default="", help="Git SHA (auto-detected if omitted)")
    args = ap.parse_args()

    only = [t.strip() for t in args.only.split(",") if t.strip()]
    if not only:
        raise SystemExit("--only given but empty")

    if args.campaign_config:
        campaign_path = Path(args.campaign_config)
    elif args.campaign:
        campaign_path = find_campaign_config(args.campaign)
    else:
        raise SystemExit("Provide --campaign <campaign_id> or --campaign-config <path>")
    if not campaign_path.exists():
        raise SystemExit(f"Campaign config not found: {campaign_path}")

    campaign = CampaignConfig.from_yaml(campaign_path)
    git_sha = args.git_sha or get_git_sha()

    print(f"Campaign ID: {campaign.campaign_id}")
    print(f"Config: {campaign_path}")
    print(f"Output directory: {campaign.output_dir}")
    print(f"Re-run experiments (--only): {', '.join(only)}")
    print(f"Git SHA: {git_sha}")

    result = CampaignRunner(campaign, git_sha=git_sha).run_campaign(only=only)
    ok = sum(1 for r in result.runs if r.success)
    print(f"\nCampaign result saved. Successful runs: {ok}/{len(result.runs)}")


if __name__ == "__main__":
    main()
