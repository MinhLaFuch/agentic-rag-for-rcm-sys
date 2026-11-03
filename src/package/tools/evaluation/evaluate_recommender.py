"""Main recommender evaluation logic."""

from __future__ import annotations

import time

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
    progress_every: int = 0,
    evaluation_users: np.ndarray | None = None,
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
    if evaluation_users is not None:
        selected = np.asarray(evaluation_users)
        if selected.ndim != 1 or not np.issubdtype(selected.dtype, np.integer):
            raise ValueError("evaluation_users must be a 1D integer array")
        if len(np.unique(selected)) != len(selected) or not np.isin(selected, users).all():
            raise ValueError("evaluation_users must be unique target-bearing users")
        users = np.sort(selected)
    if len(users) == 0:
        raise ValueError("target has no interactions to evaluate")

    if progress_every < 0:
        raise ValueError("progress_every must be non-negative")
    # Sparse recommendation only touches neighbors and Top-K, not B x catalog.
    from ..recommenders.popularity_matrix_recommender import PopularityMatrixRecommender
    from ..recommenders.item_knn_matrix_recommender import ItemKNNMatrixRecommender
    from ..recommenders.fallback_recommender import FallbackRecommender
    from ..recommenders.hybrid_item_knn_recommender import HybridItemKNNRecommender
    sparse_model = (type(model) in (PopularityMatrixRecommender, ItemKNNMatrixRecommender, HybridItemKNNRecommender)
                    or (type(model) is FallbackRecommender
                        and type(model.primary) is ItemKNNMatrixRecommender
                        and type(model.fallback) is PopularityMatrixRecommender))
    batch = 1024 if sparse_model else max(1, min(1024, batch_elements // max(1, num_items)))
    started = time.perf_counter()
    last_print = started
    last_completed = 0
    if progress_every:
        print(f"[eval:{model.name}] users=0/{len(users):,} batch={batch} ETA=warming up", flush=True)

    per_user: dict[str, list[np.ndarray]] = {}
    item_per_user: dict[str, dict[str, list[np.ndarray]]] = {"warm_item": {}, "cold_item": {}}
    recommended: dict[int, set] = {k: set() for k in ks}
    n_rel_all = np.diff(target.indptr)[users]
    familiarity = getattr(model, "item_familiarity_matrix", model.train_matrix)
    item_seen = np.asarray(familiarity.sum(axis=0)).ravel() > 0
    target_coo = target.tocoo()
    warm_target_count = np.bincount(
        target_coo.row[item_seen[target_coo.col]], minlength=target.shape[0]
    )
    cold_target_count = np.bincount(
        target_coo.row[~item_seen[target_coo.col]], minlength=target.shape[0]
    )

    for start in range(0, len(users), batch):
        u = users[start : start + batch]
        top = model.recommend(u, max_k, exclude)
        # Mask out padding (-1 values) - these are not real recommendations
        valid_mask = top >= 0
        # For invalid positions, set hits to False (no hit)
        safe_top = np.where(valid_mask, top, 0)
        looked_up = target[np.repeat(u, max_k), safe_top.ravel()]
        hits = np.asarray(looked_up.toarray() if sp.issparse(looked_up) else looked_up).reshape(safe_top.shape) > 0
        hits &= valid_mask
        recommended_item_seen = item_seen[safe_top] & valid_mask

        n_rel = n_rel_all[start : start + batch]
        for k in ks:
            metrics = ranking_metrics_at_k(hits, n_rel, k)
            for name, values in metrics.items():
                per_user.setdefault(name, []).append(values)

            for segment, target_counts, is_seen in (
                ("warm_item", warm_target_count, True),
                ("cold_item", cold_target_count, False),
            ):
                segment_relevant = target_counts[u]
                user_mask = segment_relevant > 0
                if not user_mask.any():
                    continue
                segment_hits = hits & recommended_item_seen if is_seen else hits & ~recommended_item_seen
                for name, values in ranking_metrics_at_k(
                    segment_hits[user_mask], segment_relevant[user_mask], k
                ).items():
                    item_per_user[segment].setdefault(name, []).append(values)
            # Only add valid item indices (>= 0) to recommended set
            valid_top_k = top[:, :k][valid_mask[:, :k]]
            recommended[k].update(np.unique(valid_top_k).tolist())

        completed = min(start + batch, len(users))
        now = time.perf_counter()
        if progress_every and (start == 0 or completed == len(users)
                               or completed - last_completed >= progress_every or now - last_print >= 10):
            elapsed = now - started
            rate = completed / elapsed if elapsed else 0
            eta = (len(users) - completed) / rate if rate else 0
            print(f"[eval:{model.name}] users={completed:,}/{len(users):,} "
                  f"({100*completed/len(users):.2f}%) rate={rate:.1f} users/s "
                  f"elapsed={elapsed:.0f}s ETA={eta:.0f}s (this model)", flush=True)
            last_print, last_completed = now, completed
    if progress_every:
        print(f"[eval:{model.name}] aggregating metrics", flush=True)
    metric_arrays = {name: np.concatenate(parts) for name, parts in per_user.items()}

    segments = assign_segments(model.history_sizes(users), sparse_max)
    by_segment, num_users = {}, {"all": int(len(users))}
    for seg in ("cold", "sparse", "warm"):
        mask = segments == seg
        num_users[seg] = int(mask.sum())
        if mask.any():
            by_segment[seg] = {n: float(v[mask].mean()) for n, v in metric_arrays.items()}

    relevant_items = target[users].indices if evaluation_users is not None else target_coo.col
    seen_ratio = float(item_seen[relevant_items].mean()) if len(relevant_items) else 0.0
    by_item_segment: dict[str, dict[str, float | int]] = {}
    for segment, metrics in item_per_user.items():
        if metrics:
            first_metric_parts = next(iter(metrics.values()))
            by_item_segment[segment] = {
                "num_users": int(sum(len(part) for part in first_metric_parts)),
                **{name: float(np.concatenate(parts).mean()) for name, parts in metrics.items()},
            }

    return EvaluationResult(
        overall={n: float(v.mean()) for n, v in metric_arrays.items()},
        by_segment=by_segment,
        num_users=num_users,
        catalog_coverage={f"catalog_coverage@{k}": len(recommended[k]) / num_items for k in ks},
        target_item_seen_ratio=seen_ratio,
        by_item_segment=by_item_segment,
    )
