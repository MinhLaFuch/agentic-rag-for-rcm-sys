from __future__ import annotations

import pandas as pd


def optimize_interaction_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Downcast dtype cho DataFrame interaction:
      - user_id, parent_asin (nếu có) -> category
      - rating -> float32 (thay vì float64 mặc định)
      - timestamp: GIỮ NGUYÊN int64 (timestamp ms epoch vượt phạm vi
        int32, downcast sai sẽ làm sai lệch mọi phép so sánh thời gian)

    Trả về DataFrame mới (không sửa inplace, để tránh side-effect khó
    debug).
    """
    df = df.copy()

    for col in ("user_id", "parent_asin", "domain", "original_item_id"):
        if col in df.columns:
            df[col] = df[col].astype("category")

    if "rating" in df.columns:
        df["rating"] = df["rating"].astype("float32")

    return df


def estimate_memory_usage_mb(df: pd.DataFrame) -> float:
    """Ước lượng RAM thật sự dùng (deep=True để tính cả nội dung string/category)."""
    return df.memory_usage(deep=True).sum() / (1024 * 1024)
