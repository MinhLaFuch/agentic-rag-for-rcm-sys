"""Đọc file review .jsonl.gz theo từng chunk DataFrame (không nạp hết vào RAM)."""

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
