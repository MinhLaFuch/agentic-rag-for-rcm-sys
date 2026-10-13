"""Thống kê số interaction / user / item theo từng domain của bảng đã gộp."""

from __future__ import annotations

import pandas as pd


def domain_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Thống kê nhanh số interaction/user/item theo từng domain — dùng cho report."""
    if "domain" not in df.columns:
        raise ValueError("DataFrame missing 'domain' column — chưa merge/tag đúng cách")

    return (
        df.groupby("domain")
        .agg(
            num_interactions=("user_id", "size"),
            num_users=("user_id", "nunique"),
            num_items=("parent_asin", "nunique"),
        )
        .reset_index()
    )
