"""Layer 5: Deployment, Safety & Efficiency metrics."""

from __future__ import annotations

from typing import Any

from package.evaluation._schema import PLANNER_AGENTS


def score_layer5_deployment(
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """
    Score deployment metrics including token usage and latency.

    Returns:
        Dict with keys: prompt_tokens, completion_tokens, llm_latency_seconds,
                       tool_latency_seconds, wall_seconds, inference_attempts,
                       inference_prompt_tokens, inference_completion_tokens,
                       inference_latency_seconds
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
    
    return row
