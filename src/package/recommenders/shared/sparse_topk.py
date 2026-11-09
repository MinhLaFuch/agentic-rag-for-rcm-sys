"""Exact sparse Top-K with index tie breaks and popularity on zero signal."""
import numpy as np


def sparse_topk(user_idxs, k, exclude, num_items, popularity_order, scores=None):
    result = np.full((len(user_idxs), k), -1, dtype=np.int64)
    for row, user in enumerate(user_idxs):
        if exclude is None:
            seen = set()
        else:
            start, end = exclude.indptr[user:user + 2]
            seen = set(exclude.indices[start:end][exclude.data[start:end] != 0])
        selected = []
        if scores is not None:
            start, end = scores.indptr[row:row + 2]
            ids = scores.indices[start:end]
            values = scores.data[start:end].astype(np.float32, copy=False)
            keep = values > 0
            if seen:
                keep &= ~np.isin(ids, list(seen))
            ids, values = ids[keep], values[keep]
            if len(ids) > k:
                boundary = np.partition(values, len(values) - k)[len(values) - k]
                higher = np.flatnonzero(values > boundary)
                tied = np.flatnonzero(values == boundary)
                tied = tied[np.argsort(ids[tied])[:k - len(higher)]]
                chosen = np.concatenate((higher, tied))
                ids, values = ids[chosen], values[chosen]
            selected = ids[np.lexsort((ids, -values))].tolist()
        # With positive CF signal, zero-score items tie by global index. With
        # no signal, the reference recommender falls back to training popularity.
        order = range(num_items) if selected else popularity_order
        used = set(selected)
        if len(selected) < k:
            for item in order:
                if item not in seen and item not in used:
                    selected.append(int(item))
                    if len(selected) == k:
                        break
        result[row, :len(selected)] = selected
    return result
