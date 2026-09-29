"""
Script Phase 2: tải dữ liệu thật cho DOMAIN và in báo cáo EDA cơ bản.

Trạng thái hiện tại: BLOCKED trong container (huggingface.co bị chặn ở
tầng network — xem docs/limitations.md). Script này đã viết đúng, sẽ
chạy được ngay khi chạy trên máy có internet:

    DOMAIN=Video_Games PYTHONPATH=. python scripts/run_eda.py
"""

from src.config.loader import load_config
from src.data.loader import download_domain_reviews
from src.data.eda import compute_interaction_stats


def main() -> None:
    config = load_config("data")
    domain = config["domain"]
    print(f"Downloading reviews for domain={domain} ...")

    df = download_domain_reviews(domain)
    stats = compute_interaction_stats(df)

    print("--- EDA report ---")
    print(f"num_users: {stats.num_users}")
    print(f"num_items: {stats.num_items}")
    print(f"num_interactions: {stats.num_interactions}")
    print(f"sparsity: {stats.sparsity:.6f}")
    print(f"avg_interactions_per_user: {stats.avg_interactions_per_user:.3f}")
    print(f"median_interactions_per_user: {stats.median_interactions_per_user}")
    print(f"p90_interactions_per_user: {stats.p90_interactions_per_user}")
    print(f"timestamp_range: {stats.timestamp_min} - {stats.timestamp_max}")


if __name__ == "__main__":
    main()
