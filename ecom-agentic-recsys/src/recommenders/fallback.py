from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from src.recommenders.base import Recommender


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
