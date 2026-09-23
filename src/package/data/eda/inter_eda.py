
from __future__ import annotations

import pandas as pd
from .inter_stat import InteractionStats

def inter_eda(interactions: pd.DataFrame) -> InteractionStats:
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
