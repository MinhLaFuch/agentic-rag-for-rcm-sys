"""
Load + clean interaction data thật (Phase 3, mục V).

Dùng pandas.read_json(lines=True) — đọc trực tiếp .jsonl.gz, không cần
tự viết streaming parser (đơn giản hơn, và pandas xử lý gzip built-in).
Với ~4.6M dòng x 8 cột, DataFrame chiếm vài trăm MB RAM — chấp nhận được
trên máy dev thông thường. Nếu OOM trên máy yếu, xem ghi chú ở cuối file.
"""

from __future__ import annotations

import pandas as pd
from .._config import REQUIRED_COLUMNS, OPTIONAL_COLUMNS

def clean_interactions(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Làm sạch interaction data (mục V):
      - loại dòng thiếu field bắt buộc (user_id, parent_asin, rating, timestamp)
      - loại duplicate (cùng user_id + parent_asin + timestamp)

    Trả về (df_cleaned, report) — report ghi rõ số lượng loại ở mỗi bước
    (yêu cầu "ghi log số lượng record trước/sau" ở mục IV data pipeline).
    """
    report: dict = {"num_input": len(df)}

    missing_required = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_required:
        raise ValueError(f"DataFrame missing required columns: {missing_required}")

    before_na = len(df)
    df = df.dropna(subset=REQUIRED_COLUMNS)
    report["num_dropped_missing_required_fields"] = before_na - len(df)

    before_dup = len(df)
    df = df.drop_duplicates(subset=["user_id", "parent_asin", "timestamp"])
    report["num_dropped_duplicates"] = before_dup - len(df)

    report["num_output"] = len(df)
    return df.reset_index(drop=True), report
