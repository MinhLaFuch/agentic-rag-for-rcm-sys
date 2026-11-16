"""Layer 1: Recommendation Outcome metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from package.data import ITEM_ID_SEPARATOR
from package.corpus import ItemCorpus
from package.evaluation.recommender.metrics.ranking import ranking_metrics_at_k
from package.tools.retrieval.tokenize_search_query import tokenize_search_query


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
                       target_in_pool, target_in_any_path_pool, target_reachable,
                       candidate_generation_count, retrieved_count,
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
    row["target_in_any_path_pool"] = None
    row["target_reachable"] = None  # defined together with stage_lost (R3)
    row["target_pool_detail"] = None
    for _path in ("sql", "semantic", "itemcf"):
        row[f"target_in_pool_{_path}"] = None
    if request.targets and corpus is not None and id2item is not None:
        detail = _target_pool_detail(request.targets, id2item, corpus, itemcf_reachable)
        row["target_pool_detail"] = detail
        for path in ("sql", "semantic", "itemcf"):
            row[f"target_in_pool_{path}"] = _pool_path_verdict(detail, path)
        row["target_in_any_path_pool"] = _any_path_pool_verdict(detail)

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


def _any_path_pool_verdict(detail: dict[str, dict[str, bool | None]]) -> bool | None:
    """Existential verdict across every (target, path) pool entry: True if any
    target is eligible on any path, False only when every entry is measurably
    absent, None when any entry is unknown. Unlike `target_in_pool` (no single
    eligible universe), this answers "could some path have delivered a target"."""
    values = [v for entry in detail.values() for v in entry.values()]
    if any(v is True for v in values):
        return True
    if not values or any(v is None for v in values):
        return None
    return False


def _pool_path_verdict(detail: dict[str, dict[str, bool | None]], path: str) -> bool | None:
    """Existential verdict for one retrieval path: True if any target is eligible,
    False only when every target is measurably absent, None when any is unknown."""
    values = [entry[path] for entry in detail.values()]
    if any(v is True for v in values):
        return True
    if not values or any(v is None for v in values):
        return None
    return False


# Retrieval path -> tools whose `data.candidates` feed that path. LookupTool is a
# fetch/enrichment step (item_ids in, metadata out), not candidate discovery, so it
# is not a retrieval path here.
_PATH_TOOLS = {"sql": ("FilterTool",), "semantic": ("SearchTool",), "itemcf": ("SimilarTool",)}
_PATHS = ("sql", "semantic", "itemcf")

# Loss stages, ordered by how far the target got. "survived" = reached `recommended`.
_STAGE_ORDER = {
    "pool": 0,
    "retrieve": 1,
    "rank_input": 2,
    "rank_unscored": 3,
    "rank_excluded_seen": 3,
    "rank_topk": 4,
    "final": 5,
    "survived": 6,
}


def _step_item_ids(rows: Any) -> set[str]:
    """item_id strings from a tool `candidates`/`ranked`/`items` list."""
    ids: set[str] = set()
    if not isinstance(rows, list):
        return ids
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("item_id"), str):
            ids.add(r["item_id"])
        elif isinstance(r, str):
            ids.add(r)
    return ids


def _path_candidates(steps: list[dict[str, Any]], tools: tuple[str, ...]) -> tuple[bool, set[str] | None]:
    """(exercised, candidate item_ids or None when unmeasurable).

    exercised = at least one ok step for these tools ran. The candidate set is
    None when any exercised step lacks a dict `data` (pre-R1 trajectories),
    mirroring the funnel's missing-data-is-unknown rule.
    """
    relevant = [s for s in steps if s.get("tool") in tools and s.get("ok")]
    if not relevant:
        return False, None
    if not all(isinstance(s.get("data"), dict) for s in relevant):
        return True, None
    ids: set[str] = set()
    for s in relevant:
        ids |= _step_item_ids(s["data"].get("candidates"))
    return True, ids


def _search_query_tokens(steps: list[dict[str, Any]]) -> set[str] | None:
    """Union of query_tokens across ok SearchTool steps; None when unmeasurable
    (no SearchTool ran, or any ran without persisted data — pre-R1 trajectories)."""
    search_steps = [s for s in steps if s.get("tool") == "SearchTool" and s.get("ok")]
    if not search_steps:
        return None
    if not all(isinstance(s.get("data"), dict) for s in search_steps):
        return None
    tokens: set[str] = set()
    for s in search_steps:
        for t in s["data"].get("query_tokens") or []:
            if isinstance(t, str):
                tokens.add(t)
    return tokens


def _query_hit_title_verdict(
    targets: list[int],
    id2item: Mapping[int, str],
    corpus: ItemCorpus,
    query_tokens: set[str] | None,
) -> bool | None:
    """Existential verdict: True if any target's title shares a token with any
    issued search query (lexical reachability of the BM25 path); False only when
    every target title is measurable and misses; None when unmeasurable."""
    if query_tokens is None:
        return None
    values: list[bool | None] = []
    for target_idx in targets:
        item_id = id2item.get(target_idx)
        title = None
        if item_id is not None:
            rows, _ = corpus.select(
                "SELECT title FROM items WHERE item_id = ?", (item_id,), max_rows=1
            )
            if rows and isinstance(rows[0].get("title"), str):
                title = rows[0]["title"]
        if not title:
            values.append(None)
            continue
        values.append(bool(set(tokenize_search_query(title)) & query_tokens))
    if any(v is True for v in values):
        return True
    if not values or any(v is None for v in values):
        return None
    return False


def _last_ranker(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Data of the last ok RankTool step, or None when absent/unmeasurable.

    Caveat: extract_recommendations skips an ok RankTool whose `ranked` is
    empty and may fall back to an earlier RankTool or retrieval candidates,
    while this picks the strictly last ok RankTool. When the last ranker is
    empty but `recommended` is non-empty, downstream stage attribution for a
    non-surviving target is measured against the empty ranker rather than the
    step that actually produced the output. "survived" is unaffected (it is
    checked before any ranker evidence).
    """
    for s in reversed(steps):
        if s.get("tool") == "RankTool" and s.get("ok"):
            data = s.get("data")
            return data if isinstance(data, dict) else None
    return None


def _extract_stage_diagnostics(
    request: Any,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    id2item: Mapping[int, str] | None,
    corpus: ItemCorpus | None,
    itemcf_reachable: set[int] | None,
    itemcf_reachable_request: set[int] | None,
) -> dict[str, Any]:
    """Per-target, per-path retrieval funnel diagnostics (R3).

    For each ground-truth target and each retrieval path (sql / semantic /
    itemcf) walks S0 pool -> S1/S2 retrieval -> S3/S4 ranking -> S5 final
    inclusion and reports the stage where the target was lost, or "survived".
    None means unmeasurable (path not exercised, missing `data`, unmappable
    target), never a silent negative.

    Downstream of retrieval the pipeline is shared: RankTool's `ranked`,
    `unscored_item_ids`, `excluded_seen` and `candidate_item_ids` (echoed input)
    attribute ranking losses; `recommended` is S5. A target retrieved by one
    path but lost downstream is "lost" for that path even if another path also
    carried it — per-path detail preserves which path could have delivered it.
    """
    out: dict[str, Any] = {
        "retrieved_by_sql": None,
        "retrieved_by_semantic": None,
        "retrieved_by_itemcf": None,
        "target_reachable": None,
        "rank_in_pool": None,
        "target_rank_detail": None,
        "stage_lost": None,
        "target_stage_detail": None,
        "query_hit_any_title_token": None,
    }
    steps = trajectory.get("steps") or []
    targets = list(getattr(request, "targets", None) or [])
    if not steps or not targets or id2item is None or corpus is None:
        return out

    pool_detail = _target_pool_detail(targets, id2item, corpus, itemcf_reachable)

    exercised: dict[str, bool] = {}
    path_ids: dict[str, set[str] | None] = {}
    for path, tools in _PATH_TOOLS.items():
        exercised[path], path_ids[path] = _path_candidates(steps, tools)

    ranker = _last_ranker(steps)
    ranked_map: dict[str, int] = {}
    unscored: set[str] = set()
    excluded_seen: set[str] = set()
    ranker_input: list[str] | None = None
    if ranker is not None:
        for r in ranker.get("ranked") or []:
            if isinstance(r, dict) and isinstance(r.get("item_id"), str) and isinstance(r.get("rank"), int):
                ranked_map[r["item_id"]] = r["rank"]
        unscored = set(ranker.get("unscored_item_ids") or [])
        excluded_seen = set(ranker.get("excluded_seen") or [])
        raw_input = ranker.get("candidate_item_ids")
        ranker_input = list(raw_input) if isinstance(raw_input, list) else None

    recommended_ids = set(trajectory.get("recommended") or [])

    out["query_hit_any_title_token"] = _query_hit_title_verdict(
        targets, id2item, corpus, _search_query_tokens(steps)
    )

    def _downstream_stage(item_id: str) -> str | None:
        """Stage after a successful retrieval, or None when unmeasurable."""
        if item_id in recommended_ids:
            return "survived"
        if ranker is None:
            return None
        if item_id in ranked_map:
            return "final"
        if item_id in unscored:
            return "rank_unscored"
        if item_id in excluded_seen:
            return "rank_excluded_seen"
        if ranker_input is None:
            return None  # pre-candidate_item_ids trajectory: handoff vs top_k cut unknowable
        if item_id in ranker_input:
            return "rank_topk"  # scored but cut by RankTool top_k
        return "rank_input"  # never passed to the ranker

    stage_detail: dict[str, dict[str, Any]] = {}
    rank_detail: dict[str, int | None] = {}
    per_path_retrieved: dict[str, list[bool | None]] = {p: [] for p in _PATHS}
    any_retrieved = False
    best_stages: list[str] = []  # per-target best (furthest) stage, for the flat verdict

    for target_idx in targets:
        item_id = id2item.get(target_idx)
        t_key = str(target_idx)
        path_entries: dict[str, Any] = {}
        target_best: str | None = None
        target_best_order = -1
        for path in _PATHS:
            pool = pool_detail[t_key][path]
            retrieved: bool | None = None
            if item_id is not None and exercised[path]:
                retrieved = None if path_ids[path] is None else item_id in path_ids[path]
                per_path_retrieved[path].append(retrieved)
                if retrieved:
                    any_retrieved = True
            if path == "itemcf":
                seed_reachable = (
                    None if itemcf_reachable_request is None or item_id is None
                    else target_idx in itemcf_reachable_request
                )
            else:
                seed_reachable = None

            stage: str | None = None
            if item_id is not None and pool is not None:
                if pool is False:
                    stage = "pool"
                elif exercised[path] and path_ids[path] is not None:
                    if not retrieved:
                        stage = "retrieve"
                    else:
                        stage = _downstream_stage(item_id)
            entry: dict[str, Any] = {
                "pool": pool,
                "retrieved": retrieved,
                "seed_reachable": seed_reachable,
                "stage_lost": stage,
            }
            path_entries[path] = entry
            if stage is not None and _STAGE_ORDER[stage] > target_best_order:
                target_best, target_best_order = stage, _STAGE_ORDER[stage]

        rank_detail[t_key] = ranked_map.get(item_id) if item_id is not None else None
        stage_detail[t_key] = {"paths": path_entries, "best_stage": target_best}
        if target_best is not None:
            best_stages.append(target_best)

    # Flat per-path retrieved verdicts: existential, same convention as pool verdicts.
    for path in _PATHS:
        values = per_path_retrieved[path]
        if any(v is True for v in values):
            out[f"retrieved_by_{path}"] = True
        elif not values or any(v is None for v in values):
            out[f"retrieved_by_{path}"] = None
        else:
            out[f"retrieved_by_{path}"] = False

    # target_reachable: True if any target was retrieved by any exercised path;
    # False only when every exercised path measurably missed every target;
    # None when nothing measurable ran or any exercised path is unmeasurable.
    all_retrieved_values = [v for vals in per_path_retrieved.values() for v in vals]
    if any_retrieved:
        out["target_reachable"] = True
    elif all_retrieved_values and all(v is False for v in all_retrieved_values):
        out["target_reachable"] = False
    target_ranks = [r for r in rank_detail.values() if r is not None]
    out["rank_in_pool"] = min(target_ranks) if target_ranks else None

    out["target_rank_detail"] = rank_detail
    out["target_stage_detail"] = stage_detail
    if best_stages:
        unique = set(best_stages)
        out["stage_lost"] = unique.pop() if len(unique) == 1 else "mixed"
    return out
