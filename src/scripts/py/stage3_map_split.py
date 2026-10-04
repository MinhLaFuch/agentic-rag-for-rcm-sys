import argparse
import sys

import pandas as pd

from package.config import get_data_paths, load_config
from package.data.leakage import (
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
)
from package.data.mapping import apply_id_mapping, build_id_mappings, save_mappings
from package.data.split import compute_temporal_cutoffs, temporal_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml). Phải khớp Stage 2.")
    parser.add_argument("--force", action="store_true", help="Ghi đè splits cũ nếu có.")
    args = parser.parse_args()

    split_config = load_config("split")
    train_ratio = split_config["split"]["train_ratio"]
    val_ratio = split_config["split"]["validation_ratio"]
    test_ratio = split_config["split"]["test_ratio"]
    paths = get_data_paths(args.tag)

    print(f"=== STAGE 3: ID mapping + temporal split + leakage check (tag={paths.tag}) ===")

    if not paths.filtered_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {paths.filtered_path} — chạy stage2_merge_filter.py (cùng tag) trước."
        )
    if (paths.splits_dir / "train.parquet").exists() and not args.force:
        sys.exit(f"{paths.splits_dir} đã có splits. Dùng --force để ghi đè.")

    df = pd.read_parquet(paths.filtered_path)
    print(f"loaded rows={len(df)} users={df['user_id'].nunique()} items={df['parent_asin'].nunique()}")

    user2id, item2id = build_id_mappings(df)
    df = apply_id_mapping(df, user2id, item2id)
    print(f"id_mapping num_users={len(user2id)} num_items={len(item2id)}")

    save_mappings(user2id, item2id, paths.mapped_dir)
    print(f"saved mappings -> {paths.mapped_dir}")

    cutoff_1, cutoff_2 = compute_temporal_cutoffs(df, train_ratio, val_ratio, test_ratio)
    train, validation, test = temporal_split(df, cutoff_1, cutoff_2)
    print(
        f"temporal_split cutoff_1={cutoff_1} cutoff_2={cutoff_2} "
        f"train={len(train)} val={len(validation)} test={len(test)}"
    )

    check_split_temporal_order(train, validation, test)
    check_no_duplicate_across_splits(train, validation, test)
    check_profile_snapshot(as_of_timestamp=cutoff_1, source_interactions=train)
    print("leakage_check status=PASS (3/3 check)")

    paths.splits_dir.mkdir(parents=True, exist_ok=True)
    train.to_parquet(paths.splits_dir / "train.parquet", index=False)
    validation.to_parquet(paths.splits_dir / "validation.parquet", index=False)
    test.to_parquet(paths.splits_dir / "test.parquet", index=False)

    print(f"=== STAGE 3 DONE: saved splits -> {paths.splits_dir} ===")


if __name__ == "__main__":
    main()
