"""Layer 4: Agentic Process Quality metrics."""

from __future__ import annotations

from typing import Any

from package.evaluation._schema import PLANNER_AGENTS
from package.evaluation.requests import reference_groups
from ._helper import _follows


def score_layer4_process(
    request: Any,
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """
    Score agentic process quality including plan validity, steps, and tool selection.

    Returns:
        Dict with keys: plan_valid, plan_attempts, plan_truncated, n_steps, steps_ok_rate,
                       invented_ids, reflections, first_attempt_ok, tool_selection_ok,
                       args_valid_rate, price_arg_ok, category_arg_ok, used_ranker
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS
    steps = trajectory["steps"]
    usage = trajectory.get("usage") or {}
    plan_valid = trajectory["error"] is None
    asked = bool(plan_valid and is_planner and not steps and trajectory.get("ask_user"))

    row: dict[str, Any] = {
        "plan_valid": plan_valid,
        "plan_attempts": usage.get("attempts") if is_planner else None,
        "plan_truncated": bool(trajectory.get("truncated")) if is_planner else None,
        "n_steps": len(steps) if is_planner else None,
        "steps_ok_rate": (sum(s["ok"] for s in steps) / len(steps)) if steps else None,
        "invented_ids": sum(len(s.get("invented_ids", [])) for s in steps) if is_planner else None,
        "reflections": int(trajectory.get("reflections") or 0) if is_planner else None,
        "first_attempt_ok": trajectory.get("first_attempt_ok") if is_planner else None,
    }

    # Tool selection follows reference plan
    if is_planner:
        if request.kind == "ambiguous":
            row["tool_selection_ok"] = asked  # the right plan is "no steps + a question"
        else:
            groups = reference_groups(request.kind, set(trajectory.get("tools_available", [])))
            row["tool_selection_ok"] = _follows([s["tool"] for s in steps], groups)
    else:
        row["tool_selection_ok"] = None

    # args_valid_rate: proportion of steps that did not fail before tool call (unknown_tool, invented_id, unknown_args, bad_reference)
    if is_planner and steps:
        pre_call_errors = {"unknown_tool", "invented_id", "unknown_args", "bad_reference"}
        valid_steps = sum(1 for s in steps if s.get("error_kind") not in pre_call_errors)
        row["args_valid_rate"] = valid_steps / len(steps)
    else:
        row["args_valid_rate"] = None

    # price_arg_ok: for constrained/cold_text with price_max, check if any SQLTool/SemanticSearchTool has price_max not looser than request
    price_arg_ok = None
    if is_planner and request.price_max is not None and request.kind in ("constrained", "cold_text"):
        for step in steps:
            if step.get("tool") in ("SQLTool", "SemanticSearchTool") and step.get("ok"):
                args = step.get("args")
                if isinstance(args, dict):
                    filters = args.get("filters", {})
                    if isinstance(filters, dict):
                        step_price_max = filters.get("price_max")
                        if step_price_max is not None:
                            # Check if step price_max is not looser (tolerance 1e-9)
                            if step_price_max <= request.price_max + 1e-9:
                                price_arg_ok = True
                                break
                            else:
                                price_arg_ok = False
    row["price_arg_ok"] = price_arg_ok

    # category_arg_ok: for constrained/cold_text with category, check if category appears in filters or query
    category_arg_ok = None
    if is_planner and request.category is not None and request.kind in ("constrained", "cold_text"):
        for step in steps:
            if step.get("tool") in ("SQLTool", "SemanticSearchTool") and step.get("ok"):
                args = step.get("args")
                if isinstance(args, dict):
                    filters = args.get("filters", {})
                    if isinstance(filters, dict):
                        categories_any = filters.get("categories_any", [])
                        categories_all = filters.get("categories_all", [])
                        if isinstance(categories_any, list) and request.category in categories_any:
                            category_arg_ok = True
                            break
                        if isinstance(categories_all, list) and request.category in categories_all:
                            category_arg_ok = True
                            break
                    # Check query (case-insensitive)
                    query = args.get("query", "")
                    if isinstance(query, str) and request.category.lower() in query.lower():
                        category_arg_ok = True
                        break
    row["category_arg_ok"] = category_arg_ok

    # used_ranker: True if any RecoModelTool step succeeded in the final plan
    if is_planner and steps:
        used_ranker = any(s.get("tool") == "RecoModelTool" and s.get("ok") for s in steps)
        row["used_ranker"] = used_ranker
    else:
        row["used_ranker"] = None

    return row
