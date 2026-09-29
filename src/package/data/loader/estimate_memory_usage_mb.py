"""
Tối ưu dtype cho interaction DataFrame để giảm RAM (mục XXVI — code phải
scale được, không chỉ "chạy được trên máy Claude").

pandas mặc định lưu string dưới dạng object dtype — rất tốn RAM khi có
hàng triệu dòng với giá trị lặp lại nhiều (ví dụ 137K item lặp lại
trung bình 33 lần trong 4.6M dòng). Chuyển sang `category` dtype giúp
pandas chỉ lưu mỗi giá trị unique 1 lần + mảng index nhỏ, giảm RAM đáng
kể (thường 40-70% tuỳ cardinality).
"""

from __future__ import annotations

import pandas as pd


def estimate_memory_usage_mb(df: pd.DataFrame) -> float:
    """Ước lượng RAM thật sự dùng (deep=True để tính cả nội dung string/category)."""
    return df.memory_usage(deep=True).sum() / (1024 * 1024)
