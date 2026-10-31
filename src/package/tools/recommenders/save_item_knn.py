"""Save ItemKNNRecommender model to file for later reuse."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import scipy.sparse as sp

from .item_knn_data_hash import item_knn_data_hash
from .file_hash import file_hash
from .fit_provenance import fit_provenance


def save_item_knn(
    model: Any,
    path: Path,
    k: int,
    fit_pairs: pd.DataFrame,
    *, user2id=None, item2id=None, eval_on=None, tag=None, fit_splits=None,
) -> None:
    """Save ItemKNNRecommender model to NPZ file with metadata.

    Args:
        model: Fitted ItemKNNRecommender or BaselineItemKNNRecommender instance.
        path: Destination path for the .npz file.
        k: The k (neighbors) parameter used during fitting.
        fit_pairs: DataFrame with user_idx and item_idx columns used for fitting.

    Raises:
        ValueError: If model lacks required attributes or fit_pairs is invalid.
    """
    if not hasattr(model, "similarity"):
        raise ValueError("Model must have 'similarity' attribute (not fitted or wrong model type)")
    if not isinstance(model.similarity, sp.spmatrix):
        raise ValueError(f"Model similarity must be a sparse matrix, got {type(model.similarity)}")

    if not {"user_idx", "item_idx"}.issubset(fit_pairs.columns):
        raise ValueError("fit_pairs must have user_idx and item_idx columns")

    data_hash = item_knn_data_hash(fit_pairs)
    provenance = fit_provenance(fit_pairs, user2id=user2id, item2id=item2id, eval_on=eval_on, tag=tag,
                                fit_splits=fit_splits)
    if int(k) != model.neighbors:
        raise ValueError("k mismatch with fitted model")
    expected_items = int(fit_pairs.item_idx.max()) + 1 if len(fit_pairs) else 0
    if model.similarity.shape != (expected_items, expected_items):
        raise ValueError("similarity shape does not match fit data")

    # Fit timing
    fit_time = getattr(model, "_fit_time", None)

    # Build metadata
    metadata = {
        "format_version": 2,
        "provenance": provenance,
        "algorithm": "binary_cosine_topk_v1",
        "data_hash_protocol": "sorted_event_pairs_int64_le_v1",
        "class_name": type(model).__name__,
        "k": int(k),
        "num_rows": len(fit_pairs),
        "num_users": int(fit_pairs["user_idx"].max() + 1) if not fit_pairs.empty else 0,
        "num_items": int(fit_pairs["item_idx"].max() + 1) if not fit_pairs.empty else 0,
        "data_hash": data_hash,
        "created_at": time.time(),
        "fit_time_seconds": fit_time,
    }

    # Write files
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Save similarity matrix and metadata
    sp.save_npz(str(path), model.similarity)
    metadata["artifact_sha256"] = file_hash(path)
    with open(str(path.with_suffix(".meta.json")), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
