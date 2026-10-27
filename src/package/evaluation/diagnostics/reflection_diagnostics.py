"""Diagnostics for reflection behavior."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def reflection_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze reflection behavior by agent and kind.

    Args:
        rows: List of scored rows from evaluation

    Returns:
        Dict with structure:
        {
            "agent": {
                "kind": {
                    "n_first_failed": int,  # number of requests where first_attempt_ok == False
                    "rescue_rate": float,   # mean task_success among first_failed (None if empty)
                    "mean_reflections": float,
                    "constraint_blind_spot_rate": float,  # for constrained/cold_text with recommendations,
                                                         # rate of constraint_satisfaction < 1 with reflections == 0
                }
            }
        }
    """
    from package.evaluation._schema import ORACLE_KINDS

    # Group by agent and kind
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["agent"], row["kind"])].append(row)

    result: dict[str, Any] = {}

    for (agent, kind), group in sorted(groups.items()):
        agent_data = result.setdefault(agent, {})
        kind_data = agent_data.setdefault(kind, {})

        # n_first_failed: count where first_attempt_ok == False
        first_failed = [r for r in group if r.get("first_attempt_ok") is False]
        kind_data["n_first_failed"] = len(first_failed)

        # rescue_rate: mean task_success among first_failed
        if first_failed:
            rescue_success = [r.get("task_success") for r in first_failed if r.get("task_success") is not None]
            kind_data["rescue_rate"] = sum(rescue_success) / len(rescue_success) if rescue_success else None
        else:
            kind_data["rescue_rate"] = None

        # mean_reflections
        reflections = [r.get("reflections", 0) for r in group if r.get("reflections") is not None]
        kind_data["mean_reflections"] = sum(reflections) / len(reflections) if reflections else 0.0

        # constraint_blind_spot_rate: for constrained/cold_text with recommendations,
        # rate of constraint_satisfaction < 1 with reflections == 0
        if kind in ORACLE_KINDS:
            has_rec = [r for r in group if r.get("n_recommended", 0) > 0]
            if has_rec:
                blind_spots = [
                    r for r in has_rec
                    if r.get("constraint_satisfaction", 1.0) < 1.0 and r.get("reflections", 0) == 0
                ]
                kind_data["constraint_blind_spot_rate"] = len(blind_spots) / len(has_rec)
            else:
                kind_data["constraint_blind_spot_rate"] = None
        else:
            kind_data["constraint_blind_spot_rate"] = None

    return result
