from __future__ import annotations

import sys
from typing import Any

from ..agents import extract_recommendations
from ._dataclass import AgentOutcome
from ._helper import cut
from ._limits import get_inference_limits
from ._schema import ITEM_FIELDS, METADATA_ROW_KEYS


def outcome_from_plan_results(
    request_text: str,
    results: list[dict[str, Any]],
    *,
    question: str | None = None,
    plan_error: str | None = None,
    max_items: int | None = None,
) -> AgentOutcome:
    """
    AgentOutcome from PlanExecutor.run() results.
      question    executor.last_question
      plan_error  text of the ValueError / LLMProviderError when run() raised (results is then [])
    Items = extract_recommendations(...) (so the same ids, same order as trajectory["recommended"]), de-duplicated and cut to
    max_items. Metadata comes from what the tools returned (QueryTool first, then search/ranker rows); nothing is invented.
    """
    max_items = get_inference_limits().max_items if max_items is None else max_items
    ids = list(dict.fromkeys(extract_recommendations(results, sys.maxsize)))[:max_items]
    meta: dict[str, dict[str, Any]] = {i: {f: None for f in ITEM_FIELDS} | {"item_id": i} for i in ids}
    for result in sorted((r for r in results if r.get("ok")), key=lambda r: r.get("tool") != "QueryTool"):
        for key in METADATA_ROW_KEYS:
            rows = (result.get("data") or {}).get(key)
            for row in rows if isinstance(rows, list) else []:
                target = meta.get(row.get("item_id")) if isinstance(row, dict) and isinstance(row.get("item_id"), str) else None
                if target is None:
                    continue
                for field_name in ITEM_FIELDS:
                    if target[field_name] is None and row.get(field_name) is not None:
                        target[field_name] = row[field_name]
    errors = [{"tool": str(r.get("tool") or "unknown"), "error": cut(r.get("error"))} for r in results if not r.get("ok")]
    if plan_error:
        errors.append({"tool": "planner", "error": cut(plan_error)})
    invented = list(dict.fromkeys(i for r in results for i in r.get("invented_ids") or []))
    return AgentOutcome(
        request_text=request_text, items=[meta[i] for i in ids], question=question or None, errors=errors,
        invented_ids=invented, cold_start=None, n_steps=len(results),
    )
