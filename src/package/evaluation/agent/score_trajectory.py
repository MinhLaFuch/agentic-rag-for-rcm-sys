"""Score one agent trajectory against its request. Failures count as zeros (an error is not a skipped sample)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from ...tools.corpus import ItemCorpus
from ...tools.evaluation.metrics import ranking_metrics_at_k
from ._dataclass import AgentRequest
from ._helper import items_satisfying, items_without_price
from ._schema import ANSWER_STATUSES, PLANNER_AGENTS
from .reference_groups import reference_groups


def _follows(called: list[str], groups: list[tuple[str, ...]]) -> bool:
    position = 0
    for tool in called:
        if position < len(groups) and tool in groups[position]:
            position += 1
    return position == len(groups)


def _add_answer_columns(row: dict[str, Any], trajectory: dict[str, Any]) -> None:
    status = trajectory.get("answer_status")
    answered = status is not None
    shown = status == "ok"
    inference = trajectory.get("inference_usage") or {}
    for name in ANSWER_STATUSES:
        row[f"answer_status_{name}"] = (status == name) if answered else None
    row["answer_grounded"] = bool(trajectory.get("answer_grounded")) if shown else None
    row["answer_fallback"] = bool(trajectory.get("answer_fallback")) if shown else None
    for key in ("attempts", "prompt_tokens", "completion_tokens", "latency_seconds"):
        row[f"inference_{key}"] = inference.get(key) if answered else None


def score_trajectory(
    request: AgentRequest,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    corpus: ItemCorpus,
    k: int,
) -> dict[str, Any]:
    """
    trajectory: {agent, plan, ask_user, steps[{tool, ok, invented_ids, latency_seconds}], recommended[item_id],
                 usage{attempts, prompt_tokens, completion_tokens, latency_seconds}, error, truncated,
                 tools_available, wall_seconds, reflections, first_attempt_ok,
                 answer_status, answer_grounded, answer_fallback, inference_usage}   (the last four: Inference, see below)
    `steps` / `recommended` are the FINAL attempt (after plan-reflect), so task_success is "right after fixing";
    first_attempt_ok is "right without fixing". Trajectories written before plan-reflect: reflections=0, first_attempt_ok=None.
    Returns one flat row of numbers/bools/None (None = metric not defined for this agent/kind).

    Inference columns (None when the trajectory has no answer: baseline, or a trajectory written before Inference existed):
      answer_status_<status>     whether the answer had that status (their means are the share of each status)
      answer_grounded            the answer text passed the grounding checks      (only for status "ok", else None)
      answer_fallback            the LLM answer was replaced by the template      (only for status "ok", else None)
      inference_*                tokens / latency / attempts of Inference's own LLM calls, apart from the planner's `usage`
    None of them is read by task_success, the ranking metrics or any other column above.
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS
    steps = trajectory["steps"]
    # A duplicate item must not occupy multiple ranking positions or inflate recall.
    rec = list(dict.fromkeys(trajectory["recommended"]))[:k]
    usage = trajectory.get("usage") or {}
    plan_valid = trajectory["error"] is None
    asked = bool(plan_valid and is_planner and not steps and trajectory.get("ask_user"))

    row: dict[str, Any] = {
        "request_id": request.request_id,
        "agent": agent,
        "kind": request.kind,
        "segment": request.segment,
        "plan_valid": plan_valid,
        "plan_attempts": usage.get("attempts") if is_planner else None,
        "plan_truncated": bool(trajectory.get("truncated")) if is_planner else None,
        "n_steps": len(steps) if is_planner else None,
        "steps_ok_rate": (sum(s["ok"] for s in steps) / len(steps)) if steps else None,
        "invented_ids": sum(len(s.get("invented_ids", [])) for s in steps) if is_planner else None,
        "asked_clarification": asked if is_planner else None,
        "reflections": int(trajectory.get("reflections") or 0) if is_planner else None,
        "first_attempt_ok": trajectory.get("first_attempt_ok") if is_planner else None,
        "n_recommended": len(rec),
        "prompt_tokens": usage.get("prompt_tokens") if is_planner else None,
        "completion_tokens": usage.get("completion_tokens") if is_planner else None,
        "llm_latency_seconds": usage.get("latency_seconds") if is_planner else None,
        "tool_latency_seconds": sum(s.get("latency_seconds", 0.0) for s in steps) if is_planner else None,
        "wall_seconds": trajectory.get("wall_seconds"),
    }

    _add_answer_columns(row, trajectory)

    if is_planner:
        if request.kind == "ambiguous":
            row["tool_selection_ok"] = asked  # the right plan is "no steps + a question"
        else:
            groups = reference_groups(request.kind, set(trajectory.get("tools_available", [])))
            row["tool_selection_ok"] = _follows([s["tool"] for s in steps], groups)
    else:
        row["tool_selection_ok"] = None

    ranking_keys = (f"precision@{k}", f"recall@{k}", f"hit_rate@{k}", f"ndcg@{k}", f"mrr@{k}", f"map@{k}")
    if request.kind != "ambiguous" and request.targets:
        relevant = set(request.targets)
        hits = np.zeros((1, k))
        for rank, item_id in enumerate(rec):
            hits[0, rank] = float(item2id.get(item_id, -1) in relevant)
        metrics = ranking_metrics_at_k(hits, np.array([len(relevant)]), k)
        row.update({key: float(metrics[key][0]) for key in ranking_keys})
    else:
        row.update({key: None for key in ranking_keys})

    constrained = request.kind in ("constrained", "cold_text")
    if constrained:
        ok_items = items_satisfying(corpus, rec, request.price_max, request.category)
        row["constraint_satisfaction"] = (len(ok_items) / len(rec)) if rec else 0.0
        row["price_unknown_rate"] = (len(items_without_price(corpus, rec)) / len(rec)) if rec and request.price_max else None
    else:
        row["constraint_satisfaction"] = None
        row["price_unknown_rate"] = None

    if request.kind == "ambiguous":
        row["task_success"] = asked
    else:
        steps_ok = all(s["ok"] for s in steps)
        row["task_success"] = bool(
            plan_valid and steps_ok and rec and (row["constraint_satisfaction"] == 1.0 if constrained else True)
        )
    if request.kind == "personalized" and is_planner and "MemoryTool" not in trajectory.get("tools_available", []):
        # a planner that cannot read the user's history has no honest way to personalize: not scored (asking back is fine)
        row["tool_selection_ok"] = row["task_success"] = None
    return row
