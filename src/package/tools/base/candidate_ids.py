"""Helper to extract item IDs from candidate structures."""

from __future__ import annotations

from typing import Any, Sequence

from ._error import ToolInputError


def candidate_ids(candidates: Sequence[Any]) -> list[str]:
    """Accept item-id strings or dicts with 'item_id' (i.e. another tool's output as-is)."""
    ids: list[str] = []
    for c in candidates:
        if isinstance(c, str):
            ids.append(c)
        elif isinstance(c, dict) and isinstance(c.get("item_id"), str):
            ids.append(c["item_id"])
        else:
            raise ToolInputError(f"candidate must be an item_id string or dict with 'item_id': {c!r}")
    return list(dict.fromkeys(ids))  # de-duplicate, keep order
