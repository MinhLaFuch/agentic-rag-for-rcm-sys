#!/usr/bin/env python3
"""
Chẩn đoán splits để hiểu lý do recall@10 ≡ 0.

Usage:
    python scripts/diagnose_splits.py --tag <tag> [--out output.json]
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from package.config import get_data_paths
from package.data.eda import diagnose_splits
from package.data.mapping import load_mappings
from package.data.split import load_splits


def format_percentage(value: float) -> str:
    """Format percentage with 2 decimal places."""
    return f"{value:.2f}%"


def print_diagnosis_report(diagnosis, tag: str):
    """In báo cáo chẩn đoán ra console."""
    print("="*80)
    print(f"DIAGNOSIS REPORT: {tag}")
    print("="*80)

    print("\n--- SỐ LƯỢNG CƠ BẢN ---")
    print(f"Train:   {diagnosis.train_rows} rows, {diagnosis.train_users} users, {diagnosis.train_items} items")
    print(f"Val:     {diagnosis.val_rows} rows, {diagnosis.val_users} users, {diagnosis.val_items} items")
    print(f"Test:    {diagnosis.test_rows} rows, {diagnosis.test_users} users, {diagnosis.test_items} items")

    print("\n--- KHOẢNG THỜI GIAN ---")
    print(f"Train:   {diagnosis.train_timestamp_min} - {diagnosis.train_timestamp_max}")
    print(f"Val:     {diagnosis.val_timestamp_min} - {diagnosis.val_timestamp_max}")
    print(f"Test:    {diagnosis.test_timestamp_min} - {diagnosis.test_timestamp_max}")

    print("\n--- PHÂN BỔ DOMAIN (nếu có) ---")
    if diagnosis.train_domain_ratios:
        print("Train domain ratios:")
        for domain, ratio in sorted(diagnosis.train_domain_ratios.items()):
            print(f"  {domain}: {format_percentage(ratio * 100)}")
        print("Val domain ratios:")
        for domain, ratio in sorted(diagnosis.val_domain_ratios.items()):
            print(f"  {domain}: {format_percentage(ratio * 100)}")
        print("Test domain ratios:")
        for domain, ratio in sorted(diagnosis.test_domain_ratios.items()):
            print(f"  {domain}: {format_percentage(ratio * 100)}")
    else:
        print("(không có cột domain trong splits)")

    print("\n--- TARGET ITEM COVERAGE ---")
    print(f"Val items seen in train:   {format_percentage(diagnosis.val_items_in_train_pct)}")
    print(f"Test items seen in train:  {format_percentage(diagnosis.test_items_in_train_pct)}")
    print(f"Val rows with train item:  {format_percentage(diagnosis.val_rows_with_train_item_pct)}")
    print(f"Test rows with train item: {format_percentage(diagnosis.test_rows_with_train_item_pct)}")
    print("→ Nếu con số này thấp: nhiều item cold-start trong val/test")

    print("\n--- USER HISTORY COVERAGE ---")
    print(f"Val users with train history:  {format_percentage(diagnosis.val_users_with_train_history_pct)}")
    print(f"Test users with train history: {format_percentage(diagnosis.test_users_with_train_history_pct)}")
    print("Val user train history length:")
    print(f"  min: {diagnosis.val_history_len_stats['min']:.0f}, "
          f"median: {diagnosis.val_history_len_stats['median']:.0f}, "
          f"p90: {diagnosis.val_history_len_stats['p90']:.0f}")
    print("Test user train history length:")
    print(f"  min: {diagnosis.test_history_len_stats['min']:.0f}, "
          f"median: {diagnosis.test_history_len_stats['median']:.0f}, "
          f"p90: {diagnosis.test_history_len_stats['p90']:.0f}")
    print("→ Nếu con số này thấp: nhiều user cold-start trong val/test")

    print("\n--- REPEAT PAIRS (LEAKAGE DUE TO EXCLUDE) ---")
    print(f"Val repeat pairs (in train):     {format_percentage(diagnosis.val_repeat_pairs_pct)}")
    print(f"Test repeat pairs (in train+val): {format_percentage(diagnosis.test_repeat_pairs_pct)}")
    print("→ Nếu con số này cao: nhiều cặp bị evaluator loại khỏi gợi ý")

    print("\n--- TRẦN RECALL LÝ THUYẾT (REACHABLE) ---")
    print(f"Val reachable (item in train AND pair not in history): {format_percentage(diagnosis.val_reachable_pct)}")
    print(f"Test reachable (item in train AND pair not in history): {format_percentage(diagnosis.test_reachable_pct)}")
    print("→ Đây là trần recall lý thuyết: nếu thấp, recall@10 không thể cao")

    print("\n--- MULTI-DOMAIN USERS ---")
    print(f"Train multi-domain users: {format_percentage(diagnosis.train_multi_domain_users_pct)}")
    print(f"Val multi-domain users:   {format_percentage(diagnosis.val_multi_domain_users_pct)}")
    print(f"Test multi-domain users:  {format_percentage(diagnosis.test_multi_domain_users_pct)}")


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

    # Load splits
    print(f"\nLoading splits from {paths.splits_dir}...")
    train, validation, test = load_splits(paths.splits_dir, columns=("user_idx", "item_idx"))
    print(f"Loaded: train={len(train)}, val={len(validation)}, test={len(test)}")

    # Load mappings (nếu có)
    try:
        user2id, item2id = load_mappings(paths.mapped_dir)
        print(f"Loaded mappings: {len(user2id)} users, {len(item2id)} items")
    except FileNotFoundError:
        print("Mappings not found (using None)")
        user2id, item2id = None, None

    # Try to load timestamp and domain if available
    print("Trying to load timestamp and domain columns...")
    try:
        train_full, val_full, test_full = load_splits(
            paths.splits_dir,
            columns=("user_idx", "item_idx", "timestamp", "domain")
        )
        train = train_full
        validation = val_full
        test = test_full
        print("Loaded timestamp and domain columns")
    except Exception as e:
        print(f"Could not load timestamp/domain: {e}")
        print("Proceeding without timestamp/domain")

    # Run diagnosis
    print("\nRunning diagnosis...")
    diagnosis = diagnose_splits(train, validation, test, user2id, item2id)

    # Print report
    print_diagnosis_report(diagnosis, args.tag)

    # Save to JSON if requested
    if args.out:
        out_path = Path(args.out)
        print(f"\nSaving diagnosis to {out_path}...")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(diagnosis.__dict__, f, indent=2, default=str)
        print("Done")

    # Try to load metrics.json if available
    metrics_path = paths.data_dir / "metrics.json"
    if metrics_path.exists():
        print(f"\nFound metrics.json at {metrics_path}")
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        if "target_item_seen_ratio" in metrics:
            print(f"target_item_seen_ratio from metrics.json: {metrics['target_item_seen_ratio']}")
            print("(compare with val/test_items_in_train_pct above)")


if __name__ == "__main__":
    main()
