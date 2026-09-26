"""
Load + clean interaction data thật (Phase 3, mục V).

Dùng pandas.read_json(lines=True) — đọc trực tiếp .jsonl.gz, không cần
tự viết streaming parser (đơn giản hơn, và pandas xử lý gzip built-in).
Với ~4.6M dòng x 8 cột, DataFrame chiếm vài trăm MB RAM — chấp nhận được
trên máy dev thông thường. Nếu OOM trên máy yếu, xem ghi chú ở cuối file.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["user_id", "parent_asin", "rating", "timestamp"]
OPTIONAL_COLUMNS = ["title", "text", "helpful_vote", "verified_purchase"]


def load_reviews_dataframe(
    path: str | Path, columns: list[str] | None = None
) -> pd.DataFrame:
    """
    Đọc file review .jsonl.gz thật thành DataFrame.

    columns: nếu chỉ cần một phần cột (ví dụ chỉ cần
    REQUIRED_COLUMNS để giảm RAM cho bước filtering/split), truyền vào
    đây; mặc định đọc toàn bộ cột có sẵn.
    """
    df = pd.read_json(path, lines=True, compression="infer", convert_dates=False)
    if columns is not None:
        missing = set(columns) - set(df.columns)
        if missing:
            raise ValueError(f"Requested columns not found in file: {missing}")
        df = df[columns]
    return df


def iter_reviews_dataframes(
    path: str | Path, *, columns: list[str] | None = None, chunksize: int
) -> Iterator[pd.DataFrame]:
    """Yield review rows in bounded-size DataFrames.

    ``pandas.read_json`` still parses each JSON object, but using ``chunksize``
    prevents the complete source file from being retained in one DataFrame.
    This is intended for very large domains such as Electronics.
    """
    if chunksize <= 0:
        raise ValueError("chunksize must be a positive integer")

    reader = pd.read_json(
        path,
        lines=True,
        compression="infer",
        convert_dates=False,
        chunksize=chunksize,
    )
    for df in reader:
        if columns is not None:
            missing = set(columns) - set(df.columns)
            if missing:
                raise ValueError(f"Requested columns not found in file: {missing}")
            df = df[columns]
        yield df


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
