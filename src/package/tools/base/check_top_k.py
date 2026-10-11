"""Validator for top_k parameter in tools."""

from __future__ import annotations

import numpy as np

from .._limits import MAX_CANDIDATES
from ._error import ToolInputError


def check_top_k(top_k: int, upper: int = MAX_CANDIDATES, name: str = "limit/max_rows/top_k") -> int:
    """name: tên tham số thật của tool gọi (limit / max_rows / top_k) để lỗi chỉ đúng chỗ cho LLM sửa."""
    if isinstance(top_k, (bool, np.bool_)):
        raise ToolInputError(f"Expected an integer, not a boolean, for {name}; got {top_k!r}")
    if not isinstance(top_k, (int, np.integer)):
        raise ToolInputError(f"{name} must be an integer, got {type(top_k).__name__} {top_k!r}")
    if top_k < 1:
        raise ToolInputError(f"{name} must be >= 1, got {top_k}")
    if top_k > upper:
        raise ToolInputError(f"{name} must be <= {upper}, got {top_k}")
    return int(top_k)
