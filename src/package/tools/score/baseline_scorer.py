"""Baseline scorer implementation using popularity and item-item similarity."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import sparse


class BaselineScorer:
    """
    Adapts PopularityRecommender / ItemKNNRecommender to candidate scoring.
    ItemKNN score = summed neighbour similarity to the user's history, with a
    tiny popularity term to break ties (mirrors the popularity fallback in
    ItemKNNRecommender.recommend).  Users with no history get popularity only.
    """

    def __init__(self, model: Any) -> None:
        self.model = model
        self.name = type(model).__name__

        # Validate model has required attributes
        required_attrs = ["scores", "user_items", "num_items"]
        missing = [attr for attr in required_attrs if not hasattr(model, attr)]
        if missing:
            raise AttributeError(
                f"Model must have attributes {required_attrs}, missing: {missing}. "
                f"Expected a fitted PopularityRecommender or ItemKNNRecommender."
            )

        self.popularity: np.ndarray = model.scores
        self.user_items: sparse.csr_matrix = model.user_items
        similarity = getattr(model, "similarity", None)
        self.similarity = similarity.tocsr() if similarity is not None else None
        self.num_items = int(model.num_items)
        peak = float(self.popularity.max()) if self.num_items else 0.0
        self._pop_norm = self.popularity / peak if peak > 0 else self.popularity

    def is_known_user(self, user_idx: int) -> bool:
        return 0 <= user_idx < self.user_items.shape[0] and self.user_items.getrow(user_idx).nnz > 0

    def seen_items(self, user_idx: int) -> set[int]:
        if not 0 <= user_idx < self.user_items.shape[0]:
            return set()
        return set(self.user_items.getrow(user_idx).indices.tolist())

    def score(self, user_idx: int, item_idxs: np.ndarray) -> np.ndarray:
        item_idxs = np.asarray(item_idxs, dtype=np.int64)
        valid = (item_idxs >= 0) & (item_idxs < self.num_items)
        safe = np.where(valid, item_idxs, 0)
        scores = np.where(valid, self._pop_norm[safe] * 1e-6, 0.0)
        if self.similarity is not None and self.is_known_user(user_idx):
            cf = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
            scores = scores + np.where(valid, cf[:, safe].toarray().ravel(), 0.0)
        return scores

    def has_personal_signal(self, user_idx: int) -> bool:
        """Check if the user has any collaborative filtering signal (i.e., has history with neighbors)."""
        if self.similarity is None or not self.is_known_user(user_idx):
            return False
        # Check if the user's history has any CF signal (similarity > 0)
        cf = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
        return cf.nnz > 0
