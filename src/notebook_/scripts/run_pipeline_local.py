import argparse
import os

import pandas as pd

from package.agent.config.loader import load_config
from data.clean import clean_interactions
from data.filter import kcore_filter
from data import check_no_duplicate_across_splits
from data.leakage.profile_snapshot import check_profile_snapshot
from data.leakage.split import check_split_temporal_order
from data.train.mapping import apply_id_mapping, build_id_mappings, save_mappings
from data.train.temporal_split import compute_temporal_cutoffs, temporal_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-path", required=True)
    args = parser.parse_args()

    config = load_config("data")
    domain = config["domain"]
    min_user = config["filtering"]["min_user_interactions"]
    min_item = config["filtering"]["min_item_interactions"]
    train_ratio = config["split"]["train_ratio"]
    val_ratio = config["split"]["validation_ratio"]
    test_ratio = config["split"]["test_ratio"]

    report_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        report_lines.append(msg)

    log(f"=== REPORT (domain={domain}) ===")

    # 1. Load
    df = pd.read_parquet(args.review_path)
    log(f"step=load raw_rows={len(df)}")

    # 2. Clean
    df, clean_report = clean_interactions(df)
    log(
        f"step=clean input={clean_report['num_input']} "
        f"dropped_missing={clean_report['num_dropped_missing_required_fields']} "
        f"dropped_duplicates={clean_report['num_dropped_duplicates']} "
        f"output={clean_report['num_output']}"
    )

    # 3. k-core filter
    before_filter = len(df)
    before_users = df["user_id"].nunique()
    before_items = df["parent_asin"].nunique()
    df = kcore_filter(df, user_k=min_user, item_k=min_item)
    log(
        f"step=k_core_filter (min_user={min_user}, min_item={min_item}) "
        f"rows_before={before_filter} rows_after={len(df)} "
        f"users_before={before_users} users_after={df['user_id'].nunique()} "
        f"items_before={before_items} items_after={df['parent_asin'].nunique()}"
    )

    if len(df) == 0:
        log("BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — ngưỡng min_user/min_item quá cao so với dữ liệu thật. Cần giảm ngưỡng trong configs/data.yaml.")
        _print_final(report_lines)
        return

    # 4. ID mapping
    user2id, item2id = build_id_mappings(df)
    df = apply_id_mapping(df, user2id, item2id)
    log(f"step=id_mapping num_users={len(user2id)} num_items={len(item2id)}")

    mapping_dir = f"data/mapped/{domain}"
    save_mappings(user2id, item2id, mapping_dir)
    log(f"step=save_mappings dir={mapping_dir}")

    # 5. Temporal split
    cutoff_1, cutoff_2 = compute_temporal_cutoffs(df, train_ratio, val_ratio, test_ratio)
    train, validation, test = temporal_split(df, cutoff_1, cutoff_2)
    log(
        f"step=temporal_split cutoff_1={cutoff_1} cutoff_2={cutoff_2} "
        f"train_rows={len(train)} val_rows={len(validation)} test_rows={len(test)}"
    )

    # 6. Leakage check
    try:
        check_split_temporal_order(train, validation, test)
        check_no_duplicate_across_splits(train, validation, test)
        # spot-check profile snapshot tại cutoff_1 trên chính train set
        check_profile_snapshot(as_of_timestamp=cutoff_1, source_interactions=train)
        log("step=leakage_check status=PASS (3/3 check)")
    except Exception as exc:  # LeakageError hoặc ValueError
        log(f"step=leakage_check status=FAIL error={exc}")
        log("PIPELINE ABORTED — không lưu split do phát hiện leakage.")
        _print_final(report_lines)
        raise

    # 7. Save splits
    splits_dir = f"data/splits/{domain}"
    os.makedirs(splits_dir, exist_ok=True)
    train.to_parquet(f"{splits_dir}/train.parquet", index=False)
    validation.to_parquet(f"{splits_dir}/validation.parquet", index=False)
    test.to_parquet(f"{splits_dir}/test.parquet", index=False)
    log(f"step=save_splits dir={splits_dir}")

    _print_final(report_lines)


def _print_final(report_lines: list[str]) -> None:
    # Keep this marker ASCII-only: Windows consoles using cp1252 can otherwise
    # raise UnicodeEncodeError after the pipeline has already saved its outputs.
    print("=== END REPORT ===")


if __name__ == "__main__":
    main()
