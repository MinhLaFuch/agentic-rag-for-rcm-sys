"""Dedupe interaction thô theo (user, item, timestamp) và kiểm tra cột bắt buộc; trả về (df sạch, báo cáo)."""

from __future__ import annotations

import pandas as pd
from .._schema import REQUIRED_COLUMNS

def clean_interactions(
    df: pd.DataFrame,
    *,
    validate_values: bool = False,
    min_timestamp_ms: int = 788918400000,
    max_timestamp_ms: int = 1704067200000,
    max_invalid_timestamp_fraction: float = 0.01,
    duplicate_keep: str = "last",
) -> tuple[pd.DataFrame, dict]:
    """
    Làm sạch interaction data (mục V):
      - loại dòng thiếu field bắt buộc (user_id, parent_asin, rating, timestamp)
      - khi validate_values=True, chỉ giữ rating [1, 5] và timestamp mili-giây trong [min, max)
      - loại duplicate theo (user_id, parent_asin, timestamp), mặc định giữ dòng hợp lệ cuối trong input
      - Stage 1 thực thi ngưỡng timestamp trên toàn file; ở đây tham số ngưỡng áp dụng cho batch được gọi

    Trả về (df_cleaned, report) — report ghi rõ số lượng loại ở mỗi bước
    (yêu cầu "ghi log số lượng record trước/sau" ở mục IV data pipeline).
    """
    report: dict = {"num_input": len(df)}

    missing_required = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_required:
        raise ValueError(f"DataFrame missing required columns: {missing_required}")
    if validate_values and (
        str(df["user_id"].dtype) != "string" or str(df["parent_asin"].dtype) != "string"
    ):
        raise TypeError("validated interactions require user_id and parent_asin to use pandas string dtype")

    missing = df[list(REQUIRED_COLUMNS)].isna().any(axis=1)
    report["num_dropped_missing_required_fields"] = int(missing.sum())
    df = df.loc[~missing].copy()

    report["num_dropped_invalid_rating"] = 0
    report["num_dropped_invalid_timestamp"] = 0
    if validate_values:
        if not 0 <= max_invalid_timestamp_fraction <= 1:
            raise ValueError("max_invalid_timestamp_fraction must be between 0 and 1")
        timestamp = pd.to_numeric(df["timestamp"], errors="coerce")
        invalid_timestamp = (
            timestamp.isna()
            | ~timestamp.between(min_timestamp_ms, max_timestamp_ms, inclusive="left")
            | (timestamp % 1 != 0)
        )
        invalid_count = int(invalid_timestamp.sum())
        report["num_dropped_invalid_timestamp"] = invalid_count
        invalid_fraction = invalid_count / max(1, int(report["num_input"]))
        if invalid_fraction > max_invalid_timestamp_fraction:
            raise ValueError(
                f"Invalid timestamp rows {invalid_count}/{report['num_input']} ({invalid_fraction:.2%}) "
                f"exceed configured maximum {max_invalid_timestamp_fraction:.2%}; "
                "possibly incorrect timestamp unit (expected milliseconds)."
            )
        df = df.loc[~invalid_timestamp].copy()
        df["timestamp"] = timestamp.loc[~invalid_timestamp].astype("int64")

        rating = pd.to_numeric(df["rating"], errors="coerce")
        invalid_rating = rating.isna() | ~rating.between(1, 5, inclusive="both")
        report["num_dropped_invalid_rating"] = int(invalid_rating.sum())
        df = df.loc[~invalid_rating].copy()
        df["rating"] = rating.loc[~invalid_rating]

    before_dup = len(df)
    # Source-order policy: for a duplicate key, keep the last valid row in this chunk.
    if duplicate_keep not in {"first", "last"}:
        raise ValueError("duplicate_keep must be 'first' or 'last'")
    df = df.drop_duplicates(subset=["user_id", "parent_asin", "timestamp"], keep=duplicate_keep)
    report["num_dropped_duplicates"] = before_dup - len(df)

    report["num_output"] = len(df)
    return df.reset_index(drop=True), report
