"""Dependency-free normalized vector store for optional dense retrieval."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class VectorStore:
    """Exact cosine search over a fixed item-id/vector row order."""

    format_version = 1

    def __init__(self, item_ids, vectors):
        ids = [str(item_id) for item_id in item_ids]
        values = np.asarray(vectors, dtype=np.float32)
        if values.ndim != 2 or values.shape[0] != len(ids) or not len(ids):
            raise ValueError("vectors must be a non-empty 2D array aligned with item_ids")
        if len(set(ids)) != len(ids):
            raise ValueError("item_ids must be unique")
        if not np.isfinite(values).all():
            raise ValueError("vectors must contain finite values")
        norms = np.linalg.norm(values, axis=1)
        if np.any(norms <= 0):
            raise ValueError("vectors must have non-zero rows")
        self.item_ids = tuple(ids)
        self.vectors = values / norms[:, None]
        self._positions = {item_id: index for index, item_id in enumerate(self.item_ids)}

    @property
    def dimension(self) -> int:
        return int(self.vectors.shape[1])

    def search(self, query, limit: int, allowed_ids=None):
        if isinstance(limit, bool) or not isinstance(limit, (int, np.integer)) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        vector = np.asarray(query, dtype=np.float32)
        if vector.ndim != 1 or vector.shape[0] != self.dimension:
            raise ValueError(f"query must have shape ({self.dimension},)")
        if not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
            raise ValueError("query must be finite and non-zero")
        vector = vector / np.linalg.norm(vector)
        if allowed_ids is None:
            positions = np.arange(len(self.item_ids), dtype=np.int64)
        else:
            positions = np.asarray([self._positions[item] for item in dict.fromkeys(allowed_ids) if item in self._positions], dtype=np.int64)
        if not len(positions):
            return []
        scores = self.vectors[positions] @ vector
        order = np.lexsort((np.asarray([self.item_ids[i] for i in positions]), -scores))[: int(limit)]
        return [(self.item_ids[int(positions[i])], float(scores[i])) for i in order]

    def save(self, directory: str | Path) -> None:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        np.save(target / "vectors.npy", self.vectors)
        (target / "item_ids.json").write_text(json.dumps(self.item_ids, ensure_ascii=False), encoding="utf-8")
        (target / "manifest.json").write_text(json.dumps({"format_version": self.format_version,
            "rows": len(self.item_ids), "dimension": self.dimension}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path) -> "VectorStore":
        source = Path(directory)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format_version") != cls.format_version:
            raise ValueError("unsupported vector store format")
        ids = json.loads((source / "item_ids.json").read_text(encoding="utf-8"))
        values = np.load(source / "vectors.npy", mmap_mode="r")
        if manifest.get("rows") != len(ids) or manifest.get("dimension") != values.shape[1]:
            raise ValueError("vector store manifest does not match artifacts")
        return cls(ids, values)
