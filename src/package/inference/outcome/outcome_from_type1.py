from __future__ import annotations

from typing import Any

from .._dataclass import AgentOutcome
from ..cut import cut
from .._limits import get_inference_limits
from .._schema import ITEM_FIELDS


def outcome_from_type1(request_text: str, out: dict[str, Any], *, max_items: int | None = None) -> AgentOutcome:
    """AgentOutcome from Type1Agent.recommend(): ok + items (already ranked + metadata), ok + [] (cold start), or stage + error."""
    max_items = get_inference_limits().max_items if max_items is None else max_items
    if not out.get("ok"):
        errors = [{"tool": str(out.get("stage") or "type1"), "error": cut(out.get("error"))}]
        return AgentOutcome(request_text=request_text, errors=errors)
    rows = [r for r in out.get("items") or [] if isinstance(r, dict) and isinstance(r.get("item_id"), str)]
    unique = list({r["item_id"]: r for r in reversed(rows)}.values())[::-1]  # first occurrence wins, order kept
    items = [{f: r.get(f) for f in ITEM_FIELDS} for r in unique[:max_items]]
    return AgentOutcome(request_text=request_text, items=items, cold_start=out.get("cold_start"))
