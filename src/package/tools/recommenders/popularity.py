from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .base import Recommender


class PopularityRecommender(Recommender):
    name = "popularity"

    def __init__(self) -> None:
        super().__init__()
        self.item_counts: np.ndarray | None = None

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        self.item_counts = np.asarray(train_matrix.sum(axis=0)).ravel().astype(np.float32)

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        assert self.item_counts is not None, "call fit() first"
        return np.broadcast_to(self.item_counts, (len(user_idxs), self.num_items))
