"""Schema fingerprint and logic version for corpus cache validation.

This module provides:
- Schema fingerprint: hash of SQL schema definitions from _sql.py
- Logic version: constant to increment when from_dataframe logic changes
Both are combined to validate cached corpus files against current code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def _schema_fingerprint() -> str:
    """Compute SHA256 hash of SQL schema definitions from _sql.py.

    This detects schema changes (CREATE TABLE, indexes, FTS) that would invalidate
    cached corpus files.
    """
    sql_path = Path(__file__).parent / "_sql.py"
    sql_content = sql_path.read_text(encoding="utf-8")
    return hashlib.sha256(sql_content.encode("utf-8")).hexdigest()


# Logic version for from_dataframe() - increment when build logic changes
# (e.g., different data cleaning, category handling, validation rules)
CORPUS_LOGIC_VERSION = 1


def compute_corpus_fingerprint() -> str:
    """Combine schema fingerprint and logic version into a single fingerprint."""
    schema_hash = _schema_fingerprint()
    combined = f"{schema_hash}:{CORPUS_LOGIC_VERSION}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()
