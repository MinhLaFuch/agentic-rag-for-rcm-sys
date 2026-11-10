"""Optional dense retrieval primitives.

The runtime has no model dependency: callers provide an encoder or vectors.
Offline model pinning and catalog encoding remain in scripts/evaluation.
"""

from .text_encoder import TextEncoder
from .vector_store import VectorStore
from .encoder import (
    BaseEmbeddingEncoder,
    HashEmbeddingEncoder,
    OpenAIEmbeddingEncoder,
    SentenceTransformerEncoder,
    build_embedding_encoder,
)

__all__ = [
    "TextEncoder",
    "VectorStore",
    "BaseEmbeddingEncoder",
    "HashEmbeddingEncoder",
    "OpenAIEmbeddingEncoder",
    "SentenceTransformerEncoder",
    "build_embedding_encoder",
]
