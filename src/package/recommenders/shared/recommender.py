from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .build_interaction_matrix import build_interaction_matrix


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


def _topk_row_exact(row: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k largest values in ``row``, ties broken by lower index.

    Equivalent to ``np.lexsort((arange(n), -row))[:k]`` but O(n): the k-th
    largest value partitions the row; items strictly above it are all in, and
    the remaining slots go to the lowest-indexed items tied at the threshold.
    """
    n = row.shape[0]
    k = min(k, n)
    if k == n:
        return np.lexsort((np.arange(n), -row))
    thr = np.partition(row, n - k)[n - k]
    gt = np.flatnonzero(row > thr)
    eq = np.flatnonzero(row == thr)
    sel = np.concatenate([gt, eq[: k - len(gt)]])
    return sel[np.lexsort((sel, -row[sel]))]


def _topk_indices(scores: np.ndarray, k: int) -> np.ndarray:
    """Vectorised exact top-k for a (rows, n) score matrix.

    Fast path: ``argpartition`` picks k candidates per row; a row is recomputed
    exactly only when its boundary (k-th) score is tied — i.e. equal-score
    items exist that were left out, where argpartition's arbitrary choice
    could differ from the (score desc, index asc) contract.
    """
    b, n = scores.shape
    k = min(k, n)
    part = np.argpartition(-scores, k - 1, axis=1)[:, :k]
    cand_scores = np.take_along_axis(scores, part, 1)
    ranked = np.empty((b, k), dtype=np.int64)
    for i in range(b):
        smin = cand_scores[i].min()
        sel_eq = int((cand_scores[i] == smin).sum())
        if int((scores[i] == smin).sum()) > sel_eq:
            ranked[i] = _topk_row_exact(scores[i], k)
        else:
            order = np.lexsort((part[i], -cand_scores[i]))
            ranked[i] = part[i][order]
    return ranked


class Recommender(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.num_users = 0
        self.num_items = 0
        self.train_matrix: sp.csr_matrix | None = None

    def fit(self, train_matrix: sp.csr_matrix | pd.DataFrame) -> "Recommender":
        if isinstance(train_matrix, pd.DataFrame):
            if not {"user_idx", "item_idx"}.issubset(train_matrix.columns):
                raise ValueError("DataFrame input for fit() must include user_idx and item_idx columns")
            num_users = int(train_matrix["user_idx"].max()) + 1 if not train_matrix.empty else 0
            num_items = int(train_matrix["item_idx"].max()) + 1 if not train_matrix.empty else 0
            train_matrix = build_interaction_matrix(train_matrix, num_users, num_items)
        self.__dict__.pop("history_matrix", None)
        self.__dict__.pop("_popularity_order", None)
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
        return np.diff(getattr(self, "history_matrix", self.train_matrix).indptr)[user_idxs]

    def recommend(
        self,
        user_idxs: int | np.ndarray,
        k: int,
        exclude: sp.csr_matrix | None = None,
    ) -> np.ndarray | list[int]:
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

        scalar = isinstance(user_idxs, (int, np.integer)) and not isinstance(user_idxs, (bool, np.bool_))
        if scalar:
            user_idxs = np.asarray([int(user_idxs)], dtype=np.int64)
        else:
            if not isinstance(user_idxs, np.ndarray):
                raise TypeError("user_idxs must be a numpy array or integer")
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

        fast = self._recommend_sparse(user_idxs, k, exclude)
        if fast is not None:
            return fast[0].tolist() if scalar else fast

        fused = self._recommend_topk(user_idxs, k, exclude)
        if fused is not None:
            return fused[0].tolist() if scalar else fused

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

        # Exact top-k by (score desc, item_idx asc) in O(n) per row:
        # argpartition selects the k largest scores; rows whose boundary score
        # is tied (equal-score items were left out) are recomputed exactly.
        # Replaces a per-row lexsort over the full catalog — O(n log n) — that
        # dominated dense-model evaluation time.
        ranked = _topk_indices(scores_safe, k)

        # Filter out -inf items (excluded or invalid)
        valid_mask_result = scores[np.arange(len(user_idxs))[:, None], ranked] > -np.inf
        result = np.full((len(user_idxs), k), -1, dtype=np.int64)
        for i in range(len(user_idxs)):
            valid_items = ranked[i][valid_mask_result[i]]
            result[i, :len(valid_items)] = valid_items

        if scalar:
            return result[0].tolist()
        return result

    def _recommend_sparse(self, user_idxs, k, exclude):
        return None

    def _recommend_topk(self, user_idxs, k, exclude):
        """Optional fused top-k hook for models that can rank without
        materialising the full (users x items) score matrix (e.g. torch on
        CUDA). Must return the same (len(user_idxs), k) int64 contract as the
        dense path, or None to fall through to score_batch."""
        return None

    def _get_popularity_order(self):
        if not hasattr(self, "_popularity_order"):
            counts = np.asarray(self.train_matrix.sum(axis=0)).ravel().astype(np.float32)
            self._popularity_order = np.argsort(-counts, kind="stable")
        return self._popularity_order
