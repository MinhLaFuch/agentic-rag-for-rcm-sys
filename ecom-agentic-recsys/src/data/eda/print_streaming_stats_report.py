"""
EDA functions cho interaction data (Phase 2, mục V/VI/XVIII).

Các hàm ở đây là pure function trên pandas DataFrame, KHÔNG tự tải dữ
liệu — vì vậy có thể unit test bằng dữ liệu synthetic (để verify logic
đúng), tách biệt hoàn toàn với việc dữ liệu thật có tải được hay không
(xem src/data/acquire.py — hiện đang BLOCKED do network).
"""

from __future__ import annotations

import numpy as np

from ._dataclass import StreamingInteractionStats


def print_streaming_stats_report(stats: "StreamingInteractionStats") -> None:
    """In báo cáo dễ đọc — người dùng copy toàn bộ output này gửi lại Claude."""
    counts = np.array(list(stats.interactions_per_user.values()))
    denom = stats.num_users * stats.num_items
    sparsity = 1.0 - (stats.num_interactions / denom) if denom else float("nan")

    print("=== INTERACTION EDA REPORT (paste toàn bộ phần dưới lại cho Claude) ===")
    print(f"num_interactions: {stats.num_interactions}")
    print(f"num_users: {stats.num_users}")
    print(f"num_items: {stats.num_items}")
    print(f"sparsity: {sparsity:.6f}")
    print(f"avg_rating: {stats.rating_sum / stats.num_interactions:.3f}")
    print(f"timestamp_min: {stats.timestamp_min}")
    print(f"timestamp_max: {stats.timestamp_max}")
    print(f"avg_interactions_per_user: {counts.mean():.3f}")
    print(f"median_interactions_per_user: {np.median(counts):.1f}")
    print(f"p90_interactions_per_user: {np.percentile(counts, 90):.1f}")
    print(f"p99_interactions_per_user: {np.percentile(counts, 99):.1f}")
    print(f"max_interactions_per_user: {counts.max()}")
    print(f"num_users_with_1_interaction: {int((counts == 1).sum())}")
    print(f"num_users_with_ge_5_interactions: {int((counts >= 5).sum())}")
    print(f"num_users_with_ge_10_interactions: {int((counts >= 10).sum())}")
    print("=== END REPORT ===")
