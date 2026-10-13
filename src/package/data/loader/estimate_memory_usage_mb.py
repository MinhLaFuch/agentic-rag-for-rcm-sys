"""Ước lượng RAM (MB) mà một DataFrame đang dùng."""

from __future__ import annotations

import pandas as pd


def estimate_memory_usage_mb(df: pd.DataFrame) -> float:
    """Ước lượng RAM thật sự dùng (deep=True để tính cả nội dung string/category)."""
    return df.memory_usage(deep=True).sum() / (1024 * 1024)
