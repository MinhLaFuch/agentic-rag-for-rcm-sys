"""Helper functions for Layer 4: Agentic Process Quality."""

from __future__ import annotations

from package.evaluation._schema import PLANNER_AGENTS
from package.evaluation.requests import reference_groups


def _follows(called: list[str], groups: list[tuple[str, ...]]) -> bool:
    """Check if called tools follow the reference plan groups in order."""
    position = 0
    for tool in called:
        if position < len(groups) and tool in groups[position]:
            position += 1
    return position == len(groups)


def check_tool_selection(
    request: Any,
    trajectory: dict[str, Any],
) -> bool | None:
    """
    Check if tool selection follows the reference plan.

    Returns:
        True if tools follow reference plan, False otherwise, None for non-planners.
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS
    steps = trajectory["steps"]
    plan_valid = trajectory["error"] is None
    asked = bool(plan_valid and is_planner and not steps and trajectory.get("ask_user"))
    
    if not is_planner:
        return None
    
    if request.kind == "ambiguous":
        return asked  # the right plan is "no steps + a question"
    else:
        groups = reference_groups(request.kind, set(trajectory.get("tools_available", [])))
        return _follows([s["tool"] for s in steps], groups)
