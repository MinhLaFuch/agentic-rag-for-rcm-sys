"""Layer 2: Interaction & Output Quality metrics."""

from __future__ import annotations

from package.evaluation._schema import PLANNER_AGENTS
from package.evaluation.requests import items_satisfying, items_without_price
from package.corpus import ItemCorpus


def score_layer2_interaction(
    request: Any,
    trajectory: dict[str, Any],
    *,
    corpus: ItemCorpus,
) -> dict[str, Any]:
    """
    Score interaction quality and output constraints.

    task_success (version 2):
      - ambiguous: asked_clarification (same as version 1)
      - exclusion: plan_valid AND steps_ok AND has recommendations AND exclusion_compliance=1.0
      - unanswerable: appropriate handling (ask_user, no_result, or grounded explanation of limitations)
      - other kinds: plan_valid AND steps_ok AND has recommendations AND constraint_satisfaction=1.0 (if constrained)
                     AND (if answer_status exists: answer_status == "ok" AND answer_grounded)
      - Old trajectories without answer_status use version 1 definition (no answer check)
    Returns: 
        Dict with keys: task_success, constraint_satisfaction, price_unknown_rate, asked_clarification,
                      exclusion_compliance (for exclusion kind)
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

    # Constraint satisfaction for constrained kinds (constrained, cold_text)
    constrained = request.kind in ("constrained", "cold_text")
    if constrained:
        ok_items = items_satisfying(corpus, rec, request.price_max, request.category)
        row["constraint_satisfaction"] = (len(ok_items) / len(rec)) if rec else 0.0
        row["price_unknown_rate"] = (len(items_without_price(corpus, rec)) / len(rec)) if rec and request.price_max else None
    else:
        row["constraint_satisfaction"] = None
        row["price_unknown_rate"] = None

    # Exclusion compliance for exclusion kind: fraction of recommendations that do
    # NOT violate the requested exclusions (excluded item_ids or category nodes).
    # None when the request carries no structured exclusions (unmeasurable, not 1.0).
    exclusion = request.kind == "exclusion"
    if exclusion:
        excluded_items = set(getattr(request, "excluded_item_ids", None) or [])
        excluded_cats = set(getattr(request, "excluded_categories", None) or [])
        violating: set[str] = set()
        if rec and (excluded_items or excluded_cats):
            ids = list(dict.fromkeys(rec))
            ph = ",".join("?" * len(ids))
            if excluded_items:
                eph = ",".join("?" * len(excluded_items))
                rows, _ = corpus.select(
                    f"SELECT item_id FROM items WHERE item_id IN ({ph}) AND item_id IN ({eph})",
                    ids + list(excluded_items), max_rows=len(ids),
                )
                violating |= {r["item_id"] for r in rows}
            if excluded_cats:
                cph = ",".join("?" * len(excluded_cats))
                rows, _ = corpus.select(
                    f"SELECT DISTINCT item_id FROM item_categories WHERE item_id IN ({ph}) AND category IN ({cph})",
                    ids + list(excluded_cats), max_rows=len(ids),
                )
                violating |= {r["item_id"] for r in rows}
            row["exclusion_compliance"] = 1.0 - len(violating) / len(rec)
            row["exclusion_compliance_detail"] = sorted(violating)
        else:
            row["exclusion_compliance"] = None
            row["exclusion_compliance_detail"] = None
    else:
        row["exclusion_compliance"] = None
        row["exclusion_compliance_detail"] = None

    # Task success depends on kind
    steps_ok = all(s["ok"] for s in steps)
    has_answer = trajectory.get("answer_status") is not None
    
    if request.kind == "ambiguous":
        row["task_success"] = asked
    elif request.kind == "unanswerable":
        if has_answer:
            answer_status = trajectory.get("answer_status")
            row["task_success"] = bool(
                plan_valid and steps_ok and (
                    answer_status=="ask_user" or
                    answer_status=="no_result" or
                    (answer_status=="ok" and trajectory.get("answer_grounded") and not rec)
                )
            )
        else:
            row["task_success"] = bool(
                plan_valid and steps_ok and not rec
            )
    elif exclusion:
            row["task_success"] = bool(
                plan_valid and steps_ok and rec and
                (row.get("exclusion_compliance") == 1.0 if row.get("exclusion_compliance") is not None else True)
            )
    else:
            row["task_success"] = bool(
                plan_valid and steps_ok and rec and
                (row["constraint_satisfaction"] == 1.0 if constrained else True)
            )
    return row
