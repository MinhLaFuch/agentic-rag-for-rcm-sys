"""Save ItemKNNRecommender model to file for later reuse."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp


def save_item_knn(
    model: Any,
    path: Path,
    k: int,
    fit_pairs: pd.DataFrame,
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

    # Compute hash of fit data (fast: hash sorted values, not full df)
    # This is much faster than re-fitting and detects data changes
    users = fit_pairs["user_idx"].to_numpy(dtype=np.int64)
    items = fit_pairs["item_idx"].to_numpy(dtype=np.int64)
    # Sort to ensure consistent hash regardless of row order
    order = np.lexsort((items, users))
    combined = np.column_stack((users[order], items[order])).tobytes()
    data_hash = hashlib.sha256(combined).hexdigest()

    # Fit timing
    fit_time = getattr(model, "_fit_time", None)

    # Build metadata
    metadata = {
        "format_version": 1,
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
    with open(str(path.with_suffix(".meta.json")), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
