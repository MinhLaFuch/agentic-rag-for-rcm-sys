
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class StreamingInteractionStats:
    """
    Giống InteractionStats nhưng tính bằng streaming (không load toàn bộ
    file vào RAM cùng lúc) — dùng cho file review lớn (Video_Games có
    ~4.6M dòng) chạy trên máy người dùng, không cần pandas load hết.
    """

    num_interactions: int = 0
    num_users: int = 0
    num_items: int = 0
    timestamp_min: int | None = None
    timestamp_max: int | None = None
    rating_sum: float = 0.0
    interactions_per_user: dict = field(default_factory=dict)


def compute_interaction_stats_streaming(path: str) -> "StreamingInteractionStats":
    """
    Đọc file review .jsonl.gz thật (schema: user_id, parent_asin, rating,
    timestamp, title, text, helpful_vote, verified_purchase) theo dòng,
    không load hết vào RAM. Phù hợp chạy trên máy người dùng với file
    lớn (ví dụ Video_Games ~4.6M review) mà không cần upload file lên chat.

    Sau khi chạy, in kết quả và paste lại cho Claude để cập nhật docs.
    """
    import gzip
    import json
    from collections import Counter

    user_counts: Counter = Counter()
    item_ids: set = set()
    stats = StreamingInteractionStats()

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            stats.num_interactions += 1
            user_counts[record["user_id"]] += 1
            item_ids.add(record["parent_asin"])

            ts = record.get("timestamp")
            if ts is not None:
                if stats.timestamp_min is None or ts < stats.timestamp_min:
                    stats.timestamp_min = ts
                if stats.timestamp_max is None or ts > stats.timestamp_max:
                    stats.timestamp_max = ts

            rating = record.get("rating")
            if isinstance(rating, (int, float)):
                stats.rating_sum += rating

    stats.num_users = len(user_counts)
    stats.num_items = len(item_ids)
    stats.interactions_per_user = dict(user_counts)
    return stats


def print_streaming_stats_report(stats: "StreamingInteractionStats") -> None:
    """In báo cáo dễ đọc — người dùng copy toàn bộ output này gửi lại Claude."""
    import numpy as np

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


@dataclass
class InteractionStats:
    num_users: int
    num_items: int
    num_interactions: int
    sparsity: float  # 1 - num_interactions / (num_users * num_items)
    avg_interactions_per_user: float
    median_interactions_per_user: float
    p90_interactions_per_user: float
    timestamp_min: int
    timestamp_max: int


def compute_interaction_stats(interactions: pd.DataFrame) -> InteractionStats:
    """
    interactions: DataFrame bắt buộc có cột user_id, parent_asin, timestamp.
    """
    required_cols = {"user_id", "parent_asin", "timestamp"}
    missing = required_cols - set(interactions.columns)
    if missing:
        raise ValueError(f"interactions DataFrame missing columns: {missing}")

    num_users = interactions["user_id"].nunique()
    num_items = interactions["parent_asin"].nunique()
    num_interactions = len(interactions)

    denom = num_users * num_items
    sparsity = 1.0 - (num_interactions / denom) if denom > 0 else float("nan")

    per_user_counts = interactions.groupby("user_id").size()

    return InteractionStats(
        num_users=num_users,
        num_items=num_items,
        num_interactions=num_interactions,
        sparsity=sparsity,
        avg_interactions_per_user=float(per_user_counts.mean()),
        median_interactions_per_user=float(per_user_counts.median()),
        p90_interactions_per_user=float(per_user_counts.quantile(0.9)),
        timestamp_min=int(interactions["timestamp"].min()),
        timestamp_max=int(interactions["timestamp"].max()),
    )


def k_core_filter(
    interactions: pd.DataFrame,
    min_user_interactions: int,
    min_item_interactions: int,
    max_iterations: int = 20,
) -> pd.DataFrame:
    """
    Lặp lại việc loại user/item có ít hơn ngưỡng interaction cho đến khi
    ổn định (đúng khái niệm k-core filtering nêu ở configs/data.yaml).
    """
    df = interactions.copy()
    for _ in range(max_iterations):
        user_counts = df.groupby("user_id").size()
        item_counts = df.groupby("parent_asin").size()

        valid_users = user_counts[user_counts >= min_user_interactions].index
        valid_items = item_counts[item_counts >= min_item_interactions].index

        new_df = df[
            df["user_id"].isin(valid_users) & df["parent_asin"].isin(valid_items)
        ]
        if len(new_df) == len(df):
            break
        df = new_df
    return df


def segment_users(
    interactions: pd.DataFrame,
    as_of_timestamp: int,
    sparse_threshold: int = 3,
    evolving_category_col: str | None = None,
) -> pd.DataFrame:
    """
    Gán mỗi user vào 1 trong 4 nhóm theo mục XVIII: warm / new / sparse /
    evolving. Đây là implementation tối giản cho warm/new/sparse (dùng số
    lượng interaction <= as_of_timestamp); "evolving" cần dữ liệu category
    thật để so sánh category ưa thích trước/sau — nếu không có
    evolving_category_col, cột 'evolving_interest' sẽ luôn là False
    (KHÔNG suy diễn khi thiếu dữ liệu — mục XXVIII: không tạo số liệu giả).
    """
    past = interactions[interactions["timestamp"] <= as_of_timestamp]
    counts = past.groupby("user_id").size().rename("n_interactions")

    segments = counts.to_frame()
    segments["segment"] = np.select(
        [
            segments["n_interactions"] == 0,
            segments["n_interactions"] <= sparse_threshold,
        ],
        ["new", "sparse_history"],
        default="warm",
    )

    if evolving_category_col and evolving_category_col in interactions.columns:
        # placeholder cho logic evolving-interest thật — sẽ hoàn thiện khi
        # có dữ liệu category thật (BLOCKED hiện tại)
        segments["evolving_interest"] = False
    else:
        segments["evolving_interest"] = False

    return segments.reset_index()
