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

        Note:
        - Items với điểm -inf (e.g., excluded items) không được trả về.
        - Nếu ít hơn k item có điểm hợp lệ, kết quả sẽ ngắn hơn k (padding với -1).
        - Tie-break: khi điểm bằng nhau, ưu tiên item_idx nhỏ hơn (đeterministic).
        - Khi toàn bộ điểm là 0 (không có tín hiệu cá nhân), dùng popularity làm tie-break.
        - Sử dụng float32 cho scores để tiết kiệm memory (matrix sparse cũng float32).
          float64 có thể tăng precision nhưng tốn 2x memory. Thêm tie-breaker rất nhỏ (1e-10)
          để đảm bảo determinism trong float32.
        """
        if k <= 0 or k > self.num_items:
            raise ValueError(f"k must be in [1, num_items={self.num_items}], got {k}")

        scores = np.array(self.score_batch(user_idxs), dtype=np.float32, copy=True)

        if exclude is not None:
            rows, cols = exclude[user_idxs].nonzero()
            scores[rows, cols] = -np.inf

        # Nếu toàn bộ điểm là 0 (không có tín hiệu cá nhân), dùng popularity làm tie-break
        # Tính popularity từ train_matrix (số tương tác mỗi item)
        popularity = np.asarray(self.train_matrix.sum(axis=0)).ravel()
        all_zero = (scores == 0).all(axis=1)
        if all_zero.any():
            # Thêm popularity nhỏ để tie-break mà không làm thay đổi thứ tự quá nhiều
            scores[all_zero] += popularity * 1e-6

        n = scores.shape[1]
        # Add tiny tie-breaker by item_idx for determinism when scores are equal
        # This makes ranking stable without full argsort (O(n log n) -> O(n))
        tie_breaker = np.arange(n, dtype=np.float32) * 1e-10
        scores_with_tie = scores + tie_breaker[None, :]

        top = np.argpartition(scores_with_tie, n - k, axis=1)[:, n - k :]
        top_scores = np.take_along_axis(scores_with_tie, top, axis=1)
        order = np.argsort(-top_scores, axis=1, kind="stable")
        ranked = np.take_along_axis(top, order, axis=1)

        # Filter out -inf items (excluded or invalid)
        valid_mask = scores[np.arange(len(user_idxs))[:, None], ranked] > -np.inf
        result = np.full((len(user_idxs), k), -1, dtype=np.int64)
        for i in range(len(user_idxs)):
            valid_items = ranked[i][valid_mask[i]]
            result[i, :len(valid_items)] = valid_items

        return result
