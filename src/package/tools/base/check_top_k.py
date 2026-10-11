"""Validator for top_k parameter in tools."""

from __future__ import annotations

from .._limits import MAX_CANDIDATES
from ._validation import validate_int


def check_top_k(top_k: int, upper: int = MAX_CANDIDATES, name: str = "limit/max_rows/top_k") -> int:
    """Validate top_k parameter using validate_int with domain-specific upper bound.

    Args:
        top_k: The value to validate
        upper: Maximum allowed value (default: MAX_CANDIDATES from config)
        name: Parameter name for error messages (limit/max_rows/top_k)

    Returns:
        Validated integer value
    """
    return validate_int(top_k, name, min_value=1, max_value=upper, allow_numpy=True)
