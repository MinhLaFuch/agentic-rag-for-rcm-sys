"""Đọc toàn bộ file review .jsonl.gz thành một DataFrame (chỉ dùng khi vừa RAM)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


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
