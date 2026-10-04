from __future__ import annotations

import pandas as pd


def infer_matrix_shape(*frames: pd.DataFrame) -> tuple[int, int]:
    """(num_users, num_items) t? index l?n nh?t trong c�c split."""
    num_users = int(max(f["user_idx"].max() for f in frames)) + 1
    num_items = int(max(f["item_idx"].max() for f in frames)) + 1
    return num_users, num_items
