"""
ID mapping: chuyển user_id/parent_asin gốc (string) thành integer index
liên tục (0..N-1) — cần cho hầu hết model (embedding lookup table).

Mapping phải được lưu lại (save_mappings/load_mappings) để đảm bảo
reproducibility — mục XXII yêu cầu lưu model version/data version, và
mapping chính là một phần của "data version" đó.
"""

from __future__ import annotations

import pandas as pd


def apply_id_mapping(
    df: pd.DataFrame, user2id: dict[str, int], item2id: dict[str, int]
) -> pd.DataFrame:
    """
    Thêm cột `user_idx`, `item_idx`. Ném lỗi rõ ràng nếu gặp id không có
    trong mapping (không được âm thầm bỏ qua — mục XXVIII).
    """
    unknown_users = set(df["user_id"]) - set(user2id.keys())
    unknown_items = set(df["parent_asin"]) - set(item2id.keys())
    if unknown_users or unknown_items:
        raise ValueError(
            f"Found {len(unknown_users)} unknown user_id and "
            f"{len(unknown_items)} unknown parent_asin not present in mapping. "
            "Rebuild mapping from the full dataset before applying."
        )

    out = df.copy()
    out["user_idx"] = out["user_id"].map(user2id)
    out["item_idx"] = out["parent_asin"].map(item2id)
    return out
