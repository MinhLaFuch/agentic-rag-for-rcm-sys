"""
VectorStore: dense vector index for catalog items with cosine similarity search.
"""

from __future__ import annotations

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

    @property
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        return int(self.embeddings.shape[1]) if len(self.embeddings) > 0 else 0

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 50,
        candidate_ids: set[str] | Sequence[str] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Search nearest neighbor items by cosine similarity.
        Ties are broken deterministically by item_id ascending.

        Args:
            query_vector: 1D or 2D numpy array. Will be L2-normalized.
            top_k: Maximum number of items to return.
            candidate_ids: Optional set/list of item_ids to restrict search to.

        Returns:
            List of (item_id, cosine_score) sorted descending by score, then ascending by item_id.
        """
        if len(self.item_ids) == 0 or top_k <= 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(q)
        if norm > 1e-9:
            q = q / norm
        else:
            return []

        if candidate_ids is not None:
            cand_set = set(candidate_ids)
            valid_indices = [idx for idx, cid in enumerate(self.item_ids) if cid in cand_set]
            if not valid_indices:
                return []
            sub_vecs = self.embeddings[valid_indices]
            scores = sub_vecs @ q
            pairs = [(str(self.item_ids[valid_indices[i]]), float(scores[i])) for i in range(len(valid_indices))]
            pairs.sort(key=lambda x: (-x[1], x[0]))
            return pairs[:top_k]

        scores = self.embeddings @ q
        pairs = [(str(self.item_ids[i]), float(scores[i])) for i in range(len(self.item_ids))]
        pairs.sort(key=lambda x: (-x[1], x[0]))
        return pairs[:top_k]

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
