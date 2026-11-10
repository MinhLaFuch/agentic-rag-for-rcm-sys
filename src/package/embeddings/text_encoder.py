"""Small encoder contract used by optional dense retrieval."""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


class TextEncoder:
    """Adapt a callable returning one vector per input text."""

    def __init__(self, encode_fn: Callable[[Sequence[str]], object], dimension: int | None = None):
        if not callable(encode_fn):
            raise TypeError("encode_fn must be callable")
        self.encode_fn = encode_fn
        self.dimension = dimension

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if isinstance(texts, (str, bytes)):
            raise TypeError("texts must be a sequence of strings")
        values = list(texts)
        if any(not isinstance(text, str) for text in values):
            raise TypeError("texts must contain only strings")
        result = np.asarray(self.encode_fn(values), dtype=np.float32)
        if result.ndim != 2 or result.shape[0] != len(values):
            raise ValueError(f"encoder returned shape {result.shape}, expected ({len(values)}, dimension)")
        if self.dimension is not None and result.shape[1] != self.dimension:
            raise ValueError(f"encoder returned dimension {result.shape[1]}, expected {self.dimension}")
        if not np.isfinite(result).all():
            raise ValueError("encoder returned non-finite values")
        return result
