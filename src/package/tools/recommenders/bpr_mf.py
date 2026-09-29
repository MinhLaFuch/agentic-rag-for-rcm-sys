from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .base import Recommender


class BPRMFRecommender(Recommender):
    name = "bpr_mf"

    def __init__(
        self,
        embedding_dim: int = 64,
        learning_rate: float = 0.05,
        reg: float = 0.01,
        epochs: int = 20,
        batch_size: int = 2048,
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim
        self.learning_rate = learning_rate
        self.reg = reg
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.user_factors: np.ndarray | None = None
        self.item_factors: np.ndarray | None = None
        self.item_bias: np.ndarray | None = None
        self.loss_history: list[float] = []

    def _sample_negatives(self, rng, users: np.ndarray, pos_keys: np.ndarray) -> np.ndarray:
        """Lấy mẫu item âm, cố tránh trùng item user đã tương tác (rejection tối đa 3 vòng)."""
        num_items = self.num_items
        neg = rng.integers(0, num_items, size=len(users))
        for _ in range(3):
            keys = users.astype(np.int64) * num_items + neg
            idx = np.searchsorted(pos_keys, keys)
            idx[idx >= len(pos_keys)] = len(pos_keys) - 1
            clash = pos_keys[idx] == keys
            if not clash.any():
                break
            neg[clash] = rng.integers(0, num_items, size=int(clash.sum()))
        return neg

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        rng = np.random.default_rng(self.seed)
        num_users, num_items, d = self.num_users, self.num_items, self.embedding_dim

        coo = train_matrix.tocoo()
        users_all = coo.row.astype(np.int64)
        items_all = coo.col.astype(np.int64)
        n = len(users_all)
        if n == 0:
            raise ValueError("Cannot fit BPR-MF on an empty interaction matrix")

        pos_keys = np.sort(users_all * num_items + items_all)

        self.user_factors = rng.normal(0, 0.1, (num_users, d)).astype(np.float32)
        self.item_factors = rng.normal(0, 0.1, (num_items, d)).astype(np.float32)
        self.item_bias = np.zeros(num_items, dtype=np.float32)
        self.loss_history = []

        lr, reg = self.learning_rate, self.reg
        P, Q, b = self.user_factors, self.item_factors, self.item_bias

        for _ in range(self.epochs):
            order = rng.permutation(n)
            epoch_loss = 0.0
            for start in range(0, n, self.batch_size):
                sel = order[start : start + self.batch_size]
                u, i = users_all[sel], items_all[sel]
                j = self._sample_negatives(rng, u, pos_keys)

                pu, qi, qj = P[u], Q[i], Q[j]
                x = b[i] - b[j] + np.sum(pu * (qi - qj), axis=1)
                coeff = (1.0 / (1.0 + np.exp(np.clip(x, -30, 30)))).astype(np.float32)  # sigmoid(-x)
                epoch_loss += float(np.logaddexp(0.0, -x).sum())

                c = coeff[:, None]
                np.add.at(P, u, lr * (c * (qi - qj) - reg * pu))
                np.add.at(Q, i, lr * (c * pu - reg * qi))
                np.add.at(Q, j, lr * (-c * pu - reg * qj))
                np.add.at(b, i, lr * (coeff - reg * b[i]))
                np.add.at(b, j, lr * (-coeff - reg * b[j]))

            self.loss_history.append(epoch_loss / n)

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        assert self.user_factors is not None and self.item_factors is not None
        return self.user_factors[user_idxs] @ self.item_factors.T + self.item_bias[None, :]
