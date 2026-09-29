from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from src.recommenders.base import Recommender


class RandomRecommender(Recommender):
    name = "random"

    def __init__(self, seed: int = 42) -> None:
        super().__init__()
        self._rng = np.random.default_rng(seed)

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        pass

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        return self._rng.random((len(user_idxs), self.num_items), dtype=np.float32)
