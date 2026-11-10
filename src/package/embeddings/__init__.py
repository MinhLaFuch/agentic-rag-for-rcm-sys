"""Optional dense retrieval primitives.

The runtime has no model dependency: callers provide an encoder or vectors.
Offline model pinning and catalog encoding remain in scripts/evaluation.
"""

from .text_encoder import TextEncoder
from .vector_store import VectorStore

__all__ = ["TextEncoder", "VectorStore"]
