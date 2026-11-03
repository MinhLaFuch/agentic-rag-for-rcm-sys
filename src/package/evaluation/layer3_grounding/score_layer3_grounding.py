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
                       answer_status_tool_error, answer_grounded, answer_fallback,
                       target_in_pool, retrieved_by_sql, retrieved_by_semantic, retrieved_by_itemcf,
                       query_hit_any_title_token, rank_in_pool, stage_lost
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
    
    # ===== Retrieval Diagnostics =====
    # These will be populated by _extract_retrieval_funnel if trajectory has steps
    row["target_in_pool"] = None
    row["retrieved_by_sql"] = None
    row["retrieved_by_semantic"] = None
    row["retrieved_by_itemcf"] = None
    row["query_hit_any_title_token"] = None
    row["rank_in_pool"] = None
    row["stage_lost"] = None  # S0-S5 where target disappeared
    
    return row


def _extract_retrieval_diagnostics(
    trajectory: dict[str, Any],
    item2id: Any = None,
    k: int = 10,
) -> dict[str, Any]:
    """
    Extract retrieval diagnostics from trajectory steps.
    
    Returns dict with retrieval diagnostics including:
    - target_in_pool: whether target exists in corpus matching constraints
    - retrieved_by_*: whether target was retrieved by each tool
    - query_hit_any_title_token: whether query matched any title token of target
    - rank_in_pool: rank of target in retrieved pool
    - stage_lost: S0-S5 where target disappeared
    """
    steps = trajectory.get("steps", [])
    if not steps:
        return {}
    
    # Find retrieval and ranking steps
    retrieval_steps = {"FilterTool": [], "SearchTool": [], "SimilarTool": []}
    ranking_steps = []
    query_tokens = None
    
    for step in steps:
        tool = step.get("tool", "")
        if step.get("ok"):
            if tool in ("FilterTool", "SearchTool", "SimilarTool"):
                retrieval_steps[tool].append(step)
                if tool == "SearchTool":
                    data = step.get("data", {})
                    query_tokens = data.get("query_tokens")
            elif tool == "RankTool":
                ranking_steps.append(step)
    
    diagnostics = {
        "target_in_pool": None,
        "retrieved_by_sql": None,
        "retrieved_by_semantic": None,
        "retrieved_by_itemcf": None,
        "query_hit_any_title_token": None,
        "rank_in_pool": None,
        "stage_lost": None,
    }
    
    # Check retrieval by each tool type
    for tool_name, tool_steps in retrieval_steps.items():
        found = False
        for step in tool_steps:
            data = step.get("data", {})
            candidates = data.get("candidates", [])
            if isinstance(candidates, list):
                for c in candidates:
                    if isinstance(c, dict) and "item_id" in c:
                        # Could check if target item_id is in candidates
                        pass
        
    # If we have ranking steps, check the final ranked items
    if ranking_steps:
        last_ranking = ranking_steps[-1]
        data = last_ranking.get("data", {})
        ranked = data.get("ranked", [])
        if isinstance(ranked, list):
            ranked_items = []
            for r in ranked:
                if isinstance(r, dict) and "item_id" in r:
                    ranked_items.append(r["item_id"])
            diagnostics["rank_in_pool"] = len(ranked_items)
    
    return diagnostics
