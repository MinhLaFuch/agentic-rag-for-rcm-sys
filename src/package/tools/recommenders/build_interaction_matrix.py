from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def build_interaction_matrix(interactions: pd.DataFrame, num_users: int, num_items: int) -> sparse.csr_matrix:
    """Build a user-item interaction matrix from a DataFrame with user_idx and item_idx columns."""
    users = interactions["user_idx"].to_numpy(dtype=np.int64)
    items = interactions["item_idx"].to_numpy(dtype=np.int64)
    matrix = sparse.csr_matrix(
        (np.ones(len(interactions), dtype=np.float32), (users, items)),
        shape=(num_users, num_items),
    )
    matrix.data[:] = 1.0  # binary implicit-feedback matrix
    matrix.eliminate_zeros()
    return matrix
