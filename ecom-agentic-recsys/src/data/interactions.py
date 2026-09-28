
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp


def build_interaction_matrix(
    df: pd.DataFrame, num_users: int, num_items: int
) -> sp.csr_matrix:
    """
    Trả về CSR (num_users x num_items) nhị phân float32.
    Nhiều tương tác cùng (user, item) được gộp thành 1.
    """
    for col in ("user_idx", "item_idx"):
        if col not in df.columns:
            raise ValueError(f"DataFrame missing required column '{col}'")

    users = df["user_idx"].to_numpy(dtype=np.int64)
    items = df["item_idx"].to_numpy(dtype=np.int64)

    if len(users) and (users.max() >= num_users or items.max() >= num_items):
        raise ValueError("user_idx/item_idx vượt quá num_users/num_items đã khai báo")

    mat = sp.csr_matrix(
        (np.ones(len(users), dtype=np.float32), (users, items)),
        shape=(num_users, num_items),
    )
    mat.sum_duplicates()
    mat.data = np.ones_like(mat.data, dtype=np.float32)
    mat.sort_indices()
    return mat
