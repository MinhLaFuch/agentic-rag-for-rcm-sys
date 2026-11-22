"""Request-scoped CandidateScorer ablation with conservative collaborative ordering."""

import numpy as np

from .baseline_scorer import BaselineScorer


class EvidenceScorer(BaselineScorer):
    def __init__(self, model, evidence=None, *, mode='cf_ties', popularity_weight=.1, evidence_weight=.1, cf_weight=1.0):
        if isinstance(model, BaselineScorer):
            # Reuse validated immutable model arrays across request-scoped scorers.
            self.__dict__.update(model.__dict__)
            self.popularity_weight = 0.
        else:
            super().__init__(model, popularity_weight=0.)
        if mode not in ('cf_ties', 'additive_ablation', 'normalized_blend'):
            raise ValueError('Unknown evidence scoring mode')
        if any(not np.isfinite(v) or v < 0 for v in (popularity_weight, evidence_weight, cf_weight)):
            raise ValueError('Invalid evidence/popularity weights')
        self.mode = mode
        self.evidence = dict(evidence or {})
        if any(not np.isfinite(v) or not 0 <= v <= 1 for v in self.evidence.values()):
            raise ValueError('Evidence must be normalized to [0,1]')
        self.pop_weight, self.evidence_weight, self.cf_weight = popularity_weight, evidence_weight, cf_weight
        self.name = f'evidence_{mode}'

    def score(self, user_idx, item_idxs):
        indices = np.asarray(item_idxs, dtype=np.int64)
        cf = super().score(user_idx, indices)
        valid = (indices >= 0) & (indices < self.num_items)
        secondary = np.zeros(len(indices), dtype=np.float64)
        secondary[valid] = (self._pop_norm[indices[valid]] * self.pop_weight
                            + np.array([self.evidence.get(int(i), 0.) for i in indices[valid]]) * self.evidence_weight)
        if self.mode == 'additive_ablation':
            return cf + secondary
        if self.mode == 'normalized_blend':
            # Normalize CF to [0, 1] against the user's catalog peak so positive CF noise
            # does not automatically override high-confidence retrieval evidence or popularity.
            cf_norm = np.zeros(len(indices), dtype=np.float64)
            if self.similarity is not None and self.is_known_user(user_idx):
                row = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
                peak = float(row.data.max()) if row.nnz else 0.0
                if peak > 0.0:
                    cf_norm[valid] = cf[valid] / peak
            return cf_norm * self.cf_weight + secondary
        # Preserve every strict CF comparison, allowing evidence only inside exact ties.
        # Ordinal levels are request-local scores, not calibrated cross-request probabilities.
        result = np.zeros(len(indices), dtype=np.float64)
        levels = np.unique(cf[valid])
        scale = self.pop_weight + self.evidence_weight
        result[valid] = np.searchsorted(levels, cf[valid]) * 2.
        if scale:
            result[valid] += secondary[valid] / scale
        return result
