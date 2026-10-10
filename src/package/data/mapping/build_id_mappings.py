"""Dựng user2id/item2id (id gốc -> index nguyên) từ toàn bộ interaction."""

from __future__ import annotations

import pandas as pd


def build_id_mappings(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    """
    Xây map từ user_id/parent_asin gốc -> integer index liên tục.
    Thứ tự gán index KHÔNG dựa vào timestamp (tránh rò rỉ thông tin thời
    gian vào chính index) — dùng thứ tự xuất hiện đầu tiên trong DataFrame
    (deterministic nếu DataFrame đã được sort ổn định từ trước).
    """
    unique_users = df["user_id"].drop_duplicates().tolist()
    unique_items = df["parent_asin"].drop_duplicates().tolist()

    user2id = {uid: idx for idx, uid in enumerate(unique_users)}
    item2id = {iid: idx for idx, iid in enumerate(unique_items)}
    return user2id, item2id
