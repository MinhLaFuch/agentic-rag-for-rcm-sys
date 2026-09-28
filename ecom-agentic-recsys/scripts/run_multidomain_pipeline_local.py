import argparse
import os

# data.yaml có field domain/paths dùng ${DOMAIN} interpolation cho
# workflow single-domain (Phase 2-3). Multi-domain không dùng field đó,
# nhưng loader vẫn cần env var để parse toàn bộ file — set placeholder
# an toàn nếu người dùng chưa set DOMAIN.
os.environ.setdefault("DOMAIN", "multi_domain_placeholder")

from src.config.loader import load_config
from data.clean import clean_interactions, load_reviews_dataframe
from data.domain import domain_breakdown, merge_domains, tag_domain
from data.filter import k_core_filter
from data.leakage import (
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
)
from data.mapping import apply_id_mapping, build_id_mappings, save_mappings
from data.split import compute_temporal_cutoffs, temporal_split


def parse_domain_arg(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"--domain phải có dạng TenDomain=duong_dan, nhận được: {value}"
        )
    domain, path = value.split("=", 1)
    return domain, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        action="append",
        required=True,
        type=parse_domain_arg,
        help="Lặp lại flag này cho mỗi domain, dạng TenDomain=duong_dan_file",
    )
    args = parser.parse_args()

    config = load_config("data")
    min_user = config["filtering"]["min_user_interactions"]
    min_item = config["filtering"]["min_item_interactions"]
    train_ratio = config["split"]["train_ratio"]
    val_ratio = config["split"]["validation_ratio"]
    test_ratio = config["split"]["test_ratio"]

    report_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        report_lines.append(msg)

    domain_names = [d for d, _ in args.domain]
    log(f"=== MULTI-DOMAIN PHASE 3 REPORT (domains={domain_names}) ===")

    # 1-2. Load + clean từng domain riêng, rồi tag domain
    tagged_dfs = []
    for domain, path in args.domain:
        df = load_reviews_dataframe(
            path, columns=["user_id", "parent_asin", "rating", "timestamp"]
        )
        df, clean_report = clean_interactions(df)
        log(
            f"step=load_and_clean domain={domain} "
            f"raw_rows={clean_report['num_input']} "
            f"dropped_missing={clean_report['num_dropped_missing_required_fields']} "
            f"dropped_duplicates={clean_report['num_dropped_duplicates']} "
            f"clean_rows={clean_report['num_output']}"
        )
        tagged_dfs.append(tag_domain(df, domain))

    # 3. Merge
    merged = merge_domains(tagged_dfs)
    breakdown = domain_breakdown(merged)
    log(f"step=merge total_rows={len(merged)} total_users={merged['user_id'].nunique()}")
    for _, row in breakdown.iterrows():
        log(
            f"  domain={row['domain']} interactions={row['num_interactions']} "
            f"users={row['num_users']} items={row['num_items']}"
        )

    # 3b. Dedupe lại toàn cục sau merge (an toàn double-check)
    merged, dedupe_report = clean_interactions(merged)
    log(f"step=post_merge_dedupe dropped_duplicates={dedupe_report['num_dropped_duplicates']}")

    # 4. k-core filter TRÊN DỮ LIỆU ĐÃ GỘP — đây là điểm khác biệt quan
    # trọng: min_user_interactions tính trên TỔNG interaction của user
    # qua mọi domain, không phải riêng từng domain.
    before_users = merged["user_id"].nunique()
    before_items = merged["parent_asin"].nunique()
    filtered = k_core_filter(merged, min_user_interactions=min_user, min_item_interactions=min_item)
    log(
        f"step=k_core_filter_on_merged (min_user={min_user}, min_item={min_item}) "
        f"users_before={before_users} users_after={filtered['user_id'].nunique()} "
        f"items_before={before_items} items_after={filtered['parent_asin'].nunique()}"
    )

    if len(filtered) == 0:
        log("BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — kiểm tra lại ngưỡng trong configs/data.yaml")
        print("=== END REPORT ===")
        return

    # So sánh: bao nhiêu user "sống lại" nhờ gộp domain (cold-start mitigation)
    per_domain_warm_counts = {}
    for domain in domain_names:
        single = merged[merged["domain"] == domain]
        single_filtered = k_core_filter(single, min_user_interactions=min_user, min_item_interactions=min_item)
        per_domain_warm_counts[domain] = single_filtered["user_id"].nunique()
    combined_warm = filtered["user_id"].nunique()
    log(
        f"step=cold_start_mitigation_check per_domain_warm_users={per_domain_warm_counts} "
        f"combined_warm_users={combined_warm} "
        f"(so sánh: nếu combined > sum(per_domain), đây là user 'sống lại' nhờ gộp domain)"
    )

    # 5. ID mapping toàn cục
    user2id, item2id = build_id_mappings(filtered)
    filtered = apply_id_mapping(filtered, user2id, item2id)
    log(f"step=global_id_mapping num_users={len(user2id)} num_items={len(item2id)}")

    mapping_dir = "data/mapped/multi_domain"
    save_mappings(user2id, item2id, mapping_dir)
    log(f"step=save_mappings dir={mapping_dir}")

    # 6. Temporal split toàn cục
    cutoff_1, cutoff_2 = compute_temporal_cutoffs(filtered, train_ratio, val_ratio, test_ratio)
    train, validation, test = temporal_split(filtered, cutoff_1, cutoff_2)
    log(
        f"step=temporal_split cutoff_1={cutoff_1} cutoff_2={cutoff_2} "
        f"train_rows={len(train)} val_rows={len(validation)} test_rows={len(test)}"
    )

    # 7. Leakage check
    try:
        check_split_temporal_order(train, validation, test)
        check_no_duplicate_across_splits(train, validation, test)
        check_profile_snapshot(as_of_timestamp=cutoff_1, source_interactions=train)
        log("step=leakage_check status=PASS (3/3 check)")
    except Exception as exc:
        log(f"step=leakage_check status=FAIL error={exc}")
        log("PIPELINE ABORTED — không lưu split do phát hiện leakage.")
        print("=== END REPORT ===")
        raise

    # 8. Save
    splits_dir = "data/splits/multi_domain"
    os.makedirs(splits_dir, exist_ok=True)
    train.to_parquet(f"{splits_dir}/train.parquet", index=False)
    validation.to_parquet(f"{splits_dir}/validation.parquet", index=False)
    test.to_parquet(f"{splits_dir}/test.parquet", index=False)
    log(f"step=save_splits dir={splits_dir}")

    print("=== END REPORT (paste toàn bộ báo cáo trên lại cho Claude) ===")


if __name__ == "__main__":
    main()
