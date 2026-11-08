from __future__ import annotations

from itertools import product
from typing import Any


def parameter_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Expand a mapping of parameter names to candidate values."""
    # Validate grid is a dictionary
    if not isinstance(grid, dict):
        raise TypeError("grid must be a dictionary")

    if not grid:
        return [{}]

    keys = list(grid)
    values = [grid[key] for key in keys]

    # Validate all values are lists
    for key, val in grid.items():
        if not isinstance(val, list):
            raise TypeError(f"Parameter '{key}' must have a list of candidate values, got {type(val).__name__}")

    if any(not choices for choices in values):
        raise ValueError("Every hyperparameter must have at least one candidate value")

    return [dict(zip(keys, combination)) for combination in product(*values)]
