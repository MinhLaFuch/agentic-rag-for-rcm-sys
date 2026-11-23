"""Learned candidate scorer: affine reranker over [popularity, CF] signals.

Weights were fit offline (investigations/q6_scorer_comparison_v3/v4) on
injected-target rescue@10 across two agent-eval runs: a logistic model on
per-request min-max-normalised [pop, cf] features, folded into a single
affine score (sigmoid dropped — ranking is invariant to it). The learned CF
coefficient is negative: CF similarity anti-predicts held-out targets, so
the scorer demotes high-CF candidates — consistent with the F10 finding
that ItemKNN/BPR-MF lose to plain popularity.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .baseline_scorer import BaselineScorer


class LearnedScorer(BaselineScorer):
    """BaselineScorer contract + learned affine weights on min-max features.

    score() computes the same raw signals as BaselineScorer (pop_norm and the
    ItemKNN CF row), min-max normalises each over the scored candidate set —
    the same transform the offline features used — and returns
    ``w_pop * pop_n + w_cf * cf_n + w_bias``.
    """

    # Affine coefficients on per-request min-max-normalised [pop, cf], fit on
    # pooled q6_exp1_always + q6_exp2_baseline features (see module docstring).
    DEFAULT_WEIGHTS = (1.819856, -9.981713, -0.157888)

    def __init__(self, model: Any, weights: tuple[float, float, float] | None = None) -> None:
        super().__init__(model, popularity_weight=1e-6)
        w = self.DEFAULT_WEIGHTS if weights is None else tuple(float(x) for x in weights)
        if len(w) != 3 or not all(np.isfinite(w)):
            raise ValueError(f"learned weights must be 3 finite numbers, got {weights!r}")
        self.weights = w
        self.name = f"learned_pop{w[0]:.3g}_cf{w[1]:.3g}"

    @staticmethod
    def _minmax(a: np.ndarray) -> np.ndarray:
        lo, hi = float(a.min()), float(a.max())
        return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)

    def score(self, user_idx: int, item_idxs: np.ndarray) -> np.ndarray:
        item_idxs = np.asarray(item_idxs, dtype=np.int64)
        valid = (item_idxs >= 0) & (item_idxs < self.num_items)
        safe = np.where(valid, item_idxs, 0)

        pop = self._pop_norm[safe].astype(np.float64)
        cf = np.zeros(len(item_idxs), dtype=np.float64)
        if self.similarity is not None and self.is_known_user(user_idx):
            cf_row = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
            cf = cf_row[:, safe].toarray().ravel().astype(np.float64)

        # Offline features min-max normalised each signal over the request's
        # candidate set; reproduce that transform on the scored set.
        pop_n = self._minmax(pop)
        cf_n = self._minmax(cf)
        scores = self.weights[0] * pop_n + self.weights[1] * cf_n + self.weights[2]
        scores = np.where(valid, scores, 0.0)

        if scores.shape != item_idxs.shape or not np.all(np.isfinite(scores)):
            raise RuntimeError("LearnedScorer produced invalid scores (contract violation)")
        return scores
