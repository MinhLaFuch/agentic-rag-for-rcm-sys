"""Aggregate scored rows: agent -> kind -> segment ("all" = every segment of that kind) -> mean of each metric."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

_ID_KEYS = {"request_id", "agent", "kind", "segment"}

# Columns for which we calculate percentiles (latency and token usage metrics)
_PERCENTILE_COLUMNS = {
    "wall_seconds",
    "llm_latency_seconds",
    "tool_latency_seconds",
    "prompt_tokens",
    "completion_tokens",
    "inference_latency_seconds",
    "inference_prompt_tokens",
    "inference_completion_tokens",
}

# Keys that are known to be non-numeric (dicts, lists, etc.) and should be skipped in summarization
_NON_NUMERIC_KEYS = {
    "component_failure_diagnosis",
    "component_states",
    "exclusion_compliance_detail",
    "per_step_tokens",
    "per_step_latency",
    "per_step_cost",
    "cost_breakdown_by_component",
    "memory_profile_usage",
    "memory_profile_retrieved",
    "semanticsearch_keyword_quality",
    "itemcf_seed_correctness",
    "memory_profile_retrieved",
    "reflection_invoked",
    "reflection_succeeded",
    "itemcf_seed_correctness",
    "ts_plan_valid",
    "ts_steps_ok",
    "ts_has_result",
    "ts_constraint_ok",
    "ts_answer_ok",
    "ts_grounded",
    "love_alignment",
    "hate_violation_rate",
    "exclusion_compliance",
    "category_coverage",
    "target_in_pool",
    "target_reachable",
    "candidate_generation_count",
    "retrieved_count",
    "filtered_count",
    "ranked_count",
    "reachable_only_precision@k",
    "reachable_only_recall@k",
    "reachable_only_hit_rate@k",
    "reachable_only_ndcg@k",
    "category_coverage",
    "distinct_main_categories",
    "target_reachability",
    "itemcf_seed_correctness",
    "memory_profile_retrieved",
    "memory_profile_usage",
    "semanticsearch_keyword_quality",
    "tool_argument_correctness",
    "component_failure_diagnosis",
    "reflection_invoked",
    "reflection_succeeded",
    "component_states",
    "itemcf_seed_correctness",
    "memory_profile_usage",
    "semanticsearch_keyword_quality",
    "tool_argument_correctness",
    "component_failure_diagnosis",
    "reflection_invoked",
    "reflection_succeeded",
    "component_states",
}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["agent"], row["kind"], row["segment"])].append(row)
        buckets[(row["agent"], row["kind"], "all")].append(row)

    out: dict[str, Any] = {}
    for (agent, kind, segment), group in sorted(buckets.items()):
        entry: dict[str, Any] = {"n": len(group)}
        for key in sorted({key for row in group for key in row} - _ID_KEYS):
            if key in _NON_NUMERIC_KEYS:
                continue
            values = [float(row[key]) for row in group if row.get(key) is not None]  # bool -> 0.0/1.0
            if values:
                entry[key] = float(np.mean(values))
                # Add percentiles for latency/token columns
                if key in _PERCENTILE_COLUMNS:
                    entry[f"{key}_p50"] = float(np.percentile(values, 50))
                    entry[f"{key}_p95"] = float(np.percentile(values, 95))
        out.setdefault(agent, {}).setdefault(kind, {})[segment] = entry
    return out
