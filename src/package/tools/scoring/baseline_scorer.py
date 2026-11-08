"""Baseline scorer implementation using popularity and item-item similarity."""

from __future__ import annotations

import math
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

    def __init__(self, model: Any, popularity_weight: float = 1e-6) -> None:
        self.model = model
        self.name = type(model).__name__
        if not np.isfinite(popularity_weight) or popularity_weight < 0:
            raise ValueError("popularity_weight must be a finite non-negative number")
        self.popularity_weight = float(popularity_weight)

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

        # Validate model consistency
        self._validate_model()

        peak = float(self.popularity.max()) if self.num_items else 0.0
        self._pop_norm = self.popularity / peak if peak > 0 else self.popularity

    def _validate_model(self) -> None:
        """Validate model invariants: shapes, finite values, and consistency."""
        # Check popularity shape matches num_items
        if len(self.popularity) != self.num_items:
            raise ValueError(
                f"Model popularity array has length {len(self.popularity)} "
                f"but num_items={self.num_items}. Inconsistent model state."
            )

        # Check popularity values are finite
        if not np.all(np.isfinite(self.popularity)):
            non_finite_count = np.sum(~np.isfinite(self.popularity))
            raise ValueError(
                f"Model popularity contains {non_finite_count} non-finite values (NaN or inf). "
                "Model must have finite popularity scores."
            )

        # Check user_items shape
        if self.user_items.shape[1] != self.num_items:
            raise ValueError(
                f"Model user_items has {self.user_items.shape[1]} columns "
                f"but num_items={self.num_items}. Inconsistent model state."
            )

        # Check similarity matrix shape if present
        if self.similarity is not None:
            if self.similarity.shape[0] != self.num_items or self.similarity.shape[1] != self.num_items:
                raise ValueError(
                    f"Model similarity matrix has shape {self.similarity.shape} "
                    f"but expected ({self.num_items}, {self.num_items}). Inconsistent model state."
                )
            # Check similarity values are finite
            if not np.all(np.isfinite(self.similarity.data)):
                non_finite_count = np.sum(~np.isfinite(self.similarity.data))
                raise ValueError(
                    f"Model similarity contains {non_finite_count} non-finite values (NaN or inf). "
                    "Model must have finite similarity scores."
                )

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
        scores = np.where(valid, self._pop_norm[safe] * self.popularity_weight, 0.0)
        if self.similarity is not None and self.is_known_user(user_idx):
            cf = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
            scores = scores + np.where(valid, cf[:, safe].toarray().ravel(), 0.0)

        # Validate output: must match input shape and be finite
        if scores.shape != item_idxs.shape:
            raise RuntimeError(
                f"Score output shape {scores.shape} does not match input shape {item_idxs.shape}. "
                "Scorer contract violation."
            )
        if not np.all(np.isfinite(scores)):
            non_finite_count = np.sum(~np.isfinite(scores))
            raise RuntimeError(
                f"Score output contains {non_finite_count} non-finite values (NaN or inf). "
                "Scorer contract violation."
            )

        return scores

    def has_personal_signal(self, user_idx: int) -> bool:
        """Check if the user has any collaborative filtering signal (i.e., has history with neighbors)."""
        if self.similarity is None or not self.is_known_user(user_idx):
            return False
        # Check if the user's history has any CF signal (similarity > 0)
        cf = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
        return cf.nnz > 0
