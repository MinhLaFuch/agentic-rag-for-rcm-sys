"""Helper functions for recommenders module."""

from __future__ import annotations

import numpy as np
from scipy import sparse

from .build_interaction_matrix import build_interaction_matrix


def _append_popular_unseen(
    selected: list[int], ranked_items: np.ndarray, seen: set[int], top_k: int
) -> list[int]:
    """Fill a ranking from the cached global popularity order without dense scores."""
    if len(selected) >= top_k:  # already full: without this the loop below appends EVERY remaining item
        return selected[:top_k]
    selected_set = set(selected)
    for item in ranked_items:
        item = int(item)
        if item not in seen and item not in selected_set:
            selected.append(item)
            selected_set.add(item)
            if len(selected) == top_k:
                break
    return selected


def _user_item_matrix(interactions, num_items: int) -> sparse.csr_matrix:
    """Binary user-item matrix whose user dimension is inferred from the largest user_idx."""
    return build_interaction_matrix(interactions, int(interactions["user_idx"].max()) + 1, num_items)


def _keep_top_neighbors(matrix: sparse.csr_matrix, neighbors: int) -> sparse.csr_matrix:
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    values: list[np.ndarray] = []
    for row in range(matrix.shape[0]):
        start, end = matrix.indptr[row], matrix.indptr[row + 1]
        if end <= start:
            continue
        row_values = matrix.data[start:end]
        row_cols = matrix.indices[start:end]
        take = min(neighbors, len(row_values))
        keep = np.argpartition(row_values, -take)[-take:]
        rows.append(np.full(take, row, dtype=np.int64))
        cols.append(row_cols[keep])
        values.append(row_values[keep])
    if not rows:
        return sparse.csr_matrix(matrix.shape, dtype=np.float32)
    return sparse.csr_matrix(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
        shape=matrix.shape,
    )
