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


def _version_chain(cfg: CampaignConfig, limit: int = 100) -> list[tuple[int, str]]:
    """[(bumps, campaign_id)] for the config and its --next successors."""
    chain = [(0, cfg.campaign_id)]
    cur = cfg
    for k in range(1, limit + 1):
        try:
            cur = cur.next_version()
        except ValueError:
            break
        chain.append((k, cur.campaign_id))
    return chain


def find_campaign_config(campaign_id: str) -> tuple[Path, int]:
    """Locate the configs/eval/*.yaml + version bump for a campaign token.

    Exact campaign_id match first (including ids produced by run_campaign
    ``--next`` — those exist only as bumped copies of a source YAML, so the
    returned bump count must be re-applied before running). Otherwise any
    campaign_id containing the token (``campaign_002`` resolves
    ``campaign_002_metric_fixes``). One match wins; zero or several raise.
    """
    candidates: list[tuple[Path, int, str]] = []
    for path in sorted(EVAL_CONFIGS_DIR.glob("*.yaml")):
        try:
            cfg = CampaignConfig.from_yaml(path)
        except Exception:
            continue
        for bumps, cid in _version_chain(cfg):
            candidates.append((path, bumps, cid))

    exact = [(p, b) for p, b, cid in candidates if cid == campaign_id]
    if len(exact) == 1:
        return exact[0]

    # Loose matching only over source (unbumped) ids — bumped versions are
    # exact-match territory so short tokens like "campaign_002" don't collide
    # with "campaign_002_ablation_norank"-style successors of other YAMLs.
    fuzzy = [(p, b) for p, b, cid in candidates if b == 0 and campaign_id in cid]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if not fuzzy:
        known = ", ".join(sorted({cid for _, _, cid in candidates})) or "(none)"
        raise SystemExit(
            f"No campaign config matching {campaign_id!r} under {EVAL_CONFIGS_DIR}; "
            f"known campaign_ids: {known}"
        )
    raise SystemExit(
        f"Ambiguous campaign {campaign_id!r} — matches: "
        + ", ".join(f"{p.name}#{b}" for p, b in fuzzy)
        + " — use the full campaign_id or --campaign-config"
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

    bumps = 0
    if args.campaign_config:
        campaign_path = Path(args.campaign_config)
    elif args.campaign:
        campaign_path, bumps = find_campaign_config(args.campaign)
    else:
        raise SystemExit("Provide --campaign <campaign_id> or --campaign-config <path>")
    if not campaign_path.exists():
        raise SystemExit(f"Campaign config not found: {campaign_path}")

    campaign = CampaignConfig.from_yaml(campaign_path)
    for _ in range(bumps):
        campaign = campaign.next_version()
    if bumps:
        print(f"Resolved {args.campaign} -> {campaign.campaign_id} (source: {campaign_path.name} +{bumps} version)")
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
