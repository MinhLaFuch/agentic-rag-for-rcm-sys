"""Non-neural recommendation baselines used in Phase 4."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def _append_popular_unseen(
    selected: list[int], ranked_items: np.ndarray, seen: set[int], top_k: int
) -> list[int]:
    """Fill a ranking from the cached global popularity order without dense scores."""
    selected_set = set(selected)
    for item in ranked_items:
        item = int(item)
        if item not in seen and item not in selected_set:
            selected.append(item)
            selected_set.add(item)
            if len(selected) == top_k:
                break
    return selected


class PopularityRecommender:
    """Ranks items by their interaction frequency in the fitting period."""

    def fit(self, interactions: pd.DataFrame) -> "PopularityRecommender":
        self.num_items = int(interactions["item_idx"].max()) + 1
        self.scores = np.bincount(
            interactions["item_idx"].to_numpy(dtype=np.int64), minlength=self.num_items
        ).astype(np.float64)
        self.ranked_items = np.argsort(-self.scores, kind="stable")
        self.user_items = _user_item_matrix(interactions, self.num_items)
        return self

    def recommend(self, user_idx: int, top_k: int) -> list[int]:
        seen = (
            set(self.user_items.getrow(user_idx).indices.tolist())
            if 0 <= user_idx < self.user_items.shape[0]
            else set()
        )
        return _append_popular_unseen([], self.ranked_items, seen, top_k)


def _user_item_matrix(interactions: pd.DataFrame, num_items: int) -> sparse.csr_matrix:
    users = interactions["user_idx"].to_numpy(dtype=np.int64)
    items = interactions["item_idx"].to_numpy(dtype=np.int64)
    num_users = int(users.max()) + 1
    matrix = sparse.csr_matrix(
        (np.ones(len(interactions), dtype=np.float32), (users, items)),
        shape=(num_users, num_items),
    )
    matrix.data[:] = 1.0  # binary implicit-feedback matrix
    matrix.eliminate_zeros()
    return matrix


class ItemKNNRecommender(PopularityRecommender):
    """Cosine item-item KNN over implicit user-item interactions.

    This is an exact sparse baseline.  Its item-item matrix can be large on a
    multi-domain dataset, so the command-line runner makes it opt-in.
    """

    def __init__(self, neighbors: int = 20) -> None:
        if neighbors <= 0:
            raise ValueError("neighbors must be positive")
        self.neighbors = neighbors

    def fit(self, interactions: pd.DataFrame) -> "ItemKNNRecommender":
        super().fit(interactions)
        cooccurrence = (self.user_items.T @ self.user_items).tocsr()
        cooccurrence.setdiag(0)
        cooccurrence.eliminate_zeros()

        norms = np.sqrt(self.user_items.getnnz(axis=0)).astype(np.float32)
        rows = np.repeat(np.arange(cooccurrence.shape[0]), np.diff(cooccurrence.indptr))
        cooccurrence.data /= norms[rows] * norms[cooccurrence.indices]
        self.similarity = _keep_top_neighbors(cooccurrence, self.neighbors)
        return self

    def recommend(self, user_idx: int, top_k: int) -> list[int]:
        if not 0 <= user_idx < self.user_items.shape[0]:
            return super().recommend(user_idx, top_k)
        history = self.user_items.getrow(user_idx)
        if history.nnz == 0:
            return super().recommend(user_idx, top_k)
        candidate_scores = (history @ self.similarity).tocsr()
        seen = set(history.indices.tolist())
        candidates = [
            (float(score), int(item))
            for item, score in zip(candidate_scores.indices, candidate_scores.data)
            if int(item) not in seen
        ]
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        selected = [item for _, item in candidates[:top_k]]
        # A popularity fallback gives recommendations when no neighbour scores an item.
        return _append_popular_unseen(selected, self.ranked_items, seen, top_k)


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
