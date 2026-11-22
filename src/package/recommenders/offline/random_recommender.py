from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ..shared.recommender import Recommender


class RandomRecommender(Recommender):
    name = "random"

    def __init__(self, seed: int = 42) -> None:
        super().__init__()
        self._rng = np.random.default_rng(seed)

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        pass

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        return self._rng.random((len(user_idxs), self.num_items), dtype=np.float32)

    def _recommend_sparse(self, user_idxs, k, exclude):
        """Top-k of iid random scores is a uniform random k-subset of the
        non-excluded items — sample it directly instead of materialising
        (users x num_items) scores, which made dense evaluation infeasible."""
        if type(self) is not RandomRecommender:
            return None
        rng = self._rng
        n_items = self.num_items
        users = np.asarray(user_idxs, dtype=np.int64).ravel()
        excl: dict[int, set[int]] = {}
        if exclude is not None:
            ex = exclude[users].tocoo()
            nz = ex.data != 0  # match nonzero() semantics: stored zeros don't exclude
            for r, c in zip(ex.row[nz].tolist(), ex.col[nz].tolist()):
                excl.setdefault(int(r), set()).add(int(c))
        out = np.full((len(users), k), -1, dtype=np.int64)
        for i in range(len(users)):
            banned = excl.get(i, set())
            chosen: list[int] = []
            seen = set(banned)
            # Rejection sampling; collisions are rare (history << catalog).
            for _ in range(50):
                if len(chosen) >= k:
                    break
                for c in rng.integers(0, n_items, size=max(8, 2 * (k - len(chosen)))):
                    ci = int(c)
                    if ci not in seen:
                        seen.add(ci)
                        chosen.append(ci)
                        if len(chosen) >= k:
                            break
            out[i, : len(chosen)] = chosen[:k]
        return out
