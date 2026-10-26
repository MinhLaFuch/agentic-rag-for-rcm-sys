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
                       invented_ids, reflections, first_attempt_ok, tool_selection_ok
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
    
    return row
