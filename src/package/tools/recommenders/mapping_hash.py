from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
import numpy as np


def mapping_hash(mapping: Mapping[str, int]) -> str:
    """Hash names AND numeric assignments, independent of dictionary order."""
    values = list(mapping.values())
    if any(isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0 for v in values):
        raise ValueError("mapping indices must be non-negative integers")
    if sorted(values) != list(range(len(values))):
        raise ValueError("mapping indices must be unique and contiguous from zero")
    payload = json.dumps(sorted((str(k), int(v)) for k, v in mapping.items()),
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

