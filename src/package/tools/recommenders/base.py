from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import scipy.sparse as sp


class Recommender(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.num_users = 0
        self.num_items = 0
        self.train_matrix: sp.csr_matrix | None = None

    def fit(self, train_matrix: sp.csr_matrix) -> "Recommender":
        self.train_matrix = train_matrix.tocsr()
        self.num_users, self.num_items = train_matrix.shape
        self._fit(self.train_matrix)
        return self

    @abstractmethod
    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        raise NotImplementedError

    @abstractmethod
    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        """Trả về mảng (len(user_idxs), num_items) — điểm càng cao càng nên gợi ý."""
        raise NotImplementedError

    def history_sizes(self, user_idxs: np.ndarray) -> np.ndarray:
        """Số tương tác trong dữ liệu fit của từng user (dùng cho phân đoạn cold/sparse/warm)."""
        assert self.train_matrix is not None, "call fit() first"
        return np.diff(self.train_matrix.indptr)[user_idxs]

    def recommend(
        self,
        user_idxs: np.ndarray,
        k: int,
        exclude: sp.csr_matrix | None = None,
    ) -> np.ndarray:
        """
        Top-k item cho mỗi user, đã loại item trong `exclude` (thường là
        toàn bộ lịch sử đã thấy). Trả về (len(user_idxs), k) đã sắp giảm dần theo điểm.
        """
        if k <= 0 or k > self.num_items:
            raise ValueError(f"k must be in [1, num_items={self.num_items}], got {k}")

        scores = np.array(self.score_batch(user_idxs), dtype=np.float32, copy=True)

        if exclude is not None:
            rows, cols = exclude[user_idxs].nonzero()
            scores[rows, cols] = -np.inf

        n = scores.shape[1]
        top = np.argpartition(scores, n - k, axis=1)[:, n - k :]
        top_scores = np.take_along_axis(scores, top, axis=1)
        order = np.argsort(-top_scores, axis=1, kind="stable")
        return np.take_along_axis(top, order, axis=1)
