"""Candidate scores matching the validated full-catalog hybrid formula."""
from types import SimpleNamespace

import numpy as np

from .baseline_scorer import BaselineScorer


class HybridScorer(BaselineScorer):
    def __init__(self, model, popularity_weight=4.0):
        # The remapped model uses full pre-cutoff user history, while similarity
        # remains learned on core only. Do not mutate the shared cache model.
        counts = np.asarray(model.user_items.sum(axis=0)).ravel().astype(np.float32)
        proxy = SimpleNamespace(scores=counts, user_items=model.user_items,
                                similarity=model.similarity, num_items=model.num_items)
        super().__init__(proxy, popularity_weight)
        self.name = f"hybrid_item_knn_w{popularity_weight:g}"

    def score(self, user_idx, item_idxs):
        indices = np.asarray(item_idxs, dtype=np.int64)
        valid = (indices >= 0) & (indices < self.num_items)
        result = np.zeros(indices.shape, dtype=np.float32)
        result[valid] = self._pop_norm[indices[valid]] * self.popularity_weight
        if self.is_known_user(user_idx):
            cf = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
            # Normalize across the whole catalog BEFORE candidate/seen filtering.
            peak = cf.data.max(initial=0)
            if peak > 0:
                result[valid] += cf[:, indices[valid]].toarray().ravel().astype(np.float32) / peak
        if not np.isfinite(result).all():
            raise RuntimeError("hybrid scorer produced non-finite scores")
        return result
