"""k-core filtering: lặp loại user/item dưới ngưỡng interaction cho đến khi ổn định."""

from __future__ import annotations

import pandas as pd


def k_core_filter(
    interactions: pd.DataFrame,
    min_user_interactions: int,
    min_item_interactions: int,
    max_iterations: int = 20,
) -> pd.DataFrame:
    """
    Lặp lại việc loại user/item có ít hơn ngưỡng interaction cho đến khi
    ổn định (đúng khái niệm k-core filtering nêu ở configs/data/filtering.yaml).
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
