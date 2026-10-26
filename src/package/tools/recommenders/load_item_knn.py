"""Load ItemKNNRecommender model from file."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .item_knn_data_hash import item_knn_data_hash
from .file_hash import file_hash
from .fit_provenance import fit_provenance
from .item_knn_recommender import ItemKNNRecommender


def load_item_knn(
    path: Path,
    k: int,
    fit_pairs: pd.DataFrame,
    *, user2id=None, item2id=None, eval_on=None, tag=None,
) -> ItemKNNRecommender:
    """Load ItemKNNRecommender model from NPZ file with validation.

    Args:
        path: Path to the saved .npz file.
        k: The k (neighbors) parameter to validate against saved file.
        fit_pairs: DataFrame with user_idx and item_idx columns for validation.

    Returns:
        A fitted ItemKNNRecommender instance.

    Raises:
        FileNotFoundError: If file or metadata file is missing.
        ValueError: If validation fails (k mismatch, data hash mismatch, version mismatch, etc.).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ItemKNN file not found: {path}")
    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        raise FileNotFoundError(f"ItemKNN metadata file not found: {meta_path}")

    # Load metadata
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    # Validate format version
    if metadata.get("format_version") != 2:
        raise ValueError(
            f"Unsupported format version {metadata.get('format_version')}, expected 2 (provenance required). "
            "Re-fit with --save-item-knn to generate a new file."
        )

    expected = fit_provenance(fit_pairs, user2id=user2id, item2id=item2id, eval_on=eval_on, tag=tag)
    if metadata.get("provenance") != expected:
        raise ValueError("ItemKNN provenance mismatch: mapping assignments, fit split, tag or scope changed; refit required")
    if metadata.get("algorithm") != "binary_cosine_topk_v1" or metadata.get("data_hash_protocol") != "sorted_event_pairs_int64_le_v1":
        raise ValueError("ItemKNN algorithm/hash protocol mismatch; refit required")

    # Validate k
    saved_k = metadata["k"]
    if saved_k != k:
        raise ValueError(
            f"k mismatch: saved model used k={saved_k}, current k={k}. "
            "Re-fit with --save-item-knn or adjust k in config."
        )

    # Validate data hash
    current_hash = item_knn_data_hash(fit_pairs)
    saved_hash = metadata["data_hash"]
    if current_hash != saved_hash:
        error = ValueError(
            "Data hash mismatch: fit data has changed since the model was saved. "
            "Re-fit with --save-item-knn."
        )
        error.current_data_hash = current_hash
        raise error

    # Validate num_rows
    if len(fit_pairs) != metadata["num_rows"]:
        raise ValueError(
            f"Row count mismatch: saved {metadata['num_rows']} rows, current {len(fit_pairs)} rows. "
            "Re-fit with --save-item-knn."
        )

    # Validate num_users and num_items
    current_num_users = int(fit_pairs["user_idx"].max() + 1) if not fit_pairs.empty else 0
    current_num_items = int(fit_pairs["item_idx"].max() + 1) if not fit_pairs.empty else 0
    if current_num_users != metadata["num_users"]:
        raise ValueError(
            f"num_users mismatch: saved {metadata['num_users']}, current {current_num_users}. "
            "Re-fit with --save-item-knn."
        )
    if current_num_items != metadata["num_items"]:
        raise ValueError(
            f"num_items mismatch: saved {metadata['num_items']}, current {current_num_items}. "
            "Re-fit with --save-item-knn."
        )

    # Load similarity matrix
    if file_hash(path) != metadata.get("artifact_sha256"):
        raise ValueError("ItemKNN artifact checksum mismatch; refit required")
    similarity = sp.load_npz(path)
    if similarity.shape != (current_num_items, current_num_items) or not np.isfinite(similarity.data).all():
        raise ValueError("ItemKNN similarity shape or values invalid")

    # Reconstruct model
    # ItemKNNRecommender is just a pass-through to BaselineItemKNNRecommender
    model = ItemKNNRecommender(neighbors=k)

    # Set similarity (the expensive part)
    model.similarity = similarity

    # Reconstruct cheap attributes from fit_pairs (parent class BaselinePopularityRecommender)
    from .build_interaction_matrix import build_interaction_matrix

    model.num_items = current_num_items
    model.scores = np.bincount(
        fit_pairs["item_idx"].to_numpy(dtype=np.int64), minlength=model.num_items
    ).astype(np.float64)
    model.ranked_items = np.argsort(-model.scores, kind="stable")
    model.user_items = build_interaction_matrix(fit_pairs, current_num_users, model.num_items)

    # Store fit time from metadata
    model._fit_time = metadata.get("fit_time_seconds")
    model._fit_data_hash = current_hash
    model._provenance = expected

    return model
