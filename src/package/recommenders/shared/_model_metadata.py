"""Model metadata utilities: file hashes, mapping hashes, split names, data hashes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import numpy as np
import pandas as pd


def file_hash(path) -> str:
    """SHA256 hash of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mapping_hash(mapping: Mapping[str, int]) -> str:
    """Hash names AND numeric assignments, independent of dictionary order."""
    values = list(mapping.values())
    if any(isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0 for v in values):
        raise ValueError("mapping indices must be non-negative integers")
    if sorted(values) != list(range(len(values))):
        raise ValueError("mapping indices must be unique and contiguous from zero")
    payload = json.dumps(sorted((str(k), int(v)) for k, v in mapping.items()),
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fit_split_names(eval_on: str) -> list[str]:
    """Return training split names for a given evaluation split."""
    if eval_on not in {"validation", "test"}:
        raise ValueError("eval_on must be validation or test")
    return ["train"] if eval_on == "validation" else ["train", "validation"]


def item_knn_data_hash(fit_pairs: pd.DataFrame) -> str:
    """Stable fingerprint for the exact interaction pairs used to fit ItemKNN."""
    if not {"user_idx", "item_idx"}.issubset(fit_pairs.columns):
        raise ValueError("fit_pairs must contain user_idx and item_idx columns")
    users = fit_pairs["user_idx"].to_numpy(dtype=np.int64)
    items = fit_pairs["item_idx"].to_numpy(dtype=np.int64)
    for column in ("user_idx", "item_idx"):
        values = fit_pairs[column]
        if values.isna().any() or (values < 0).any() or not np.array_equal(values.to_numpy(), values.to_numpy(dtype=np.int64)):
            raise ValueError("fit indices must be non-negative integers without nulls")
    order = np.lexsort((items, users))
    return hashlib.sha256(np.column_stack((users[order], items[order])).astype("<i8", copy=False).tobytes()).hexdigest()
