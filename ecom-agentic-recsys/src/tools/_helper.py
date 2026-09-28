import json, hashlib
from .base import *

def _hash_input(kwargs: dict[str, Any]) -> str:
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def check_top_k(top_k: int, upper: int = MAX_CANDIDATES) -> int:
    if not isinstance(top_k, (int, np.integer)) or not 1 <= top_k <= upper:
        raise ToolInputError(f"top_k must be an integer in [1, {upper}], got {top_k!r}")
    return int(top_k)


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