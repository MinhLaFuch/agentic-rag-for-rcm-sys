import argparse
import os

from package.config.loader import load_config
from package.data.clean import clean_interactions
from package.data import tag_domain
from package.data.domain import domain_breakdown, merge_domains
from package.data.loader import estimate_memory_usage_mb, optimize_interaction_dtypes
from package.data.filter import k_core_filter

os.environ.setdefault("DOMAIN", "multi_domain_placeholder")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        action="append",
        required=True,
        help="Tên domain (phải đã chạy Stage 1 trước). Lặp lại flag cho mỗi domain.",
    )
    parser.add_argument("--cleaned-dir", default="data/cleaned")
    parser.add_argument("--output-dir", default="data/filtered/multi_domain")
    args = parser.parse_args()

    config = load_config("data")
    min_user = config["filtering"]["min_user_interactions"]
    min_item = config["filtering"]["min_item_interactions"]

    print(f"=== STAGE 2: merge + filter domains={args.domain} ===")

    import pandas as pd

    tagged_dfs = []
    for domain in args.domain:
        path = os.path.join(args.cleaned_dir, domain, "interactions.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Không tìm thấy {path} — chạy stage1_clean_domain.py cho "
                f"domain '{domain}' trước."
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

    before_users = merged["user_id"].nunique()
    filtered = k_core_filter(merged, min_user_interactions=min_user, min_item_interactions=min_item)
    del merged
    print(
        f"k_core_filter (min_user={min_user}, min_item={min_item}) "
        f"users_before={before_users} users_after={filtered['user_id'].nunique()} "
        f"rows_after={len(filtered)}"
    )

    if len(filtered) == 0:
        print("BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — giảm ngưỡng trong configs/data.yaml")
        return

    filtered = optimize_interaction_dtypes(filtered)
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, "interactions.parquet")
    filtered.to_parquet(output_path, index=False)

    print(f"=== STAGE 2 DONE: saved {len(filtered)} rows -> {output_path} ===")


if __name__ == "__main__":
    main()

# GHI CHÚ NẾU VẪN OOM Ở STAGE NÀY:
# - Giảm số domain load cùng lúc (chạy Stage 2 với 2 domain trước, xem
#   kết quả, rồi thêm domain thứ 3 sau nếu máy đủ RAM).
# - Tăng ngưỡng min_user_interactions/min_item_interactions tạm thời để
#   loại bớt dữ liệu sớm hơn (đổi trong configs/data.yaml).
# - Cân nhắc dùng scripts/py/sample_review_data.py để lấy sample trước khi
#   chạy Stage 1, giảm kích thước ngay từ đầu.
