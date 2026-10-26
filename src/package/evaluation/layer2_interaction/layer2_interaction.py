"""Layer 2: Interaction & Output Quality metrics."""

from __future__ import annotations

from typing import Any

from package.evaluation._schema import PLANNER_AGENTS
from package.evaluation.requests import items_satisfying, items_without_price
from package.tools.corpus import ItemCorpus


def score_layer2_interaction(
    request: Any,
    trajectory: dict[str, Any],
    *,
    corpus: ItemCorpus,
) -> dict[str, Any]:
    """
    Score interaction quality and output constraints.

    Returns:
        Dict with keys: task_success, constraint_satisfaction, price_unknown_rate, asked_clarification
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS
    steps = trajectory["steps"]
    rec = list(dict.fromkeys(trajectory["recommended"]))
    plan_valid = trajectory["error"] is None
    asked = bool(plan_valid and is_planner and not steps and trajectory.get("ask_user"))
    
    row: dict[str, Any] = {
        "asked_clarification": asked if is_planner else None,
    }
    
    # Constraint satisfaction for constrained kinds
    constrained = request.kind in ("constrained", "cold_text")
    if constrained:
        ok_items = items_satisfying(corpus, rec, request.price_max, request.category)
        row["constraint_satisfaction"] = (len(ok_items) / len(rec)) if rec else 0.0
        row["price_unknown_rate"] = (len(items_without_price(corpus, rec)) / len(rec)) if rec and request.price_max else None
    else:
        row["constraint_satisfaction"] = None
        row["price_unknown_rate"] = None
    
    # Task success depends on kind
    if request.kind == "ambiguous":
        row["task_success"] = asked
    else:
        steps_ok = all(s["ok"] for s in steps)
        row["task_success"] = bool(
            plan_valid and steps_ok and rec and (row["constraint_satisfaction"] == 1.0 if constrained else True)
        )
    
    return row
