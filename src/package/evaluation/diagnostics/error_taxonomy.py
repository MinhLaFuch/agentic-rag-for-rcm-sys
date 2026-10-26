"""Diagnostics for error taxonomy."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def error_taxonomy(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Classify errors by type (step-level and plan-level) by agent and kind.

    Args:
        trajectories: List of trajectory dicts

    Returns:
        Dict with structure:
        {
            "agent": {
                "kind": {
                    "step_errors": {
                        "unknown_tool": int,
                        "invented_id": int,
                        "unknown_args": int,
                        "bad_reference": int,
                        "tool_error": int,
                        "exception": int,
                        "None": int,  # steps with no error
                    },
                    "plan_errors": {
                        "plan_invalid": int,  # trajectory["error"] starts with ValueError
                        "provider_error": int,  # trajectory["provider_error"] == True
                    }
                }
            }
        }
    """
    # Group by agent and kind
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for traj in trajectories:
        groups[(traj["agent"], traj.get("kind", "unknown"))].append(traj)

    result: dict[str, Any] = {}

    for (agent, kind), group in sorted(groups.items()):
        agent_data = result.setdefault(agent, {})
        kind_data = agent_data.setdefault(kind, {})

        # Count step errors
        step_error_counts: dict[str, int] = defaultdict(int)
        for traj in group:
            for step in traj.get("steps", []):
                error_kind = step.get("error_kind", None)
                if error_kind is None:
                    step_error_counts["None"] += 1
                else:
                    step_error_counts[error_kind] += 1

        kind_data["step_errors"] = dict(step_error_counts)

        # Count plan errors
        plan_invalid = 0
        provider_error = 0
        for traj in group:
            if traj.get("error"):
                if isinstance(traj["error"], str) and traj["error"].startswith("ValueError"):
                    plan_invalid += 1
            if traj.get("provider_error"):
                provider_error += 1

        kind_data["plan_errors"] = {
            "plan_invalid": plan_invalid,
            "provider_error": provider_error,
        }

    return result
