"""Ghi train/validation/test parquet (đối xứng với load_splits)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ._schema import SPLIT_NAMES
from .split_path import split_path


def save_splits(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame, splits_dir: str | Path
) -> Path:
    """Ghi 3 split vào ``splits_dir`` (tạo nếu chưa có) theo đúng thứ tự SPLIT_NAMES; trả về ``splits_dir``."""
    splits_dir = Path(splits_dir)
    splits_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(SPLIT_NAMES, (train, validation, test)):
        frame.to_parquet(split_path(splits_dir, name), index=False)
    return splits_dir
