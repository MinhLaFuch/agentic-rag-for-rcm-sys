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
                       args_valid_rate, price_arg_ok, category_arg_ok, used_ranker,
                       itemcf_seed_correctness, memory_profile_usage, semanticsearch_keyword_quality,
                       tool_argument_correctness, component_failure_diagnosis,
                       reflection_invoked, reflection_succeeded
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

    # price_arg_ok: for constrained/cold_text with price_max, check if any FilterTool/SearchTool has price_max not looser than request
    price_arg_ok = None
    if is_planner and request.price_max is not None and request.kind in ("constrained", "cold_text"):
        for step in steps:
            if step.get("tool") in ("FilterTool", "SearchTool") and step.get("ok"):
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
            if step.get("tool") in ("FilterTool", "SearchTool") and step.get("ok"):
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

    # used_ranker: True if any RankTool step succeeded in the final plan
    if is_planner and steps:
        used_ranker = any(s.get("tool") == "RankTool" and s.get("ok") for s in steps)
        row["used_ranker"] = used_ranker
    else:
        row["used_ranker"] = None

    # ===== Component-Specific Diagnostics ====
    
    # ItemCF seed correctness: for similar kind, check if seed item was used correctly
    itemcf_seed_correctness = None
    if is_planner and request.kind == "similar" and request.seed_item_id:
        for step in steps:
            if step.get("tool") == "SimilarTool" and step.get("ok"):
                args = step.get("args", {})
                if isinstance(args, dict):
                    items = args.get("items", [])
                    if isinstance(items, list) and request.seed_item_id in items:
                        itemcf_seed_correctness = True
                        break
    row["itemcf_seed_correctness"] = itemcf_seed_correctness

    # Memory profile retrieval and usage
    memory_profile_usage = None
    memory_profile_retrieved = False
    if is_planner:
        memory_step = None
        for step in steps:
            if step.get("tool") == "MemoryTool" and step.get("ok"):
                memory_step = step
                break
        
        if memory_step:
            memory_profile_retrieved = True
            data = memory_step.get("data", {})
            # Check if memory profile was actually used in subsequent steps
            profile_used = False
            for step in steps:
                args = step.get("args", {})
                if isinstance(args, dict):
                    filters = args.get("filters", {})
                    if isinstance(filters, dict):
                        # Check if memory profile fields were used
                        if any(key in filters for key in ["categories_any", "categories_all", "price_max"]):
                            # Check if values came from memory
                            pass
                        # Also check query for memory-derived keywords
                        query = args.get("query", "")
                        if query and memory_step.get("data", {}):
                            # Could check if query uses memory categories
                            pass
            
            # For now, just track if memory was retrieved and if any subsequent SQL/SemanticSearch used it
            used_after_memory = False
            memory_idx = steps.index(memory_step) if memory_step in steps else -1
            for step in steps[memory_idx+1:]:
                if step.get("tool") in ("FilterTool", "SearchTool", "SimilarTool"):
                    args = step.get("args", {})
                    if isinstance(args, dict):
                        # Check for $N.path references to memory step
                        for v in args.values():
                            if isinstance(v, str) and v.startswith(f"${memory_idx+1}."):
                                used_after_memory = True
                                break
            
            memory_profile_usage = "retrieved_and_used" if used_after_memory else ("retrieved_not_used" if memory_profile_retrieved else "not_retrieved")
    row["memory_profile_retrieved"] = memory_profile_retrieved
    row["memory_profile_usage"] = memory_profile_usage

    # SemanticSearch keyword quality: check if query tokens are meaningful
    semanticsearch_keyword_quality = None
    if is_planner:
        for step in steps:
            if step.get("tool") == "SearchTool" and step.get("ok"):
                args = step.get("args", {})
                if isinstance(args, dict):
                    query = args.get("query", "")
                    if query:
                        # Basic quality check: non-empty, reasonable length, not just stop words
                        tokens = query.strip().split()
                        if len(tokens) >= 2 and any(len(t) > 2 for t in tokens):
                            semanticsearch_keyword_quality = "good"
                        elif tokens:
                            semanticsearch_keyword_quality = "weak"
                        else:
                            semanticsearch_keyword_quality = "empty"
                        break
    row["semanticsearch_keyword_quality"] = semanticsearch_keyword_quality

    # Tool argument correctness: check if args match expected schema
    tool_argument_correctness = None
    if is_planner and steps:
        correct = 0
        total = 0
        for step in steps:
            if step.get("ok"):
                total += 1
                correct += 1
            else:
                error_kind = step.get("error_kind")
                if error_kind in ("unknown_args", "bad_reference"):
                    total += 1
                elif error_kind not in ("unknown_tool", "invented_id"):
                    total += 1
        tool_argument_correctness = correct / total if total > 0 else None
    row["tool_argument_correctness"] = tool_argument_correctness

    # Aggregated component failure diagnosis
    component_failure_diagnosis = {}
    if is_planner and steps:
        for step in steps:
            tool = step.get("tool", "unknown")
            ok = step.get("ok", False)
            if not ok:
                error_kind = step.get("error_kind", "unknown")
                if tool not in component_failure_diagnosis:
                    component_failure_diagnosis[tool] = {"total_failures": 0, "error_kinds": {}}
                component_failure_diagnosis[tool]["total_failures"] += 1
                component_failure_diagnosis[tool]["error_kinds"][error_kind] = component_failure_diagnosis[tool]["error_kinds"].get(error_kind, 0) + 1
    row["component_failure_diagnosis"] = component_failure_diagnosis

    # Reflection tracking: was reflection actually invoked and did it succeed?
    reflection_invoked = trajectory.get("reflections", 0) > 0 if is_planner else False
    # Reflection succeeded if first_attempt_ok was False but final result is ok
    reflection_succeeded = False
    if reflection_invoked:
        first_ok = trajectory.get("first_attempt_ok", False)
        final_steps_ok = all(s.get("ok", True) for s in trajectory.get("steps", []))
        final_has_rec = len(trajectory.get("recommended", [])) > 0
        # Reflection succeeded if first attempt failed but final succeeded
        reflection_succeeded = (not first_ok) and final_steps_ok and final_has_rec
    row["reflection_invoked"] = reflection_invoked
    row["reflection_succeeded"] = reflection_succeeded

    # Distinguish component states
    component_states = {}
    if is_planner:
        available_tools = set(trajectory.get("tools_available", []))
        for tool_name in ("SimilarTool", "MemoryTool", "SearchTool", "FilterTool", "RankTool", "LookupTool"):
            invoked = any(s.get("tool") == tool_name for s in trajectory.get("steps", []))
            if tool_name not in available_tools:
                component_states[tool_name] = "not_implemented"
            elif not invoked:
                component_states[tool_name] = "not_invoked"
            else:
                # Check if any invocation succeeded
                succeeded = any(s.get("tool") == tool_name and s.get("ok", False) for s in trajectory.get("steps", []))
                failed = any(s.get("tool") == tool_name and not s.get("ok", False) for s in trajectory.get("steps", []))
                if succeeded and not failed:
                    component_states[tool_name] = "invoked_and_succeeded"
                elif failed and not succeeded:
                    component_states[tool_name] = "invoked_and_failed"
                else:
                    component_states[tool_name] = "mixed_results"
    row["component_states"] = component_states

    return row
