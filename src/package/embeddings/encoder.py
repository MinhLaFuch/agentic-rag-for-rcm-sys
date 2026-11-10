"""
Embedding encoders for dense retrieval.

Supports:
- OpenAIEmbeddingEncoder: standard OpenAI / vLLM / Ollama / TEI /v1/embeddings endpoint
- SentenceTransformerEncoder: local sentence-transformers models (if installed)
- HashEmbeddingEncoder: deterministic offline encoder for unit/integration testing
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseEmbeddingEncoder(ABC):
    """Abstract base class for text embedding encoders."""

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode a list of text strings into a 2D float32 numpy array of shape (N, dim).
        Vectors must be L2-normalized.
        """
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        ...


class HashEmbeddingEncoder(BaseEmbeddingEncoder):
    """
    Deterministic pseudo-embedding encoder for testing and offline environments.
    Uses MD5/SHA256 word hashing with bag-of-words random projections to produce consistent
    normalized dense representations without network or GPU dependencies.
    """

    def __init__(self, dim: int = 128) -> None:
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            if not text:
                continue
            words = text.lower().split()
            vec = np.zeros(self._dim, dtype=np.float32)
            for w in words:
                h = hashlib.sha256(w.encode("utf-8")).digest()
                # Unpack first 8 bytes into bucket and sign
                bucket = int.from_bytes(h[:4], "little") % self._dim
                sign = 1.0 if (h[4] % 2 == 0) else -1.0
                vec[bucket] += sign
            norm = np.linalg.norm(vec)
            if norm > 1e-9:
                vec /= norm
            out[i] = vec
        return out


class OpenAIEmbeddingEncoder(BaseEmbeddingEncoder):
    """
    Encoder that connects to any OpenAI-compatible `/v1/embeddings` endpoint
    (OpenAI, vLLM, Ollama, LM Studio, TEI, etc.).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        batch_size: int = 64,
        dim: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._batch_size = batch_size
        self._dim = dim

    def dimension(self) -> int:
        if self._dim is not None:
            return self._dim
        # Probe dimension with dummy string
        sample = self.encode(["probe"])
        self._dim = int(sample.shape[1])
        return self._dim

    def _encode_batch(self, batch: list[str]) -> np.ndarray:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "input": batch,
        }

        req = urllib.request.Request(
            url=f"{self._base_url}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Embedding API request failed: {exc}") from exc

        embeddings_data = data.get("data", [])
        # Ensure ordered by index
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        vecs = [item["embedding"] for item in embeddings_data]
        arr = np.asarray(vecs, dtype=np.float32)
        # L2-normalize
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms > 1e-9, norms, 1.0)
        return arr / norms

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            dim = self._dim if self._dim is not None else 128
            return np.empty((0, dim), dtype=np.float32)

        results = []
        for i in range(0, len(texts), self._batch_size):
            chunk = texts[i : i + self._batch_size]
            results.append(self._encode_batch(chunk))

        arr = np.vstack(results)
        if self._dim is None:
            self._dim = int(arr.shape[1])
        return arr


class SentenceTransformerEncoder(BaseEmbeddingEncoder):
    """
    Local sentence-transformers encoder (requires sentence-transformers package).
    """

    def __init__(self, model_name_or_path: str = "sentence-transformers/all-MiniLM-L6-v2", device: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. Run `pip install sentence-transformers` "
                "or use OpenAIEmbeddingEncoder / HashEmbeddingEncoder."
            ) from exc

        self._model = SentenceTransformer(model_name_or_path, device=device)
        self._dim = self._model.get_sentence_embedding_dimension()

    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        vecs = self._model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(vecs, dtype=np.float32)


def build_embedding_encoder(config: dict[str, Any] | None = None) -> BaseEmbeddingEncoder:
    """
    Factory creating an embedding encoder from config dictionary.
    Falls back to HashEmbeddingEncoder if unconfigured or dependencies missing.
    """
    if config is None:
        return HashEmbeddingEncoder()

    provider = config.get("provider", "hash")
    if provider == "openai_compatible":
        base_url = config.get("base_url") or "http://localhost:8000/v1"
        model = config.get("model") or "text-embedding-3-small"
        api_key = config.get("api_key")
        timeout = float(config.get("timeout_seconds", 60.0))
        return OpenAIEmbeddingEncoder(base_url=base_url, model=model, api_key=api_key, timeout_seconds=timeout)

    if provider == "sentence_transformers":
        model_name = config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        return SentenceTransformerEncoder(model_name_or_path=model_name)

    return HashEmbeddingEncoder(dim=int(config.get("dim", 128)))

