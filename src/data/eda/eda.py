
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import gzip
import json
from collections import Counter

@dataclass
class StreamingInteractionStats:
    
    num_interactions: int = 0
    num_users: int = 0
    num_items: int = 0
    timestamp_min: int | None = None
    timestamp_max: int | None = None
    rating_sum: float = 0.0
    interactions_per_user: dict = field(default_factory=dict)


def compute_interaction_stats_streaming(path: str | Path) -> "StreamingInteractionStats":

    user_counts: Counter = Counter()
    item_ids: set = set()
    stats = StreamingInteractionStats()

    review_path = Path(path)
    open_file = gzip.open if review_path.suffix == ".gz" else open

    with open_file(review_path, "rt", encoding="utf-8") as f:
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
