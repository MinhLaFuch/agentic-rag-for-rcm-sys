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
