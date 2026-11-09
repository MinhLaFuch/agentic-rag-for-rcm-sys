from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ..shared.recommender import Recommender


class PopularityMatrixRecommender(Recommender):
    name = "popularity"

    def __init__(self) -> None:
        super().__init__()
        self.item_counts: np.ndarray | None = None

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        self.item_counts = np.asarray(train_matrix.sum(axis=0)).ravel().astype(np.float32)

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        assert self.item_counts is not None, "call fit() first"
        return np.broadcast_to(self.item_counts, (len(user_idxs), self.num_items))

    def _recommend_sparse(self, user_idxs, k, exclude):
        if type(self) is not PopularityMatrixRecommender:
            return None
        from ..shared.sparse_topk import sparse_topk
        return sparse_topk(user_idxs, k, exclude, self.num_items, self._get_popularity_order())
