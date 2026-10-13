"""Helper functions for tools base module."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _hash_input(kwargs: dict[str, Any]) -> str:
    """Stable hash of input kwargs for deduplication."""
    normalized = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _simplify_args(kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Simplify args for logging: truncate long lists/dicts, keep structure.

    This prevents logs from growing unbounded with large candidate lists or
    complex nested structures.
    """
    simplified = {}
    for key, value in kwargs.items():
        if isinstance(value, (list, tuple)):
            simplified[key] = f"<{type(value).__name__} length={len(value)}>"
        elif isinstance(value, dict):
            simplified[key] = f"<dict keys={list(value.keys())}>"
        elif isinstance(value, str) and len(value) > 100:
            simplified[key] = f"<str length={len(value)} prefix={value[:50]!r}...>"
        else:
            simplified[key] = value
    return simplified
