"""Layer 3: Grounded Retrieval & Evidence metrics."""

from __future__ import annotations

from typing import Any

from package.evaluation._schema import ANSWER_STATUSES


def score_layer3_grounding(
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """
    Score answer grounding and fallback status.

    Returns:
        Dict with keys: answer_status_ok, answer_status_ask_user, answer_status_no_result,
                       answer_status_tool_error, answer_grounded, answer_fallback
    """
    status = trajectory.get("answer_status")
    answered = status is not None
    shown = status == "ok"
    inference = trajectory.get("inference_usage") or {}
    
    row: dict[str, Any] = {}
    
    # Answer status flags
    for name in ANSWER_STATUSES:
        row[f"answer_status_{name}"] = (status == name) if answered else None
    
    # Grounding metrics (only for status "ok")
    row["answer_grounded"] = bool(trajectory.get("answer_grounded")) if shown else None
    row["answer_fallback"] = bool(trajectory.get("answer_fallback")) if shown else None
    
    return row
