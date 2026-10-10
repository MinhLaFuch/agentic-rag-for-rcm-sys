import argparse
import sys

import pandas as pd

from package.config import get_data_paths, get_domains, load_config
from package.data import tag_domain
from package.data.clean import clean_interactions
from package.data.domain import domain_breakdown, merge_domains
from package.data.filter import k_core_filter
from package.data.loader import estimate_memory_usage_mb, optimize_interaction_dtypes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        action="append",
        help="Tên domain (phải đã chạy Stage 1). Lặp lại cho mỗi domain; mặc định: tất cả trong domains.yaml.",
    )
    parser.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml). Stage 3 phải dùng cùng tag.")
    parser.add_argument("--force", action="store_true", help="Ghi đè output cũ nếu có.")
    parser.add_argument(
        "--cold-start-report",
        action="store_true",
        help="In số user warm khi lọc riêng từng domain so với khi gộp (tốn thêm RAM/thời gian).",
    )
    args = parser.parse_args()

    filtering_config = load_config("data/filtering")
    min_user = filtering_config["filtering"]["min_user_interactions"]
    min_item = filtering_config["filtering"]["min_item_interactions"]
    max_iter = filtering_config["filtering"]["max_iterations"]
    domains = args.domain or get_domains()
    paths = get_data_paths(args.tag)
    output_path = paths.filtered_path

    if output_path.exists() and not args.force:
        raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để ghi đè.")

    print(f"=== STAGE 2: merge + filter domains={domains} tag={paths.tag} ===")

    tagged_dfs = []
    for domain in domains:
        path = paths.cleaned_path(domain)
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {path} — chạy stage1_clean_domain.py cho domain '{domain}' trước."
            )
        df = pd.read_parquet(path)
        print(f"  loaded domain={domain} rows={len(df)} memory_mb={estimate_memory_usage_mb(df):.1f}")
        tagged_dfs.append(tag_domain(df, domain))

    merged = merge_domains(tagged_dfs)
    del tagged_dfs  # giải phóng ngay, không giữ 2 bản copy trong RAM
    print(f"merged total_rows={len(merged)} memory_mb={estimate_memory_usage_mb(merged):.1f}")

    breakdown = domain_breakdown(merged)
    for _, row in breakdown.iterrows():
        print(
            f"  domain={row['domain']} interactions={row['num_interactions']} "
            f"users={row['num_users']} items={row['num_items']}"
        )

    merged, dedupe_report = clean_interactions(merged)
    print(f"post_merge_dedupe dropped={dedupe_report['num_dropped_duplicates']}")

    # k-core chạy TRÊN DỮ LIỆU ĐÃ GỘP: min_user_interactions tính trên tổng interaction
    # của user qua mọi domain, không phải riêng từng domain.
    before_users = merged["user_id"].nunique()
    filtered = k_core_filter(merged, min_user, min_item, max_iter)
    print(
        f"k_core_filter (min_user={min_user}, min_item={min_item}) "
        f"users_before={before_users} users_after={filtered['user_id'].nunique()} "
        f"rows_after={len(filtered)}"
    )

    if args.cold_start_report:
        # Bao nhiêu user "sống lại" nhờ gộp domain (giảm cold-start): nếu combined > sum(per_domain).
        per_domain_warm = {}
        for domain in domains:
            single = merged[merged["domain"] == domain]
            single_filtered = k_core_filter(single, min_user, min_item, max_iter)
            per_domain_warm[domain] = single_filtered["user_id"].nunique()
        print(
            f"cold_start_check per_domain_warm_users={per_domain_warm} "
            f"combined_warm_users={filtered['user_id'].nunique()}"
        )
    del merged

    if len(filtered) == 0:
        sys.exit("BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — giảm ngưỡng filtering trong configs/data/filtering.yaml")

    filtered = optimize_interaction_dtypes(filtered)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_parquet(output_path, index=False)

    print(f"=== STAGE 2 DONE: saved {len(filtered)} rows -> {output_path} ===")


if __name__ == "__main__":
    main()

# NẾU VẪN OOM Ở STAGE NÀY:
# - Giảm số domain load cùng lúc: chạy với 2 domain trước (TAG riêng), rồi thêm domain thứ 3.
# - Tăng tạm filtering.min_user_interactions / min_item_interactions trong configs/data/filtering.yaml
#   để loại bớt dữ liệu sớm hơn.
