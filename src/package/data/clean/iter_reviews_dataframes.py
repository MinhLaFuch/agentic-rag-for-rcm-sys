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
