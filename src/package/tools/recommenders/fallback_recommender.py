from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .recommender import Recommender


class FallbackRecommender(Recommender):
    def __init__(self, primary: Recommender, fallback: Recommender) -> None:
        super().__init__()
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}+{fallback.name}_fallback"

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        self.primary.fit(train_matrix)
        self.fallback.fit(train_matrix)

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        scores = np.array(self.primary.score_batch(user_idxs), dtype=np.float32, copy=True)
        cold = self.history_sizes(user_idxs) == 0
        if cold.any():
            scores[cold] = self.fallback.score_batch(user_idxs[cold])
        return scores

    def _recommend_sparse(self, user_idxs, k, exclude):
        from .item_knn_matrix_recommender import ItemKNNMatrixRecommender
        from .popularity_matrix_recommender import PopularityMatrixRecommender
        if type(self.primary) is ItemKNNMatrixRecommender and type(self.fallback) is PopularityMatrixRecommender:
            return self.primary._recommend_sparse(user_idxs, k, exclude)
        return None
