#!/usr/bin/env python3
"""
Chẩn đoán splits để hiểu lý do recall@10 ≡ 0.

Usage:
    python scripts/eda_diagnostic/diagnose_splits.py --tag <tag> [--out output.json]
"""

import argparse
import json
from pathlib import Path

from package.config import get_data_paths
from package.data.eda import diagnose_splits
from package.data.split import load_splits


def format_percentage(value: float) -> str:
    """Format percentage with 2 decimal places."""
    return f"{value:.2f}%"


def print_diagnosis_report(diagnosis, tag: str):
    """Report counts separately from pair eligibility and macro metric bounds."""
    print(f"DIAGNOSIS REPORT: {tag} (protocol v2)")
    for prefix in ("train", "val", "test"):
        print(f"{prefix}: rows={getattr(diagnosis, prefix + '_rows')}, "
              f"users={getattr(diagnosis, prefix + '_users')}, "
              f"items={getattr(diagnosis, prefix + '_items')}")
        print(f"  timestamps: {getattr(diagnosis, prefix + '_timestamp_min')} .. "
              f"{getattr(diagnosis, prefix + '_timestamp_max')}")
        print(f"  domain row fractions: {getattr(diagnosis, prefix + '_domain_ratios')}")
    print("\nTrain-only references (not runtime test-fit):")
    for prefix in ("val", "test"):
        print(f"{prefix}: unique items in train={getattr(diagnosis, prefix + '_items_in_train_pct'):.3f}%; "
              f"rows with train items={getattr(diagnosis, prefix + '_rows_with_train_item_pct'):.3f}%; "
              f"users with train history={getattr(diagnosis, prefix + '_users_with_train_history_pct'):.3f}%")
        print(f"  unique train history per target user (including zeros): {getattr(diagnosis, prefix + '_history_len_stats')}")
    print("\nRepeat pairs are not necessarily leakage. Item warm means ANY fit user interacted.")
    print("Catalog eligibility is micro unique-pair coverage, NOT a universal macro Recall@K ceiling.")


def main():
    parser = argparse.ArgumentParser(
        description="Chẩn đoán splits để hiểu lý do recall@10 ≡ 0"
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Data tag (e.g., exp_002, exp_003)"
    )
    parser.add_argument(
        "--out",
        help="Path to output JSON file (optional)"
    )
    args = parser.parse_args()

    print("="*80)
    print("DIAGNOSING SPLITS")
    print("="*80)
    print(f"Tag: {args.tag}")

    # Load data paths
    paths = get_data_paths(args.tag)
    print(f"Splits dir: {paths.splits_dir}")

    print(f"Loading splits from {paths.splits_dir}...")
    train, validation, test = load_splits(
        paths.splits_dir, columns=("user_idx", "item_idx", "timestamp", "domain"))
    for name, frame in (("train", train), ("validation", validation), ("test", test)):
        print(f"{name}: actual columns={list(frame.columns)}")

    # Run diagnosis
    print("\nRunning diagnosis...")
    diagnosis = diagnose_splits(train, validation, test)

    # Print report
    print_diagnosis_report(diagnosis, args.tag)

    # Save to JSON if requested
    if args.out:
        out_path = Path(args.out)
        print(f"\nSaving diagnosis to {out_path}...")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(diagnosis.__dict__, f, indent=2, default=str)
        print("Done")

    print("\nProtocol definitions:")
    print(json.dumps(diagnosis.protocol, indent=2))
    print("\nRuntime fit diagnostics (unique pairs; history includes cold users):")
    print(json.dumps(diagnosis.fit_diagnostics, indent=2))
    print("\nPer-domain runtime fit diagnostics:")
    print(json.dumps(diagnosis.domain_diagnostics, indent=2))


if __name__ == "__main__":
    main()
