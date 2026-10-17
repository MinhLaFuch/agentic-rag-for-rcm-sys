from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import scipy.sparse as sp


def _prepare_train_matrix(train_matrix) -> sp.csr_matrix:
    """Validate the training matrix and return a canonical CSR copy-if-needed (the caller's matrix is never mutated).

    Canonical = no duplicate entries and no stored zeros, so that ``indptr`` really counts a user's
    interactions (history_sizes, BPR negative sampling and user segments all rely on that).
    """
    if not sp.issparse(train_matrix):
        raise TypeError(f"train_matrix must be a scipy sparse matrix, got {type(train_matrix).__name__}")
    if train_matrix.ndim != 2:
        raise ValueError(f"train_matrix must be 2-dimensional, got ndim={train_matrix.ndim}")
    matrix = train_matrix.tocsr()
    if matrix.nnz:
        if not np.isfinite(matrix.data).all():
            raise ValueError("train_matrix contains NaN or infinite values")
        if (matrix.data < 0).any():
            raise ValueError("train_matrix must be non-negative (implicit feedback)")
    if not matrix.has_canonical_format or (matrix.nnz and (matrix.data == 0).any()):
        matrix = matrix.copy()
        matrix.sum_duplicates()
        matrix.eliminate_zeros()
    return matrix


class Recommender(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.num_users = 0
        self.num_items = 0
        self.train_matrix: sp.csr_matrix | None = None

    def fit(self, train_matrix: sp.csr_matrix) -> "Recommender":
        self.train_matrix = _prepare_train_matrix(train_matrix)
        self.num_users, self.num_items = self.train_matrix.shape
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
        - Khi toàn bộ điểm hợp lệ là 0 (không có tín hiệu cá nhân), dùng popularity làm điểm.
        - Sử dụng float32 cho scores để tiết kiệm memory (matrix sparse cũng float32).

        Contract (English summary):
        - Returns an int64 array of shape (len(user_idxs), k). ``-1`` is ONLY a padding sentinel
          (fewer than k recommendable items); callers must mask it before indexing anything.
        - ``exclude`` must be sparse with the same shape as the training matrix; its non-zero entries are
          never recommended.
        - A model that returns NaN scores is a bug, so it raises ValueError instead of silently dropping items.
        - The popularity fallback looks only at NON-excluded items, so a user whose remaining items all
          score 0 is still ranked by popularity (and excluded items stay excluded).
        """
        if self.train_matrix is None:
            raise RuntimeError("call fit() first")

        # Validate k (numpy integers are fine; bool is not a count)
        if isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) or k <= 0 or k > self.num_items:
            raise ValueError(f"k must be in [1, num_items={self.num_items}] and an integer, got {k!r}")
        k = int(k)

        # Validate user_idxs
        if not isinstance(user_idxs, np.ndarray):
            raise TypeError("user_idxs must be a numpy array")
        if user_idxs.ndim != 1:
            raise ValueError("user_idxs must be 1-dimensional")
        if len(user_idxs) == 0:
            raise ValueError("user_idxs cannot be empty")
        if not np.issubdtype(user_idxs.dtype, np.integer):
            raise TypeError(f"user_idxs must be an integer array, got dtype {user_idxs.dtype}")
        if np.any(user_idxs < 0) or np.any(user_idxs >= self.num_users):
            raise ValueError(
                f"user_idxs must be in [0, num_users={self.num_users}), "
                f"got out-of-range indices"
            )

        # Validate exclude
        if exclude is not None:
            if not sp.issparse(exclude):
                raise TypeError(f"exclude must be a scipy sparse matrix or None, got {type(exclude).__name__}")
            if exclude.shape != self.train_matrix.shape:
                raise ValueError(
                    f"exclude has shape {exclude.shape} but the training matrix has shape {self.train_matrix.shape}"
                )
            exclude = exclude.tocsr()

        scores = np.array(self.score_batch(user_idxs), dtype=np.float32, copy=True)
        if scores.shape != (len(user_idxs), self.num_items):
            raise ValueError(
                f"{self.name}.score_batch returned shape {scores.shape}, expected {(len(user_idxs), self.num_items)}"
            )
        if np.isnan(scores).any():
            raise ValueError(f"{self.name}.score_batch returned NaN scores; refusing to rank (is the model diverging?)")

        if exclude is not None:
            rows, cols = exclude[user_idxs].nonzero()
            scores[rows, cols] = -np.inf

        # Users with no personal signal (every NON-excluded score is 0) are ranked by popularity instead.
        valid = scores > -np.inf
        all_zero_valid = valid.any(axis=1) & np.where(valid, scores == 0, True).all(axis=1)
        if all_zero_valid.any():
            popularity = np.asarray(self.train_matrix.sum(axis=0)).ravel().astype(np.float32)
            rows = np.where(all_zero_valid)[0]
            scores[rows] = np.where(valid[rows], popularity[None, :], -np.inf)

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
