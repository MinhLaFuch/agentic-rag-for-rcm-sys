"""
VectorStore: dense vector index for catalog items with cosine similarity search.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np


class VectorStore:
    """
    In-memory dense vector store supporting filtered cosine similarity search.
    Expects L2-normalized vectors so that dot-product equals cosine similarity.
    """

    def __init__(self, item_ids: Sequence[str], embeddings: np.ndarray) -> None:
        if len(item_ids) != len(embeddings):
            raise ValueError(f"Mismatch: len(item_ids)={len(item_ids)} != len(embeddings)={len(embeddings)}")
        
        self.item_ids = np.asarray(item_ids, dtype=object)
        self.embeddings = np.asarray(embeddings, dtype=np.float32)
        
        # Ensure L2 normalized
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.where(norms > 1e-9, norms, 1.0)
        self.embeddings = self.embeddings / norms

        self.id2idx = {item_id: idx for idx, item_id in enumerate(self.item_ids)}

    def __len__(self) -> int:
        return len(self.item_ids)

    def dimension(self) -> int:
        return self.embeddings.shape[1] if len(self.embeddings) > 0 else 0

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 50,
        candidate_ids: set[str] | Sequence[str] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Search nearest neighbor items by cosine similarity.

        Args:
            query_vector: 1D or 2D numpy array. Will be L2-normalized.
            top_k: Maximum number of items to return.
            candidate_ids: Optional set/list of item_ids to restrict search to (pre-filtering).

        Returns:
            List of (item_id, cosine_score) sorted descending by score.
        """
        if len(self.item_ids) == 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(q)
        if norm > 1e-9:
            q = q / norm
        else:
            return []

        # If candidate_ids is specified, only evaluate those
        if candidate_ids is not None:
            valid_indices = [self.id2idx[cid] for cid in candidate_ids if cid in self.id2idx]
            if not valid_indices:
                return []
            
            sub_vecs = self.embeddings[valid_indices]
            scores = sub_vecs @ q
            k = min(top_k, len(scores))
            
            if k < len(scores):
                top_sub_idx = np.argpartition(-scores, k)[:k]
                top_sub_idx = top_sub_idx[np.argsort(-scores[top_sub_idx])]
            else:
                top_sub_idx = np.argsort(-scores)
                
            return [(str(self.item_ids[valid_indices[i]]), float(scores[i])) for i in top_sub_idx]

        # Full catalog search
        scores = self.embeddings @ q
        k = min(top_k, len(scores))
        if k <= 0:
            return []

        if k < len(scores):
            top_idx = np.argpartition(-scores, k)[:k]
            top_idx = top_idx[np.argsort(-scores[top_idx])]
        else:
            top_idx = np.argsort(-scores)

        return [(str(self.item_ids[i]), float(scores[i])) for i in top_idx]

    def save(self, path: Path | str) -> None:
        """Save vector store to a compressed .npz archive."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            p,
            item_ids=self.item_ids,
            embeddings=self.embeddings,
        )

    @classmethod
    def load(cls, path: Path | str) -> "VectorStore":
        """Load vector store from a .npz archive."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"VectorStore file not found: {p}")
        data = np.load(p, allow_pickle=True)
        item_ids = [str(x) for x in data["item_ids"]]
        embeddings = data["embeddings"].astype(np.float32)
        return cls(item_ids=item_ids, embeddings=embeddings)
