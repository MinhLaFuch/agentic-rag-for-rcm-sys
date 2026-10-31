"""Consistent schema and logic fingerprint for corpus cache validation."""

from __future__ import annotations

import hashlib

from ._sql import CORPUS_LOGIC_VERSION, get_corpus_schema_fingerprint


def compute_corpus_fingerprint() -> str:
    """Combine the canonical SQL schema fingerprint and construction logic version."""
    combined = f"{get_corpus_schema_fingerprint()}:{CORPUS_LOGIC_VERSION}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()
