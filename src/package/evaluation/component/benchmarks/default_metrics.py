"""Default metrics for memory utility analysis."""

from __future__ import annotations


def default_metrics(k: int) -> list[str]:
    return ["task_success", f"recall@{k}", f"ndcg@{k}", "constraint_satisfaction", "first_attempt_ok",
            "completion_tokens", "llm_latency_seconds"]