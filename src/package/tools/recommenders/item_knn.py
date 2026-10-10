from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .base import Recommender


class ItemKNNRecommender(Recommender):
    name = "item_knn"

    def __init__(self, k: int = 50, block_elements: int = 20_000_000) -> None:
        super().__init__()
        if k <= 0:
            raise ValueError("k must be positive")
        self.k = k
        self.block_elements = block_elements
        self.similarity: sp.csr_matrix | None = None  # (items x items), hàng i = láng giềng của i

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        num_items = self.num_items
        item_user = train_matrix.T.tocsr()  # items x users
        norms = np.sqrt(np.asarray(train_matrix.multiply(train_matrix).sum(axis=0)).ravel())
        norms[norms == 0] = 1.0

        k = min(self.k, max(1, num_items - 1))
        block = max(1, self.block_elements // max(1, num_items))

        rows, cols, vals = [], [], []
        for start in range(0, num_items, block):
            end = min(start + block, num_items)
            co = (item_user[start:end] @ train_matrix).toarray().astype(np.float32)  # (B, items)
            co /= norms[start:end, None]
            co /= norms[None, :]
            co[np.arange(end - start), np.arange(start, end)] = 0.0  # bỏ tự tương đồng

            if k < num_items:
                top = np.argpartition(co, num_items - k, axis=1)[:, num_items - k :]
            else:
                top = np.tile(np.arange(num_items), (end - start, 1))
            top_vals = np.take_along_axis(co, top, axis=1)
            keep = top_vals > 0
            r = np.repeat(np.arange(start, end), top.shape[1]).reshape(top.shape)
            rows.append(r[keep])
            cols.append(top[keep])
            vals.append(top_vals[keep])

        self.similarity = sp.csr_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(num_items, num_items),
            dtype=np.float32,
        )

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        assert self.similarity is not None and self.train_matrix is not None
        # score(u, i) = sum_{j in history(u)} sim(i, j), với sim đã cắt top-k
        history = self.train_matrix[user_idxs]
        return (history @ self.similarity.T).toarray().astype(np.float32)
