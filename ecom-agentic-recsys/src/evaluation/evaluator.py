from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from src.evaluation.metrics import ranking_metrics_at_k
from src.recommenders.base import Recommender


@dataclass
class EvaluationResult:
    overall: dict[str, float]
    by_segment: dict[str, dict[str, float]]
    num_users: dict[str, int]
    catalog_coverage: dict[str, float]
    target_item_seen_ratio: float


def assign_segments(history_sizes: np.ndarray, sparse_max: int) -> np.ndarray:
    return np.where(
        history_sizes == 0, "cold", np.where(history_sizes <= sparse_max, "sparse", "warm")
    )


def evaluate_recommender(
    model: Recommender,
    exclude: sp.csr_matrix,
    target: sp.csr_matrix,
    ks: list[int],
    sparse_max: int = 4,
    batch_elements: int = 20_000_000,
) -> EvaluationResult:
    """
    model    : đã fit trên dữ liệu 'fit'
    exclude  : ma trận item đã thấy cần loại (thường = dữ liệu fit)
    target   : ground-truth (val hoặc test), cùng shape
    """
    if exclude.shape != target.shape:
        raise ValueError("exclude and target must have the same shape")

    users = np.where(np.diff(target.indptr) > 0)[0]
    if len(users) == 0:
        raise ValueError("target has no interactions to evaluate")

    max_k = max(ks)
    num_items = target.shape[1]
    batch = max(16, min(1024, batch_elements // max(1, num_items)))

    per_user: dict[str, list[np.ndarray]] = {}
    recommended: dict[int, set] = {k: set() for k in ks}
    n_rel_all = np.diff(target.indptr)[users]

    for start in range(0, len(users), batch):
        u = users[start : start + batch]
        top = model.recommend(u, max_k, exclude)
        gt = target[u].toarray() > 0
        hits = np.take_along_axis(gt, top, axis=1)
        n_rel = n_rel_all[start : start + batch]
        for k in ks:
            for name, values in ranking_metrics_at_k(hits, n_rel, k).items():
                per_user.setdefault(name, []).append(values)
            recommended[k].update(np.unique(top[:, :k]).tolist())

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
