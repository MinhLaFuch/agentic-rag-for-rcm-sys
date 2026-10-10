"""Validation helpers for tool inputs - ensure types are correct and raise clear errors."""

from __future__ import annotations

from typing import Any

from ._error import ToolInputError


def validate_list_like(value: Any, name: str) -> list[Any]:
    """Ensure value is a list or tuple, return as list."""
    if not isinstance(value, (list, tuple)):
        raise ToolInputError(f"{name} must be a list or tuple, got {type(value).__name__}")
    return list(value)


def validate_int(value: Any, name: str, *, min_value: int = 1, max_value: int | None = None) -> int:
    """Ensure value is an integer (not bool), in range, and not truncated."""
    if isinstance(value, bool):
        raise ToolInputError(f"{name} must be an integer, not a boolean")
    if not isinstance(value, int):
        if isinstance(value, float):
            if not value.is_integer():
                raise ToolInputError(f"{name} must be an integer, got float {value}")
            raise ToolInputError(f"{name} must be an integer, got float {value} (use int({int(value)}))")
        raise ToolInputError(f"{name} must be an integer, got {type(value).__name__}")
    
    if min_value is not None and value < min_value:
        raise ToolInputError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ToolInputError(f"{name} must be <= {max_value}, got {value}")
    
    return value


def validate_float(value: Any, name: str, *, min_value: float | None = None, max_value: float | None = None) -> float:
    """Ensure value is a number (int or float), in range."""
    if isinstance(value, bool):
        raise ToolInputError(f"{name} must be a number, not a boolean")
    if not isinstance(value, (int, float)):
        raise ToolInputError(f"{name} must be a number, got {type(value).__name__}")
    
    float_value = float(value)
    if min_value is not None and float_value < min_value:
        raise ToolInputError(f"{name} must be >= {min_value}, got {float_value}")
    if max_value is not None and float_value > max_value:
        raise ToolInputError(f"{name} must be <= {max_value}, got {float_value}")
    
    return float_value


def validate_dict(value: Any, name: str) -> dict[str, Any]:
    """Ensure value is a dict."""
    if not isinstance(value, dict):
        raise ToolInputError(f"{name} must be a dict, got {type(value).__name__}")
    return value
