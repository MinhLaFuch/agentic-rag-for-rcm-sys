from __future__ import annotations

import numpy as np
import pandas as pd

from ._helper import _append_popular_unseen, _keep_top_neighbors
from .baseline_popularity import PopularityRecommender


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
