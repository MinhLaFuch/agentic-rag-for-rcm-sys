"""Sparse normalized CF/popularity blend with explicit pre-cutoff popularity."""
import numpy as np

from .recommender import Recommender


class HybridItemKNNRecommender(Recommender):
    def __init__(self, cf, popularity_history, weight=1.0, *, popularity_only=False):
        super().__init__()
        if not np.isfinite(weight) or weight < 0:
            raise ValueError("weight must be finite and non-negative")
        self.cf, self.weight, self.popularity_only = cf, float(weight), popularity_only
        self.train_matrix = cf.train_matrix
        self.history_matrix = popularity_history
        self.num_users, self.num_items = self.train_matrix.shape
        self.counts = np.asarray(popularity_history.sum(axis=0)).ravel().astype(np.float32)
        peak = self.counts.max(initial=0)
        self.popularity = self.counts / peak if peak else self.counts
        self.order = np.argsort(-self.counts, kind="stable")
        self.name = "history_popularity" if popularity_only else f"hybrid_item_knn_w{weight:g}"

    def _fit(self, train_matrix):
        raise ValueError("construct from an already fitted CF model and pre-target history")

    def score_batch(self, user_idxs):
        values = np.zeros((len(user_idxs), self.num_items), dtype=np.float32)
        if not self.popularity_only:
            values = (self.history_matrix[user_idxs] @ self.cf.similarity.T).toarray().astype(np.float32)
            maxima = values.max(axis=1, keepdims=True)
            values = np.divide(values, maxima, out=np.zeros_like(values), where=maxima > 0)
        return values + (1 if self.popularity_only else self.weight) * self.popularity

    def _recommend_sparse(self, user_idxs, k, exclude):
        from .sparse_topk import sparse_topk
        if self.popularity_only:
            return sparse_topk(user_idxs, k, exclude, self.num_items, self.order)
        scores = (self.history_matrix[user_idxs] @ self.cf.similarity.T).tocsr()
        scores.sum_duplicates()
        result = np.full((len(user_idxs), k), -1, dtype=np.int64)
        for row, user in enumerate(user_idxs):
            start, end = scores.indptr[row:row + 2]
            ids, values = scores.indices[start:end], scores.data[start:end].astype(np.float32)
            peak = values.max(initial=0)
            if peak:
                values = values / peak
            seen = set()
            if exclude is not None:
                a, b = exclude.indptr[user:user + 2]
                seen = set(exclude.indices[a:b][exclude.data[a:b] != 0])
            popular = []
            for item in self.order:
                if item not in seen:
                    popular.append(int(item))
                    if len(popular) == k:
                        break
            # Any item outside this union has zero CF and popularity no higher
            # than the kth unseen popular item, so cannot enter the exact Top-K.
            candidates = np.union1d(ids, popular).astype(np.int64)
            candidates = candidates[~np.isin(candidates, list(seen))]
            cf_values = np.zeros(len(candidates), dtype=np.float32)
            positions = np.searchsorted(candidates, ids)
            valid = positions < len(candidates)
            valid &= ~np.isin(ids, list(seen))
            cf_values[positions[valid]] = values[valid]
            combined = cf_values + self.weight * self.popularity[candidates]
            # At weight zero, keep the positive CF order and complete with
            # popularity, avoiding arbitrary global-index zero-score fillers.
            if self.weight == 0:
                positive = combined > 0
                picked = candidates[positive][np.lexsort((candidates[positive], -combined[positive]))][:k].tolist()
                picked += [i for i in popular if i not in picked][:k - len(picked)]
            else:
                picked = candidates[np.lexsort((candidates, -combined))][:k].tolist()
            result[row, :len(picked)] = picked
        return result
