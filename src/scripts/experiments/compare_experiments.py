"""
So sánh thí nghiệm ablation (base template).

Cách chạy:
    PYTHONPATH=. python scripts/experiments/compare_experiments.py

Đọc config từ configs/agent/ablation.yaml, load dữ liệu từ các exp_NNN directories,
so sánh theo các contrast được định nghĩa, và sinh báo cáo markdown/CSV/JSON.

The per-contrast execution lives in package.evaluation.ablation.run_ablation_contrasts
— shared with the campaign runner, which resolves groups from experiment names
instead of config paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from package.evaluation.ablation import get_ablation_limits, run_ablation_contrasts
from package.config import get_data_paths
from package.config.load_config import ConfigError
from package.utils import ensure_utf8_stdout


def parse_args() -> argparse.Namespace:
    # Config is fixed to configs/agent/ablation.yaml; per-run variation goes through CONFIG_OVERLAY_PATH.
    return argparse.ArgumentParser(description="Compare ablation experiments").parse_args()


def main() -> None:
    ensure_utf8_stdout()
    parse_args()

    print("=" * 60)
    print("Ablation Comparison Tool")
    print("=" * 60)

    # Load limits
    print("Loading config from configs/agent/ablation.yaml...")
    try:
        limits = get_ablation_limits()
    except ConfigError as e:
        print(f"ERROR: {e}")
        return

    print(f"Bootstrap resamples: {limits.bootstrap_resamples}")
    print(f"Confidence: {limits.confidence}")
    print(f"Min n warn: {limits.min_n_warn}")
    print(f"Seed: {limits.seed}")
    print(f"Metrics: {', '.join(limits.metrics)}")
    print(f"Groups: {list(limits.groups.keys())}")
    print(f"Contrasts: {len(limits.contrasts)}")
    print("")

    # Validate groups exist (paths resolve relative to outputs.agent_eval)
    base_dir = get_data_paths().output_dir("agent_eval")
    groups: dict[str, list[Path]] = {}
    for group_name, exp_names in limits.groups.items():
        print(f"Validating group '{group_name}' with exps: {exp_names}")
        groups[group_name] = [base_dir / name for name in exp_names]
        for exp_dir in groups[group_name]:
            if not exp_dir.exists():
                print(f"ERROR: experiment directory not found: {exp_dir}")
                return
    print("")

    # Prepare output directory
    output_dir = get_data_paths().experiments_dir / limits.output_subdir

    summary = run_ablation_contrasts(
        limits=limits,
        groups=groups,
        contrasts=limits.contrasts,
        output_dir=output_dir,
    )

    # Report per-contrast outcomes (the runner already wrote all artifacts)
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Output directory: {summary['output_dir']}")
    print(f"Contrasts processed: {len(summary['contrasts'])}")
    for name, status in summary["contrasts"].items():
        marker = "OK" if status["status"] == "ok" else f"ERROR: {status.get('error')}"
        print(f"  {name}: {marker}")

    if summary["missing_columns"]:
        print(f"\nMissing columns (skipped): {', '.join(summary['missing_columns'])}")

    print("\nDone.")


if __name__ == "__main__":
    main()
