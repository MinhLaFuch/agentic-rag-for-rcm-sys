"""Diagnostics for failure rates."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def failure_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate failure rates by agent and kind.

    Args:
        rows: List of scored rows from evaluation

    Returns:
        Dict with structure:
        {
            "agent": {
                "kind": {
                    "answer_status_tool_error_rate": float,  # rate of answer_status == "tool_error"
                    "answer_status_no_result_rate": float,   # rate of answer_status == "no_result"
                    "provider_error_rate": float,             # rate of provider_error == True
                    "sql_time_budget_hits_rate": float,       # mean sql_time_budget_hits (per trajectory)
                }
            }
        }
    """
    # Group by agent and kind
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["agent"], row["kind"])].append(row)

    result: dict[str, Any] = {}

    for (agent, kind), group in sorted(groups.items()):
        agent_data = result.setdefault(agent, {})
        kind_data = agent_data.setdefault(kind, {})

        n = len(group)

        # answer_status_tool_error_rate
        tool_error_count = sum(1 for r in group if r.get("answer_status_tool_error") is True)
        kind_data["answer_status_tool_error_rate"] = tool_error_count / n if n > 0 else 0.0

        # answer_status_no_result_rate
        no_result_count = sum(1 for r in group if r.get("answer_status_no_result") is True)
        kind_data["answer_status_no_result_rate"] = no_result_count / n if n > 0 else 0.0

        # provider_error_rate
        provider_error_count = sum(1 for r in group if r.get("provider_error") is True)
        kind_data["provider_error_rate"] = provider_error_count / n if n > 0 else 0.0

        # sql_time_budget_hits_rate: mean of sql_time_budget_hits
        budget_hits = [r.get("sql_time_budget_hits", 0) for r in group if r.get("sql_time_budget_hits") is not None]
        kind_data["sql_time_budget_hits_rate"] = sum(budget_hits) / len(budget_hits) if budget_hits else 0.0

    return result
