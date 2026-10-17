"""Helper to extract item IDs from candidate structures."""

from __future__ import annotations

from typing import Any, Sequence

from ._error import ToolInputError
from ._validation import validate_list_like


def candidate_ids(candidates: Sequence[Any]) -> list[str]:
    """Accept item-id strings or dicts with 'item_id' (i.e. another tool's output as-is).

    Returns a list of unique item IDs in the order they first appear.

    Use this when you only need item IDs and don't care about scores or other metadata.

    Example:
        >>> candidate_ids(["a", "b", {"item_id": "c"}])
        ['a', 'b', 'c']
    """
    ids: list[str] = []
    for c in validate_list_like(candidates, "candidates"):
        if isinstance(c, str):
            ids.append(c)
        elif isinstance(c, dict) and isinstance(c.get("item_id"), str):
            ids.append(c["item_id"])
        else:
            raise ToolInputError(
                f"invalid entry in candidates: each candidate must be an item_id string or dict with a string 'item_id', got {c!r}"
            )
    return list(dict.fromkeys(ids))  # de-duplicate, keep order
