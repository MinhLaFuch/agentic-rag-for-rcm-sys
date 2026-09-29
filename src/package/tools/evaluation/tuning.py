"""Hyperparameter tuning utilities for validation-only search."""

from __future__ import annotations

from itertools import product
from typing import Any


def parameter_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Expand a mapping of parameter names to candidate values."""
    if not grid:
        return [{}]
    keys = list(grid)
    values = [grid[key] for key in keys]
    if any(not choices for choices in values):
        raise ValueError("Every hyperparameter must have at least one candidate value")
    return [dict(zip(keys, combination)) for combination in product(*values)]


def merge_model_params(base: dict[str, Any], model_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a baseline config with one model's parameters overridden."""
    merged = {**base}
    merged[model_name] = {**base.get(model_name, {}), **params}
    return merged
