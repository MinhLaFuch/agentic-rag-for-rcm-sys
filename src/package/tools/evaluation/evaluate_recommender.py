"""Main recommender evaluation logic."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ._dataclass import EvaluationResult
from ._helper import assign_segments
from .metrics import ranking_metrics_at_k
from ..recommenders.recommender import Recommender


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

    Contract:
    - ``exclude`` / ``target`` are sparse matrices of the same shape (any sparse format is accepted).
      Any entry of ``target`` that is > 0 is a relevant item; stored zeros and duplicate entries are ignored,
      so they can neither create phantom users nor inflate the number of relevant items.
    - Only users with at least one relevant item are evaluated; metrics are macro-averaged over those users.
    - Segments (cold/sparse/warm) come from ``model.history_sizes`` = interactions in the data the model was
      FIT on, never from ``target``. ``-1`` padding in ``recommend`` output never counts as a hit or as coverage.
    - ``ks``: a non-empty collection of unique positive integers, each <= the catalog size.
    - Raises ValueError when the target has nothing to evaluate.
    """
    if not (sp.issparse(exclude) and sp.issparse(target)):
        raise TypeError("exclude and target must be scipy sparse matrices")
    if exclude.shape != target.shape:
        raise ValueError("exclude and target must have the same shape")
    exclude = exclude.tocsr()
    train_matrix = getattr(model, "train_matrix", None)
    if train_matrix is None:
        raise ValueError("model must be fitted before evaluation (train_matrix is None)")
    if train_matrix.shape[1] != target.shape[1]:
        raise ValueError(
            f"model was fit on {train_matrix.shape[1]} items but target has {target.shape[1]} items; "
            "the item index spaces must match"
        )
    # Binary ground truth: ignores stored zeros / duplicates so indptr counts relevant items exactly.
    target = (target.tocsr() > 0).astype(np.int8).tocsr()

    # Validate ks parameter (bool is an int subclass but is not a valid cut-off)
    try:
        ks = list(ks)
    except TypeError:
        raise ValueError("ks must be a non-empty list of positive integers") from None
    if not ks:
        raise ValueError("ks must be a non-empty list of positive integers")
    if not all(isinstance(k, (int, np.integer)) and not isinstance(k, (bool, np.bool_)) and k > 0 for k in ks):
        raise ValueError("all k values in ks must be positive integers")
    ks = [int(k) for k in ks]
    if len(set(ks)) != len(ks):
        raise ValueError("ks must contain unique values (no duplicates)")

    max_k = max(ks)
    num_items = target.shape[1]
    if max_k > num_items:
        raise ValueError(f"max_k ({max_k}) cannot exceed num_items ({num_items})")

    # Validate sparse_max
    if isinstance(sparse_max, (bool, np.bool_)) or not isinstance(sparse_max, (int, np.integer)) or sparse_max < 0:
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
