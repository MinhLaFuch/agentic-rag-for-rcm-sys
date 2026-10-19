"""Stage 2: merge domains and apply k-core filtering."""

from __future__ import annotations

import sys

import pandas as pd

from ...config import DataPaths, load_config
from .. import tag_domain
from ..clean import clean_interactions
from ..domain import domain_breakdown, merge_domains
from ..filter import k_core_filter
from ..loader import estimate_memory_usage_mb, optimize_interaction_dtypes


def merge_filter_domains(
    paths: DataPaths,
    domains: list[str],
    force: bool = False,
    cold_start_report: bool = False,
) -> dict:
    """Merge multiple domains and apply k-core filtering.

    Args:
        paths: DataPaths configuration.
        domains: List of domain names to merge.
        force: Overwrite existing output.
        cold_start_report: Print cold-start statistics (expensive).

    Returns:
        Report dictionary with statistics.

    Raises:
        SystemExit: If k-core filtering removes all data (BLOCKED).
    """
    filtering_config = load_config("data/filtering")
    min_user = filtering_config["filtering"]["min_user_interactions"]
    min_item = filtering_config["filtering"]["min_item_interactions"]
    output_path = paths.filtered_path

    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để ghi đè.")

    print(f"=== STAGE 2: merge + filter domains={domains} tag={paths.tag} ===")

    tagged_dfs = []
    for domain in domains:
        path = paths.cleaned_path(domain)
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {path} — chạy python scripts/data_pipeline/run_pipeline.py --stages 1 --domain {domain} trước."
            )
        df = pd.read_parquet(path)
        print(f"  loaded domain={domain} rows={len(df)} memory_mb={estimate_memory_usage_mb(df):.1f}")
        tagged_dfs.append(tag_domain(df, domain))

    merged = merge_domains(tagged_dfs)
    del tagged_dfs
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
    print(
        f"k_core_filter (min_user={min_user}, min_item={min_item}) "
        f"users_before={before_users} users_after={filtered['user_id'].nunique()} "
        f"rows_after={len(filtered)}"
    )

    if cold_start_report:
        per_domain_warm = {}
        for domain in domains:
            single = merged[merged["domain"] == domain]
            single_filtered = k_core_filter(single, min_user_interactions=min_user, min_item_interactions=min_item)
            per_domain_warm[domain] = single_filtered["user_id"].nunique()
        print(
            f"cold_start_check per_domain_warm_users={per_domain_warm} "
            f"combined_warm_users={filtered['user_id'].nunique()}"
        )
    del merged

    if len(filtered) == 0:
        sys.exit(
            "BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — giảm ngưỡng filtering trong configs/data/filtering.yaml. "
            "Nếu vẫn OOM: chạy ít domain cùng lúc với tag riêng (--domain D1 --domain D2 --tag mytag), "
            "hoặc tăng tạm filtering.min_user_interactions/min_item_interactions."
        )

    filtered = optimize_interaction_dtypes(filtered)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_parquet(output_path, index=False)

    print(f"=== STAGE 2 DONE: saved {len(filtered)} rows -> {output_path} ===")

    return {"num_rows": len(filtered), "num_users": filtered["user_id"].nunique(), "num_items": filtered["parent_asin"].nunique()}
