"""Main recommender evaluation logic."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ._dataclass import EvaluationResult
from ._helper import assign_segments
from .metrics import ranking_metrics_at_k
from ..recommenders.base import Recommender


def evaluate_recommender(
    model: Recommender,
    exclude: sp.csr_matrix,
    target: sp.csr_matrix,
    ks: list[int],
    sparse_max: int = 4,
    batch_elements: int = 20_000_000,
) -> EvaluationResult:
    """
    Evaluate a recommender model on target data with exclusion matrix.

    model    : đã fit trên dữ liệu 'fit'
    exclude  : ma trận item đã thấy cần loại (thường = dữ liệu fit)
    target   : ground-truth (val hoặc test), cùng shape
    """
    if exclude.shape != target.shape:
        raise ValueError("exclude and target must have the same shape")

    # Validate ks parameter
    if not ks:
        raise ValueError("ks must be a non-empty list of positive integers")
    if not all(isinstance(k, int) and k > 0 for k in ks):
        raise ValueError("all k values in ks must be positive integers")
    if len(set(ks)) != len(ks):
        raise ValueError("ks must contain unique values (no duplicates)")

    max_k = max(ks)
    num_items = target.shape[1]
    if max_k > num_items:
        raise ValueError(f"max_k ({max_k}) cannot exceed num_items ({num_items})")

    # Validate sparse_max
    if not isinstance(sparse_max, int) or sparse_max < 0:
        raise ValueError("sparse_max must be a non-negative integer")

    users = np.where(np.diff(target.indptr) > 0)[0]
    if len(users) == 0:
        raise ValueError("target has no interactions to evaluate")

    batch = max(16, min(1024, batch_elements // max(1, num_items)))

    per_user: dict[str, list[np.ndarray]] = {}
    recommended: dict[int, set] = {k: set() for k in ks}
    n_rel_all = np.diff(target.indptr)[users]

    for start in range(0, len(users), batch):
        u = users[start : start + batch]
        top = model.recommend(u, max_k, exclude)
        gt = target[u].toarray() > 0

        # Mask out padding (-1 values) - these are not real recommendations
        valid_mask = top >= 0
        # For invalid positions, set hits to False (no hit)
        hits = np.where(valid_mask, np.take_along_axis(gt, top, axis=1), False)

        n_rel = n_rel_all[start : start + batch]
        for k in ks:
            for name, values in ranking_metrics_at_k(hits, n_rel, k).items():
                per_user.setdefault(name, []).append(values)
            # Only add valid item indices (>= 0) to recommended set
            valid_top_k = top[:, :k][valid_mask[:, :k]]
            recommended[k].update(np.unique(valid_top_k).tolist())

    metric_arrays = {name: np.concatenate(parts) for name, parts in per_user.items()}

    segments = assign_segments(model.history_sizes(users), sparse_max)
    by_segment, num_users = {}, {"all": int(len(users))}
    for seg in ("cold", "sparse", "warm"):
        mask = segments == seg
        num_users[seg] = int(mask.sum())
        if mask.any():
            by_segment[seg] = {n: float(v[mask].mean()) for n, v in metric_arrays.items()}

    item_seen = np.asarray(model.train_matrix.sum(axis=0)).ravel() > 0
    target_coo = target.tocoo()
    seen_ratio = float(item_seen[target_coo.col].mean()) if target_coo.nnz else 0.0

    return EvaluationResult(
        overall={n: float(v.mean()) for n, v in metric_arrays.items()},
        by_segment=by_segment,
        num_users=num_users,
        catalog_coverage={f"catalog_coverage@{k}": len(recommended[k]) / num_items for k in ks},
        target_item_seen_ratio=seen_ratio,
    )
