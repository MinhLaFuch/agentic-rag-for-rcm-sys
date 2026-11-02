"""Versioned artifact provenance."""
from __future__ import annotations

from .mapping_hash import mapping_hash
from .fit_split_names import fit_split_names


def fit_provenance(fit_pairs, *, user2id=None, item2id=None, eval_on=None, tag=None) -> dict:
    """Unmapped synthetic models remain usable; dataset-bound loads require mappings."""
    if (user2id is None) != (item2id is None):
        raise ValueError("provide both user2id and item2id")
    if eval_on is not None and (user2id is None or not tag):
        raise ValueError("dataset-bound provenance requires mappings and tag")
    nu = int(fit_pairs.user_idx.max()) + 1 if len(fit_pairs) else 0
    ni = int(fit_pairs.item_idx.max()) + 1 if len(fit_pairs) else 0
    if user2id is not None and (nu > len(user2id) or ni > len(item2id)):
        raise ValueError("fit indices exceed mapping dimensions")
    return {
        "scope": "dataset_bound" if eval_on is not None else "numeric_pairs_only",
        "user_mapping_hash": mapping_hash(user2id) if user2id is not None else None,
        "item_mapping_hash": mapping_hash(item2id) if item2id is not None else None,
        "eval_on": eval_on, "fit_splits": fit_split_names(eval_on) if eval_on else None,
        "tag": tag,
    }

