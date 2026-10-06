"""Validator for top_k parameter in tools."""

from __future__ import annotations

import numpy as np

from .._limits import MAX_CANDIDATES
from ._error import ToolInputError


def check_top_k(top_k: int, upper: int = MAX_CANDIDATES) -> int:
    if not isinstance(top_k, (int, np.integer)) or not 1 <= top_k <= upper:
        raise ToolInputError(f"top_k must be an integer in [1, {upper}], got {top_k!r}")
    return int(top_k)
