"""
EDA functions cho interaction data (Phase 2, mục V/VI/XVIII).

Các hàm ở đây là pure function trên pandas DataFrame, KHÔNG tự tải dữ
liệu — vì vậy có thể unit test bằng dữ liệu synthetic (để verify logic
đúng), tách biệt hoàn toàn với việc dữ liệu thật có tải được hay không
(xem src/data/acquire.py — hiện đang BLOCKED do network).
"""

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
    ổn định (đúng khái niệm k-core filtering nêu ở configs/filtering.yaml).
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
