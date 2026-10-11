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
        - Khi toàn bộ điểm hợp lệ là 0 (không có tín hiệu cá nhân), dùng popularity làm tie-break.
        - Sử dụng float32 cho scores để tiết kiệm memory (matrix sparse cũng float32).
        """
        # Validate k
        if not isinstance(k, int) or k <= 0 or k > self.num_items:
            raise ValueError(f"k must be in [1, num_items={self.num_items}], got {k}")

        # Validate user_idxs
        if not isinstance(user_idxs, np.ndarray):
            raise TypeError("user_idxs must be a numpy array")
        if user_idxs.ndim != 1:
            raise ValueError("user_idxs must be 1-dimensional")
        if len(user_idxs) == 0:
            raise ValueError("user_idxs cannot be empty")
        if np.any(user_idxs < 0) or np.any(user_idxs >= self.num_users):
            raise ValueError(
                f"user_idxs must be in [0, num_users={self.num_users}), "
                f"got out-of-range indices"
            )

        scores = np.array(self.score_batch(user_idxs), dtype=np.float32, copy=True)

        if exclude is not None:
            rows, cols = exclude[user_idxs].nonzero()
            scores[rows, cols] = -np.inf

        # Nếu toàn bộ điểm hợp lệ là 0 (không có tín hiệu cá nhân), dùng popularity làm tie-break
        # Tính popularity từ train_matrix (số tương tác mỗi item)
        popularity = np.asarray(self.train_matrix.sum(axis=0)).ravel()
        # Check only non-excluded items for all-zero condition
        if exclude is not None:
            # Mask out excluded items when checking for all-zero
            valid_mask = scores > -np.inf
            # Use valid_mask to zero out excluded scores before checking
            scores_masked = np.where(valid_mask, scores, 0.0)
            all_zero_valid = np.where(
                valid_mask.any(axis=1),
                (scores_masked == 0).all(axis=1),
                False
            )
        else:
            all_zero_valid = (scores == 0).all(axis=1)

        if all_zero_valid.any():
            # Thêm popularity nhỏ để tie-break mà không làm thay đổi thứ tự quá nhiều
            scores[all_zero_valid] += popularity * 1e-6

        n = scores.shape[1]
        # Create mask for valid (non -inf) items
        valid_mask = scores > -np.inf
        # Fill -inf with very negative value so they sort to the end when inverted
        scores_safe = np.where(valid_mask, scores, -1e30)

        # Use lexsort to break ties by score (descending) then item_idx (ascending)
        # This ensures determinism without relying on epsilon addition
        # Create inverted scores for descending order
        inv_scores = -scores_safe
        # lexsort sorts by last key first, so item_idx first, then score
        # Use item_idx as secondary key (smaller index = higher priority)
        item_indices = np.arange(n)

        # Use lexsort on each row - this is still a loop but lexsort is efficient
        ranked = np.zeros((len(user_idxs), k), dtype=np.int64)
        for i in range(len(user_idxs)):
            # Get indices sorted by (score descending, item_idx ascending)
            sorted_indices = np.lexsort((item_indices, inv_scores[i]))
            # Take top k
            ranked[i] = sorted_indices[:k]

        # Filter out -inf items (excluded or invalid)
        valid_mask_result = scores[np.arange(len(user_idxs))[:, None], ranked] > -np.inf
        result = np.full((len(user_idxs), k), -1, dtype=np.int64)
        for i in range(len(user_idxs)):
            valid_items = ranked[i][valid_mask_result[i]]
            result[i, :len(valid_items)] = valid_items

        return result
