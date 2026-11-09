"""Layer 5: Deployment, Safety & Efficiency metrics."""

from __future__ import annotations

from typing import Any

from package.evaluation import PLANNER_AGENTS
from package.agents.planner import check_time_budget_error


def score_layer5_deployment(
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """
    Score deployment metrics including token usage and latency.

    Returns:
        Dict with keys: prompt_tokens, completion_tokens, llm_latency_seconds,
                       tool_latency_seconds, wall_seconds, inference_attempts,
                       inference_prompt_tokens, inference_completion_tokens,
                       inference_latency_seconds, provider_error, sql_time_budget_hits,
                       per_step_tokens, per_step_latency, per_step_cost,
                       cost_per_request, cost_per_successful_request,
                       cost_breakdown_by_component, latency_distribution
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS
    steps = trajectory["steps"]
    usage = trajectory.get("usage") or {}
    inference = trajectory.get("inference_usage") or {}
    answered = trajectory.get("answer_status") is not None

    row: dict[str, Any] = {
        "prompt_tokens": usage.get("prompt_tokens") if is_planner else None,
        "completion_tokens": usage.get("completion_tokens") if is_planner else None,
        "llm_latency_seconds": usage.get("latency_seconds") if is_planner else None,
        "tool_latency_seconds": sum(s.get("latency_seconds", 0.0) for s in steps) if is_planner else None,
        "wall_seconds": trajectory.get("wall_seconds"),
    }

    # Inference-specific metrics (only when trajectory has an answer)
    for key in ("attempts", "prompt_tokens", "completion_tokens", "latency_seconds"):
        row[f"inference_{key}"] = inference.get(key) if answered else None

    # provider_error: from trajectory field
    row["provider_error"] = trajectory.get("provider_error", False)

    # sql_time_budget_hits: count steps with time budget errors
    if is_planner and steps:
        sql_time_budget_hits = sum(1 for s in steps if check_time_budget_error(s.get("error")))
        row["sql_time_budget_hits"] = sql_time_budget_hits
    else:
        row["sql_time_budget_hits"] = None

    # ===== Per-step breakdown =====
    per_step_tokens = []
    per_step_latency = []
    per_step_cost = []
    
    if is_planner and steps:
        for i, step in enumerate(steps):
            step_tokens = step.get("tokens", {})
            step_latency = step.get("latency_seconds", 0.0)
            step_cost = step.get("cost", 0.0)
            
            per_step_tokens.append({
                "step": i + 1,
                "tool": step.get("tool"),
                "prompt_tokens": step_tokens.get("prompt_tokens", 0),
                "completion_tokens": step_tokens.get("completion_tokens", 0),
                "total_tokens": step_tokens.get("prompt_tokens", 0) + step_tokens.get("completion_tokens", 0),
            })
            per_step_latency.append({
                "step": i + 1,
                "tool": step.get("tool"),
                "latency_seconds": step_latency,
            })
            per_step_cost.append({
                "step": i + 1,
                "tool": step.get("tool"),
                "cost_usd": step_cost,
            })
    
    row["per_step_tokens"] = per_step_tokens
    row["per_step_latency"] = per_step_latency
    row["per_step_cost"] = per_step_cost

    # Cost per request and per successful request
    total_cost = sum(step.get("cost", 0.0) for step in steps) if is_planner else 0.0
    row["cost_per_request"] = total_cost
    row["cost_per_successful_request"] = total_cost if trajectory.get("task_success") else None

    # Cost breakdown by component
    cost_breakdown = {}
    if is_planner and steps:
        for step in steps:
            tool = step.get("tool", "unknown")
            cost = step.get("cost", 0.0)
            if tool not in cost_breakdown:
                cost_breakdown[tool] = 0.0
            cost_breakdown[tool] += cost
    row["cost_breakdown_by_component"] = cost_breakdown

    # Latency distribution
    latencies = [s.get("latency_seconds", 0.0) for s in steps] if is_planner and steps else []
    if latencies:
        import numpy as np
        row["latency_p50"] = float(np.percentile(latencies, 50))
        row["latency_p95"] = float(np.percentile(latencies, 95))
        row["latency_p99"] = float(np.percentile(latencies, 99))
        row["latency_mean"] = float(np.mean(latencies))
        row["latency_std"] = float(np.std(latencies))
    else:
        row["latency_p50"] = None
        row["latency_p95"] = None
        row["latency_p99"] = None
        row["latency_mean"] = None
        row["latency_std"] = None

    return row
