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

    out = df.copy()
    out["domain"] = domain
    out["original_item_id"] = out["parent_asin"]
    out["parent_asin"] = out["parent_asin"].apply(lambda x: namespaced_item_id(domain, x))
    return out
