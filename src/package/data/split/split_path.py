"""Single place that decides where a split file lives (used by load_splits, save_splits, scripts, DataPaths)."""

from __future__ import annotations

from pathlib import Path

from ._schema import SPLIT_NAMES

SPLIT_FILE_SUFFIX = ".parquet"


def split_path(splits_dir: str | Path, name: str) -> Path:
    """``<splits_dir>/<name>.parquet`` for name in SPLIT_NAMES."""
    if name not in SPLIT_NAMES:
        raise ValueError(f"unknown split {name!r}; expected one of {SPLIT_NAMES}")
    return Path(splits_dir) / f"{name}{SPLIT_FILE_SUFFIX}"
