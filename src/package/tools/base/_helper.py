"""Helper functions for tools base module."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _hash_input(kwargs: dict[str, Any]) -> str:
    """Stable hash of input kwargs for deduplication."""
    normalized = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
