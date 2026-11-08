"""Layer 1: Recommendation Outcome metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from package.data import ITEM_ID_SEPARATOR
from package.tools.corpus import ItemCorpus
from package.evaluation.recommender.metrics.ranking import ranking_metrics_at_k


def score_layer1_outcome(
    request: Any,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    k: int,
    seen_item_ids: set[int] | None = None,
    corpus: ItemCorpus | None = None,
) -> dict[str, Any]:
    """
    Score recommendation outcome against ground truth targets.

    Args:
        request: AgentRequest with kind, targets, seed_item_id, category, etc.
        trajectory: Trajectory dict with 'recommended' list
        item2id: Mapping from item_id string to item_idx int
        k: Number of recommendations to consider
        seen_item_ids: Set of item_idx the user has seen in their fit history (for seen_item_rate)
        corpus: ItemCorpus for category/main_category lookups

    Returns:
        Dict with keys: n_recommended, precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k,
                       seen_item_rate, seed_in_result, distinct_domains, distinct_main_categories,
                       target_in_pool, target_reachable, candidate_generation_count, retrieved_count,
                       filtered_count, ranked_count, reachable_only_precision@k, reachable_only_recall@k,
                       reachable_only_hit_rate@k, reachable_only_ndcg@k, category_coverage,
                       target_reachability
    """
    # Deduplicate recommendations and limit to k
    rec = list(dict.fromkeys(trajectory["recommended"]))[:k]

    row: dict[str, Any] = {"n_recommended": len(rec)}

    # ===== Target Reachability =====
    # Check if target items exist in the corpus (S0: target in pool)
    if request.targets and corpus is not None:
        target_in_pool = 0
        for target_idx in request.targets:
            # Check if target item exists in corpus
            item_id = None
            # We need to find item_id from item_idx
            # This requires reverse lookup - we'll use a different approach
            pass
        row["target_in_pool"] = None  # Placeholder - requires reverse mapping
        row["target_reachable"] = None  # Placeholder - requires catalog check
    else:
        row["target_in_pool"] = None
        row["target_reachable"] = None

    # Calculate ranking metrics only for non-ambiguous requests with targets
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

    # seen_item_rate: proportion of top-k items the user has seen in their fit history
    if seen_item_ids is not None and rec:
        seen_count = sum(1 for item_id in rec if item2id.get(item_id, -1) in seen_item_ids)
        row["seen_item_rate"] = seen_count / len(rec)
    else:
        row["seen_item_rate"] = None

    # seed_in_result: for 'similar' kind, whether the seed item is in top-k
    if request.kind == "similar" and request.seed_item_id and rec:
        row["seed_in_result"] = request.seed_item_id in rec
    else:
        row["seed_in_result"] = None

    # distinct_domains: number of unique domains (prefix before ITEM_ID_SEPARATOR) in top-k
    if rec:
        domains = set()
        for item_id in rec:
            if ITEM_ID_SEPARATOR in item_id:
                domain = item_id.split(ITEM_ID_SEPARATOR)[0]
                domains.add(domain)
        row["distinct_domains"] = len(domains)
    else:
        row["distinct_domains"] = None

    # distinct_main_categories: number of unique main_categories from corpus in top-k
    if corpus is not None and rec:
        main_cats = set()
        for item_id in rec:
            rows, _ = corpus.select(
                "SELECT main_category FROM items WHERE item_id = ?",
                (item_id,),
                max_rows=1
            )
            if rows and rows[0]["main_category"]:
                main_cats.add(rows[0]["main_category"])
        row["distinct_main_categories"] = len(main_cats)
    else:
        row["distinct_main_categories"] = None

    # ===== Retrieval Funnel Metrics (S0-S5) =====
    row["target_in_pool"] = None
    row["target_reachable"] = None
    row["candidate_generation_count"] = None
    row["retrieved_count"] = None
    row["filtered_count"] = None
    row["ranked_count"] = None
    row["reachable_only_precision@k"] = None
    row["reachable_only_recall@k"] = None
    row["reachable_only_hit_rate@k"] = None
    row["reachable_only_ndcg@k"] = None

    # Category coverage: for constrained/cold_text, proportion of target categories covered in recommendations
    if request.kind in ("constrained", "cold_text") and request.category and corpus is not None and rec:
        rec_cats = set()
        for item_id in rec:
            rows, _ = corpus.select(
                "SELECT main_category FROM items WHERE item_id = ?",
                (item_id,),
                max_rows=1
            )
            if rows and rows[0]["main_category"]:
                rec_cats.add(rows[0]["main_category"])
        row["category_coverage"] = 1.0 if request.category in rec_cats else 0.0
    else:
        row["category_coverage"] = None

    return row


def _extract_retrieval_funnel(
    trajectory: dict[str, Any],
    item2id: Mapping[str, int],
    k: int,
    corpus: Any = None,
) -> dict[str, Any]:
    """
    Extract retrieval funnel metrics from trajectory steps.
    
    Stages:
    S0: Target in pool (all items matching constraints in corpus)
    S1: Candidate generation (items from retrieval tools)
    S2: Retrieval (items returned by the retrieval tool)
    S3: Filtering (items after filters applied)
    S4: Ranking (items after RankTool)
    S5: Final inclusion (items in final recommendations)
    
    Returns dict with funnel metrics.
    """
    steps = trajectory.get("steps", [])
    if not steps:
        return {}
    
    # Find retrieval and ranking steps
    retrieval_steps = []
    ranking_steps = []
    
    for step in steps:
        tool = step.get("tool", "")
        if step.get("ok") and tool in ("FilterTool", "SearchTool", "SimilarTool"):
            retrieval_steps.append(step)
        elif step.get("ok") and tool == "RankTool":
            ranking_steps.append(step)
    
    funnel = {}
    
    # Candidate generation: total candidates from all retrieval steps
    total_candidates = 0
    for step in retrieval_steps:
        data = step.get("data", {})
        candidates = data.get("candidates", [])
        total_candidates += len(candidates) if isinstance(candidates, list) else 0
    funnel["candidate_generation_count"] = total_candidates
    
    # Retrieved: unique candidates from retrieval
    retrieved_items = set()
    for step in retrieval_steps:
        data = step.get("data", {})
        candidates = data.get("candidates", [])
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict) and "item_id" in c:
                    retrieved_items.add(c["item_id"])
                elif isinstance(c, str):
                    retrieved_items.add(c)
    funnel["retrieved_count"] = len(retrieved_items)
    
    # Filtered: items after RankTool ranking (if available)
    if ranking_steps:
        last_ranking = ranking_steps[-1]
        data = last_ranking.get("data", {})
        ranked = data.get("ranked", [])
        filtered_items = set()
        if isinstance(ranked, list):
            for r in ranked:
                if isinstance(r, dict) and "item_id" in r:
                    filtered_items.add(r["item_id"])
        funnel["filtered_count"] = len(filtered_items)
        funnel["ranked_count"] = len(filtered_items)
    else:
        funnel["filtered_count"] = funnel["retrieved_count"]
        funnel["ranked_count"] = funnel["retrieved_count"]
    
    return funnel
