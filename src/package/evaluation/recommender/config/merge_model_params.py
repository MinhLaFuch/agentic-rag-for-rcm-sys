from __future__ import annotations

from typing import Any


def merge_model_params(base: dict[str, Any], model_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a baseline config with one model's parameters overridden."""
    merged = {**base}
    merged[model_name] = {**base.get(model_name, {}), **params}
    return merged
