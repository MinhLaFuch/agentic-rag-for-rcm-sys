"""Gắn cột domain và đổi parent_asin sang dạng namespace 'Domain::asin'."""

from __future__ import annotations

import pandas as pd

from .namespaced_item_id import namespaced_item_id


def tag_domain(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """
    Gắn domain vào một DataFrame interaction đã clean (có cột
    user_id, parent_asin, rating, timestamp):
      - thêm cột `domain`
      - thêm cột `original_item_id` (giữ giá trị parent_asin gốc, để
        truy vết ngược lại metadata gốc của domain đó)
      - overwrite `parent_asin` thành item id đã namespace

    `user_id` GIỮ NGUYÊN: cùng một user xuất hiện ở nhiều domain vẫn là một user (đây là lý do gộp domain giảm cold-start).
    """
    if "parent_asin" not in df.columns:
        raise ValueError("DataFrame must have a 'parent_asin' column")

    # A deep copy plus Series.apply creates one Python string object per event. On
    # tens of millions of rows that temporarily needs several GB. Keep the frame
    # shallow, encode repeated IDs once as categories, and namespace only the
    # distinct category labels. Assignment replaces columns on `out` without
    # changing the caller's DataFrame.
    out = df.copy(deep=False)
    original_item_ids = df["parent_asin"].astype("category")
    out["original_item_id"] = original_item_ids
    out["parent_asin"] = original_item_ids.cat.rename_categories(
        lambda item_id: namespaced_item_id(domain, str(item_id))
    )
    out["domain"] = pd.Categorical([domain] * len(df), categories=[domain])
    return out
