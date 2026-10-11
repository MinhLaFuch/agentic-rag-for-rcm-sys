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
            raise ToolInputError(f"candidate must be an item_id string or dict with 'item_id': {c!r}")
    return list(dict.fromkeys(ids))  # de-duplicate, keep order


def candidate_results(candidates: Sequence[Any]) -> list[dict[str, Any]]:
    """Accept item-id strings or dicts with 'item_id', keeping full data for dicts.

    Similar to candidate_ids, but preserves all fields from dict inputs (score, similarity, etc.)
    while de-duplicating by item_id and keeping insertion order.

    Use this when you need to preserve retrieval scores or other metadata for downstream
    processing (e.g., score fusion, reranking, or debugging).

    Returns:
        List of dicts with unique item_ids. For string inputs, converts to {"item_id": id}.

    Example:
        >>> candidate_results([
        ...     {"item_id": "a", "score": 0.9, "similarity": 0.8},
        ...     "b",
        ...     {"item_id": "c", "score": 0.7}
        ... ])
        [{'item_id': 'a', 'score': 0.9, 'similarity': 0.8}, {'item_id': 'b'}, {'item_id': 'c', 'score': 0.7}]
    """
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for c in validate_list_like(candidates, "candidates"):
        if isinstance(c, str):
            result = {"item_id": c}
        elif isinstance(c, dict) and isinstance(c.get("item_id"), str):
            result = c
        else:
            raise ToolInputError(f"candidate must be an item_id string or dict with 'item_id': {c!r}")

        item_id = result["item_id"]
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            results.append(result)

    return results
