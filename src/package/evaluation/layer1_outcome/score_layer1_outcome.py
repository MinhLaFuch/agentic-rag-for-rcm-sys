"""Layer 1: Recommendation Outcome metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from package.data import ITEM_ID_SEPARATOR
from package.corpus import ItemCorpus
from package.evaluation.recommender.metrics.ranking import ranking_metrics_at_k


def score_layer1_outcome(
    request: Any,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    k: int,
    seen_item_ids: set[int] | None = None,
    corpus: ItemCorpus | None = None,
    id2item: Mapping[int, str] | None = None,
    itemcf_reachable: set[int] | None = None,
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

    # ===== Target pool availability (per retrieval path) =====
    # The system has no single eligible item universe: SQL/BM25/Lookup read the
    # corpus `items` table (temporally masked when a metadata policy is active),
    # ItemCF reads the similarity matrix, and the scorer has its own index bounds.
    # `target_in_pool` therefore stays None; per-path availability lives in
    # `target_in_pool_{sql,semantic,itemcf}` and per-target detail in
    # `target_pool_detail` (input to stage-loss diagnostics, not to Recall).
    row["target_in_pool"] = None
    row["target_reachable"] = None  # defined together with stage_lost (R3)
    row["target_pool_detail"] = None
    for _path in ("sql", "semantic", "itemcf"):
        row[f"target_in_pool_{_path}"] = None
    if request.targets and corpus is not None and id2item is not None:
        detail = _target_pool_detail(request.targets, id2item, corpus, itemcf_reachable)
        row["target_pool_detail"] = detail
        for path in ("sql", "semantic", "itemcf"):
            row[f"target_in_pool_{path}"] = _pool_path_verdict(detail, path)

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

    # Steps recorded before tool `data` was persisted carry no candidate/ranked
    # payloads: the funnel is unmeasurable, not zero. Only emit counts when every
    # relevant step reports a data dict (an empty dict is a genuine empty result).
    relevant_steps = retrieval_steps + ranking_steps
    if relevant_steps and not all(isinstance(s.get("data"), dict) for s in relevant_steps):
        return {}

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




def _target_pool_detail(
    targets: list[int],
    id2item: Mapping[int, str],
    corpus: ItemCorpus,
    itemcf_reachable: set[int] | None,
) -> dict[str, dict[str, bool | None]]:
    """Per-target, per-path pool membership. None = availability unknown, never a silent False.

    - sql / semantic: the corpus `items` table as the tools see it (the TEMP views
      installed by apply_metadata_policy make first_seen_ts <= as_of filtering
      automatic; the dormant dense leg shares the same corpus universe).
    - itemcf: target index has a nonzero column in the ItemKNN similarity matrix
      (i.e. is some item's kept neighbour), and — only when the temporal metadata
      policy is active — is also visible in the corpus, mirroring SimilarTool.
    """
    detail: dict[str, dict[str, bool | None]] = {}
    resolvable: list[tuple[int, str]] = []
    for target_idx in targets:
        item_id = id2item.get(target_idx)
        if item_id is None:
            detail[str(target_idx)] = {"sql": None, "semantic": None, "itemcf": None}
        else:
            resolvable.append((target_idx, item_id))
    if not resolvable:
        return detail

    visible = set(corpus.item_domains([item_id for _, item_id in resolvable]))
    enforce_cf_visibility = bool(
        (getattr(corpus, "_evaluation_metadata_policy", None) or {}).get("first_seen_filter")
    )
    for target_idx, item_id in resolvable:
        in_catalog = item_id in visible
        entry: dict[str, bool | None] = {"sql": in_catalog, "semantic": in_catalog, "itemcf": None}
        if itemcf_reachable is not None:
            entry["itemcf"] = target_idx in itemcf_reachable and (not enforce_cf_visibility or in_catalog)
        detail[str(target_idx)] = entry
    return detail


def _pool_path_verdict(detail: dict[str, dict[str, bool | None]], path: str) -> bool | None:
    """Existential verdict for one retrieval path: True if any target is eligible,
    False only when every target is measurably absent, None when any is unknown."""
    values = [entry[path] for entry in detail.values()]
    if any(v is True for v in values):
        return True
    if not values or any(v is None for v in values):
        return None
    return False
