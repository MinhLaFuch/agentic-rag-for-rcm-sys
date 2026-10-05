"""Đọc train/validation/test parquet do stage 3 ghi ra."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from ._config import SPLIT_NAMES

def load_splits(
    splits_dir: str | Path, columns: Sequence[str] = ("user_idx", "item_idx")
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Trả về (train, validation, test). Cột không có trong file bị bỏ qua (vd timestamp)."""
    splits_dir = Path(splits_dir)
    frames = []
    for name in SPLIT_NAMES:
        path = splits_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} không tồn tại — chạy stage3_map_split.sh trước.")
        available = set(pq.ParquetFile(path).schema.names)
        frames.append(pd.read_parquet(path, columns=[c for c in columns if c in available]))
    return frames[0], frames[1], frames[2]


def infer_matrix_shape(*frames: pd.DataFrame) -> tuple[int, int]:
    """(num_users, num_items) từ index lớn nhất trong các split."""
    num_users = int(max(f["user_idx"].max() for f in frames)) + 1
    num_items = int(max(f["item_idx"].max() for f in frames)) + 1
    return num_users, num_items
