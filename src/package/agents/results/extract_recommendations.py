"""What the user would actually be shown: the item ids at the end of an agent's tool results."""

from __future__ import annotations

from typing import Any

# Preference order: a ranked list beats raw retrieval order, which beats QueryTool (SQL IN order, not rank order).
_GROUPS = (("RecoModelTool",), ("SemanticSearchTool", "SQLTool", "ItemCFTool"), ("QueryTool",))
_ROWS_KEY = {"RecoModelTool": "ranked", "QueryTool": "items"}  # every other tool returns `candidates`


def extract_recommendations(results: list[dict[str, Any]], k: int) -> list[str]:
    for group in _GROUPS:
        for r in reversed(results):
            if r.get("ok") and r.get("tool") in group:
                rows = r["data"].get(_ROWS_KEY.get(r["tool"], "candidates"), [])
                ids = [x["item_id"] for x in rows if isinstance(x, dict) and isinstance(x.get("item_id"), str)]
                if ids:
                    return ids[:k]
    return []
