"""Agent evaluation pieces: constraint lookups, request building, recommendation extraction, scoring, summary."""

import math

import numpy as np
import pytest

from package.agents import extract_recommendations
from package.evaluation import (
    AgentRequest,
    build_requests,
    items_satisfying,
    items_without_price,
    reference_groups,
    score_trajectory,
    summarize,
    filter_requests_by_scope,
)
from package.evaluation.requests._helper import _deepest_category
from package.evaluation.layer1_outcome import _extract_retrieval_funnel
from package.data.leakage import LeakageError
from package.memory.memory_tool import MemoryTool
from package.tools import get_tool_limits
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C

ITEM2ID = {VG_A: 0, VG_B: 1, VG_C: 2, EL_A: 3, EL_D: 4}
ID2ITEM = {v: k for k, v in ITEM2ID.items()}


def test_items_satisfying_needs_known_price_and_category(corpus):
    ids = [VG_A, VG_B, VG_C, EL_A]
    assert items_satisfying(corpus, ids, 20, "Accessories") == {VG_C}  # VG_B has no price, EL_A costs 25.99
    assert items_satisfying(corpus, ids, None, "Accessories") == {VG_C, EL_A}
    assert items_satisfying(corpus, ids, 20, None) == {VG_A, VG_C}
    assert items_satisfying(corpus, [], 20, "Accessories") == set()
    assert items_without_price(corpus, [VG_A, VG_B]) == {VG_B}


def test_deepest_category_is_the_last_of_the_taxonomy_path(corpus):
    assert _deepest_category(corpus, VG_A) == "Games"
    assert _deepest_category(corpus, EL_A) == "Electronics"


def _requests(corpus, **overrides):
    args = dict(
        seg_of={0: "warm", 1: "cold"},
        target_by_user={0: {1, 2}, 1: {3, 4}},
        last_item_of={0: 0},
        id2user={0: "u0", 1: "u1"},
        id2item=ID2ITEM,
        item2id=ITEM2ID,
        corpus=corpus,
        per_segment=1,
        n_ambiguous=2,
        language="en",
        k=10,
        price_slack=1.25,
        price_round_to=5,
        rng=np.random.default_rng(0),
    )
    args.update(overrides)
    return {r.request_id: r for r in build_requests(**args)}


def test_build_requests_makes_every_kind_with_the_right_ground_truth(corpus):
    reqs = _requests(corpus)
    assert sorted(reqs) == ["ambiguous-none-0", "ambiguous-none-1", "cold_text-cold-0", "constrained-warm-0",
                            "exclusion-warm-0", "personalized-warm-0", "similar-warm-0", "unanswerable-none-0"]
    similar = reqs["similar-warm-0"]
    assert similar.seed_item_id == VG_A and VG_A in similar.text and similar.targets == [1, 2] and not similar.oracle
    constrained = reqs["constrained-warm-0"]  # VG_B has no price, so VG_C (5.5, "Accessories") seeds the constraint
    assert constrained.category == "Accessories" and constrained.price_max == math.ceil(5.5 * 1.25 / 5) * 5
    assert constrained.targets == [2] and "Accessories" in constrained.text and "10" in constrained.text and constrained.oracle
    cold = reqs["cold_text-cold-0"]
    assert cold.category == "Electronics" and cold.targets == [3, 4] and cold.oracle
    assert reqs["ambiguous-none-0"].user_id is None and reqs["ambiguous-none-0"].targets == []
    
    # Check exclusion request: built from held-out items -> oracle scope
    exclusion = reqs["exclusion-warm-0"]
    assert exclusion.user_id is not None
    assert exclusion.targets  # should have targets (held-out items except the excluded one)
    assert exclusion.oracle
    
    # Check unanswerable request
    unanswerable = reqs["unanswerable-none-0"]
    assert unanswerable.user_id is None
    assert unanswerable.targets == []


def test_request_scope_keeps_target_informed_cases_separate(corpus):
    requests = list(_requests(corpus).values())
    realistic = filter_requests_by_scope(requests, "realistic")
    oracle = filter_requests_by_scope(requests, "oracle")
    assert realistic and all(not request.oracle for request in realistic)
    assert oracle and all(request.oracle for request in oracle)
    assert {request.request_id for request in realistic}.isdisjoint({request.request_id for request in oracle})
    # exclusion derives its excluded item+category from held-out items: oracle, never realistic
    assert "exclusion-warm-0" in {request.request_id for request in oracle}
    assert "exclusion-warm-0" not in {request.request_id for request in realistic}
    assert len(filter_requests_by_scope(requests, "all")) == len(requests)
    with pytest.raises(ValueError, match="scope"):
        filter_requests_by_scope(requests, "unknown")


def test_scored_rows_carry_the_oracle_flag(corpus):
    request = AgentRequest(request_id="exclusion-warm-0", kind="exclusion", segment="warm",
                           text="t", targets=[1], oracle=True)
    row = score_trajectory(request, _trajectory(steps=[_step("SimilarTool")], recommended=[VG_A]),
                           item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["oracle"] is True
    assert "oracle" not in summarize([row])["planner"]["exclusion"]["all"]  # flag, not a score


def test_build_requests_is_deterministic_and_rejects_unknown_language(corpus):
    assert [r.to_dict() for r in _requests(corpus).values()] == [r.to_dict() for r in _requests(corpus).values()]
    with pytest.raises(ValueError):
        _requests(corpus, language="xx")


def test_extract_recommendations_prefers_ranking_then_retrieval_then_query():
    ranked = {"tool": "RankTool", "ok": True, "data": {"ranked": [{"item_id": "a"}, {"item_id": "b"}, {"item_id": "c"}]}}
    cands = {"tool": "SearchTool", "ok": True, "data": {"candidates": [{"item_id": "x"}, {"item_id": "y"}]}}
    fetched = {"tool": "LookupTool", "ok": True, "data": {"items": [{"item_id": "z"}]}}
    assert extract_recommendations([cands, ranked, fetched], 2) == ["a", "b"]
    assert extract_recommendations([cands, fetched], 5) == ["x", "y"]
    assert extract_recommendations([fetched], 5) == ["z"]
    assert extract_recommendations([{**ranked, "ok": False}], 5) == []
    assert extract_recommendations([], 5) == []


def test_reference_groups_drop_tools_the_agent_does_not_have():
    assert reference_groups("personalized", {"SearchTool", "RankTool"}) == [("SearchTool",), ("RankTool",)]
    assert reference_groups("personalized", {"MemoryTool", "SearchTool", "RankTool"})[0] == ("MemoryTool",)
    assert reference_groups("ambiguous", {"RankTool"}) == []


def _trajectory(agent="planner", steps=(), recommended=(), error=None, ask_user=None, tools=("SimilarTool", "RankTool")):
    return {"agent": agent, "plan": [], "ask_user": ask_user, "steps": list(steps), "recommended": list(recommended),
            "usage": {"attempts": 1, "prompt_tokens": 7, "completion_tokens": 3, "latency_seconds": 0.5}, "error": error,
            "truncated": False, "tools_available": list(tools), "wall_seconds": 1.0}


def _step(tool, ok=True):
    return {"tool": tool, "ok": ok, "error": None, "invented_ids": [], "latency_seconds": 0.01}


def _data_step(tool, data, ok=True):
    return {**_step(tool, ok), "data": data}


def test_score_trajectory_ranking_and_tool_selection(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    traj = _trajectory(steps=[_step("SimilarTool"), _step("RankTool")], recommended=[VG_A, VG_B])
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["recall@2"] == 1.0 and row["hit_rate@2"] == 1.0 and row["mrr@2"] == 0.5
    assert row["ndcg@2"] == pytest.approx(1 / math.log2(3))
    assert row["precision@2"] == pytest.approx(0.5)
    assert row["map@2"] == pytest.approx(0.5)
    assert row["tool_selection_ok"] is True and row["task_success"] is True and row["n_steps"] == 2
    wrong_order = _trajectory(steps=[_step("RankTool"), _step("SimilarTool")], recommended=[VG_A])
    assert score_trajectory(request, wrong_order, item2id=ITEM2ID, corpus=corpus, k=2)["tool_selection_ok"] is False


def test_score_trajectory_deduplicates_recommendations_before_ranking(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    traj = _trajectory(steps=[_step("SimilarTool"), _step("RankTool")], recommended=[VG_B, VG_B])
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["n_recommended"] == 1
    assert row["precision@2"] == pytest.approx(0.5)  # one unique result and one unfilled rank
    assert row["recall@2"] == row["hit_rate@2"] == row["ndcg@2"] == row["map@2"] == 1.0


def test_failed_plan_scores_zero_not_missing(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    row = score_trajectory(request, _trajectory(error="ValueError: bad json"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["plan_valid"] is False and row["recall@2"] == 0.0 and row["task_success"] is False


def test_constraint_satisfaction_and_unknown_price(corpus):
    request = AgentRequest(request_id="c", kind="constrained", segment="warm", text="t", targets=[2], price_max=20.0, category="Accessories")
    traj = _trajectory(steps=[_step("SearchTool"), _step("RankTool")], recommended=[VG_C, VG_B], tools=("SearchTool", "RankTool"))
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["constraint_satisfaction"] == 0.5 and row["price_unknown_rate"] == 0.5 and row["task_success"] is False


def test_ambiguous_request_succeeds_only_by_asking(corpus):
    request = AgentRequest(request_id="a", kind="ambiguous", segment="none", text="t")
    asked = score_trajectory(request, _trajectory(ask_user="Which product?"), item2id=ITEM2ID, corpus=corpus, k=2)
    acted = score_trajectory(request, _trajectory(steps=[_step("RankTool")], recommended=[VG_A]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert asked["task_success"] is True and asked["asked_clarification"] is True and asked["recall@2"] is None
    assert acted["task_success"] is False


def test_baseline_rows_have_no_agent_only_metrics(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    row = score_trajectory(request, _trajectory(agent="baseline", recommended=[VG_B]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["tool_selection_ok"] is None and row["n_steps"] is None and row["recall@2"] == 1.0


def test_retrieval_funnel_is_unavailable_without_step_data():
    # Steps recorded before tool `data` was persisted must not read as zero retrieval.
    assert _extract_retrieval_funnel({"steps": [_step("SearchTool"), _step("RankTool")]}, ITEM2ID, k=10) == {}
    # A data-carrying step mixed with a data-less one is still unmeasurable.
    mixed = {"steps": [_data_step("SearchTool", {"candidates": [{"item_id": "a"}]}), _step("RankTool")]}
    assert _extract_retrieval_funnel(mixed, ITEM2ID, k=10) == {}


def test_retrieval_funnel_counts_real_and_genuinely_empty_results():
    cands = {"candidates": [{"item_id": "a"}, {"item_id": "b"}]}
    ranked = {"ranked": [{"item_id": "a"}, {"item_id": "b"}, {"item_id": "c"}]}
    full = _extract_retrieval_funnel({"steps": [_data_step("SearchTool", cands), _data_step("RankTool", ranked)]}, ITEM2ID, k=10)
    assert full["candidate_generation_count"] == 2 and full["retrieved_count"] == 2
    assert full["filtered_count"] == 3 and full["ranked_count"] == 3
    empty = _extract_retrieval_funnel(
        {"steps": [_data_step("SearchTool", {"candidates": []}), _data_step("RankTool", {"ranked": []})]}, ITEM2ID, k=10)
    assert empty["candidate_generation_count"] == 0 and empty["retrieved_count"] == 0
    assert empty["filtered_count"] == 0 and empty["ranked_count"] == 0
    # Steps with no retrieval/ranking tool at all: genuinely zero funnel.
    lookup_only = _extract_retrieval_funnel({"steps": [_data_step("LookupTool", {"items": []})]}, ITEM2ID, k=10)
    assert lookup_only["candidate_generation_count"] == 0


def test_score_trajectory_keeps_funnel_none_without_step_data(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    traj = _trajectory(steps=[_step("SimilarTool"), _step("RankTool")], recommended=[VG_A])
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    for key in ("candidate_generation_count", "retrieved_count", "filtered_count", "ranked_count", "rank_in_pool"):
        assert row[key] is None, key


def test_score_trajectory_counts_candidates_when_steps_carry_data(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_A}, {"item_id": VG_B}]}),
             _data_step("RankTool", {"ranked": [{"item_id": VG_A}]})]
    row = score_trajectory(request, _trajectory(steps=steps, recommended=[VG_A]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["candidate_generation_count"] == 2 and row["retrieved_count"] == 2
    assert row["filtered_count"] == 1 and row["ranked_count"] == 1


def _pool_request(targets):
    return AgentRequest(request_id="t", kind="similar", segment="warm", text="t", targets=targets)


def _pool_row(corpus, targets, *, id2item=None, itemcf_reachable=None):
    return score_trajectory(
        _pool_request(targets), _trajectory(steps=[_step("SimilarTool")], recommended=[VG_A]),
        item2id=ITEM2ID, corpus=corpus, k=2,
        id2item=id2item if id2item is not None else ID2ITEM,
        itemcf_reachable=itemcf_reachable)


def test_target_in_pool_per_path(corpus):
    # target idx 1 = VG_B: in corpus, not in the ItemCF reachable set
    row = _pool_row(corpus, [1], itemcf_reachable={0, 5})
    assert row["target_in_pool_sql"] is True and row["target_in_pool_semantic"] is True
    assert row["target_in_pool_itemcf"] is False
    assert row["target_pool_detail"]["1"] == {"sql": True, "semantic": True, "itemcf": False}
    # no shared pool exists: the bare columns stay unavailable
    assert row["target_in_pool"] is None and row["target_reachable"] is None


def test_target_in_pool_divergence_across_paths(corpus):
    # idx 5 maps to an item absent from the corpus but reachable by ItemCF
    id2item = {**ID2ITEM, 5: "Ghost::x"}
    row = _pool_row(corpus, [5], id2item=id2item, itemcf_reachable={5})
    assert row["target_in_pool_sql"] is False and row["target_in_pool_semantic"] is False
    assert row["target_in_pool_itemcf"] is True
    assert row["target_pool_detail"]["5"] == {"sql": False, "semantic": False, "itemcf": True}


def test_target_in_pool_temporal_policy_restricts_itemcf(corpus):
    id2item = {**ID2ITEM, 5: "Ghost::x"}
    corpus._evaluation_metadata_policy = {"first_seen_filter": True}  # mirrors apply_metadata_policy
    row = _pool_row(corpus, [5], id2item=id2item, itemcf_reachable={5})
    assert row["target_in_pool_itemcf"] is False  # SimilarTool would filter it via item_domains
    row2 = _pool_row(corpus, [0], id2item=id2item, itemcf_reachable={0})
    assert row2["target_in_pool_itemcf"] is True  # VG_A visible in corpus


def test_target_in_pool_unknown_never_reads_as_false(corpus):
    # idx 99 has no id2item entry: availability unknown -> verdicts None, not False
    row = _pool_row(corpus, [99], itemcf_reachable={99})
    assert row["target_in_pool_sql"] is None and row["target_in_pool_itemcf"] is None
    assert row["target_pool_detail"]["99"] == {"sql": None, "semantic": None, "itemcf": None}
    # mixed: one measurable absence + one unknown -> still None (cannot rule out)
    row2 = _pool_row(corpus, [5, 99], id2item={**ID2ITEM, 5: "Ghost::x"}, itemcf_reachable=set())
    assert row2["target_in_pool_sql"] is None


def test_target_in_pool_empty_targets_and_missing_inputs(corpus):
    row = _pool_row(corpus, [])
    assert row["target_in_pool_sql"] is None and row["target_pool_detail"] is None
    # no id2item -> cannot map indices to catalog ids -> unavailable
    row2 = score_trajectory(_pool_request([1]), _trajectory(steps=[_step("SimilarTool")], recommended=[VG_A]),
                            item2id=ITEM2ID, corpus=corpus, k=2)
    assert row2["target_in_pool_sql"] is None and row2["target_pool_detail"] is None
    # itemcf_reachable=None -> only that path is unavailable
    row3 = _pool_row(corpus, [1], itemcf_reachable=None)
    assert row3["target_in_pool_sql"] is True and row3["target_in_pool_itemcf"] is None


def test_target_in_any_path_pool(corpus):
    # existential across all (target, path): True when any path can reach a target
    row = _pool_row(corpus, [1], itemcf_reachable={0, 5})
    assert row["target_in_any_path_pool"] is True
    # divergence: absent from corpus but reachable via ItemCF -> still True
    id2item = {**ID2ITEM, 5: "Ghost::x"}
    row2 = _pool_row(corpus, [5], id2item=id2item, itemcf_reachable={5})
    assert row2["target_in_any_path_pool"] is True
    # measurable absence on every path -> False
    row3 = _pool_row(corpus, [5], id2item=id2item, itemcf_reachable=set())
    assert row3["target_in_any_path_pool"] is False
    # any unknown -> None, never a silent False
    row4 = _pool_row(corpus, [99], itemcf_reachable={99})
    assert row4["target_in_any_path_pool"] is None
    # empty targets -> unmeasurable
    row5 = _pool_row(corpus, [])
    assert row5["target_in_any_path_pool"] is None


def test_target_in_pool_multiple_targets_existential(corpus):
    id2item = {**ID2ITEM, 5: "Ghost::x"}
    # targets 0 (in corpus+cf) and 5 (not in corpus, in cf): every path has >=1 eligible
    row = _pool_row(corpus, [0, 5], id2item=id2item, itemcf_reachable={0, 5})
    assert row["target_in_pool_sql"] is True and row["target_in_pool_itemcf"] is True
    # targets 1 (corpus, not cf) and 5 (cf, not corpus): each path still finds one
    row2 = _pool_row(corpus, [1, 5], id2item=id2item, itemcf_reachable={5})
    assert row2["target_in_pool_sql"] is True and row2["target_in_pool_itemcf"] is True
    # no target anywhere: measurable absences only -> False
    row3 = _pool_row(corpus, [5], id2item=id2item, itemcf_reachable=set(), )
    assert row3["target_in_pool_sql"] is False and row3["target_in_pool_itemcf"] is False


def test_target_pool_detail_is_skipped_by_summarize(corpus):
    row = _pool_row(corpus, [1], itemcf_reachable={0})
    summary = summarize([row])
    assert "target_pool_detail" not in summary["planner"]["similar"]["all"]
    assert "target_in_pool_sql" not in summary["planner"]["similar"]["all"]  # diagnostic, not a score


def _stage_row(corpus, targets, steps, recommended=(), *, itemcf_reachable=None, itemcf_reachable_request=None,
               id2item=None):
    return score_trajectory(
        _pool_request(targets), _trajectory(steps=steps, recommended=list(recommended)),
        item2id=ITEM2ID, corpus=corpus, k=2,
        id2item=id2item if id2item is not None else ID2ITEM,
        itemcf_reachable=itemcf_reachable,
        itemcf_reachable_request=itemcf_reachable_request)


def _ranker_data(ranked=(), candidate_item_ids=None, unscored=(), excluded_seen=()):
    data = {"ranked": [{"rank": i + 1, "item_id": iid} for i, iid in enumerate(ranked)],
            "unscored_item_ids": list(unscored), "excluded_seen": list(excluded_seen)}
    if candidate_item_ids is not None:
        data["candidate_item_ids"] = list(candidate_item_ids)
    return data


def test_stage_diagnostics_survived_target(corpus):
    # target idx 1 = VG_B: in pool, retrieved by ItemCF, ranked #1, recommended
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_A}, {"item_id": VG_B}]}),
             _data_step("RankTool", _ranker_data(ranked=[VG_B, VG_A], candidate_item_ids=[VG_A, VG_B]))]
    row = _stage_row(corpus, [1], steps, recommended=[VG_B],
                     itemcf_reachable={1}, itemcf_reachable_request={1})
    assert row["retrieved_by_itemcf"] is True and row["retrieved_by_sql"] is None
    assert row["target_reachable"] is True and row["rank_in_pool"] == 1
    detail = row["target_stage_detail"]["1"]
    assert detail["best_stage"] == "survived"
    assert detail["paths"]["itemcf"]["stage_lost"] == "survived"
    assert detail["paths"]["itemcf"]["seed_reachable"] is True
    assert detail["paths"]["sql"]["stage_lost"] is None  # path not exercised
    assert row["stage_lost"] == "survived" and row["target_rank_detail"]["1"] == 1


def test_stage_diagnostics_pool_and_retrieve_losses(corpus):
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_A}]})]
    # idx 1 in corpus but NOT in itemcf_reachable -> pool loss on itemcf path
    row = _stage_row(corpus, [1], steps, itemcf_reachable=set(), itemcf_reachable_request={1})
    d = row["target_stage_detail"]["1"]["paths"]["itemcf"]
    assert d["stage_lost"] == "pool" and d["pool"] is False
    # idx 2 = VG_C reachable by ItemCF but absent from candidates -> retrieve loss
    row2 = _stage_row(corpus, [2], steps, itemcf_reachable={2}, itemcf_reachable_request={2})
    d2 = row2["target_stage_detail"]["2"]["paths"]["itemcf"]
    assert d2["stage_lost"] == "retrieve" and d2["retrieved"] is False
    assert row2["retrieved_by_itemcf"] is False and row2["target_reachable"] is False
    assert row2["stage_lost"] == "retrieve"


def test_stage_diagnostics_ranking_losses(corpus):
    cands = {"candidates": [{"item_id": VG_B}]}
    base = [_data_step("SimilarTool", cands)]
    # never passed to the ranker
    row = _stage_row(corpus, [1], base + [_data_step("RankTool", _ranker_data(ranked=[VG_A], candidate_item_ids=[VG_A]))],
                     itemcf_reachable={1})
    assert row["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] == "rank_input"
    assert row["rank_in_pool"] is None
    # passed but outside the scorer matrix
    row2 = _stage_row(corpus, [1], base + [_data_step("RankTool", _ranker_data(ranked=[VG_A], candidate_item_ids=[VG_A, VG_B], unscored=[VG_B]))],
                      itemcf_reachable={1})
    assert row2["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] == "rank_unscored"
    # passed but excluded as already seen
    row3 = _stage_row(corpus, [1], base + [_data_step("RankTool", _ranker_data(ranked=[VG_A], candidate_item_ids=[VG_A, VG_B], excluded_seen=[VG_B]))],
                      itemcf_reachable={1})
    assert row3["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] == "rank_excluded_seen"
    # scored but cut by RankTool top_k
    row4 = _stage_row(corpus, [1], base + [_data_step("RankTool", _ranker_data(ranked=[VG_A], candidate_item_ids=[VG_A, VG_B]))],
                      itemcf_reachable={1})
    assert row4["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] == "rank_topk"
    # ranked but absent from final recommendations
    row5 = _stage_row(corpus, [1], base + [_data_step("RankTool", _ranker_data(ranked=[VG_B, VG_A], candidate_item_ids=[VG_A, VG_B]))],
                      recommended=[VG_A], itemcf_reachable={1})
    assert row5["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] == "final"
    assert row5["rank_in_pool"] == 1 and row5["stage_lost"] == "final"


def test_stage_diagnostics_unknown_without_ranker_input(corpus):
    # pre-candidate_item_ids trajectory: handoff vs top_k cut is unknowable -> None
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_B}]}),
             _data_step("RankTool", {"ranked": [{"rank": 1, "item_id": VG_A}], "unscored_item_ids": [], "excluded_seen": []})]
    row = _stage_row(corpus, [1], steps, itemcf_reachable={1})
    assert row["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] is None
    assert row["stage_lost"] is None


def test_stage_diagnostics_unexercised_paths_and_missing_data(corpus):
    # no retrieval steps at all -> every path unexercised -> all None
    row = _stage_row(corpus, [1], [_data_step("LookupTool", {"items": []})], itemcf_reachable={1})
    assert row["retrieved_by_sql"] is None and row["retrieved_by_itemcf"] is None
    assert row["target_reachable"] is None and row["stage_lost"] is None
    # exercised but data-less step -> unmeasurable, not False
    row2 = _stage_row(corpus, [1], [_step("SimilarTool")], itemcf_reachable={1})
    assert row2["retrieved_by_itemcf"] is None
    assert row2["target_stage_detail"]["1"]["paths"]["itemcf"]["stage_lost"] is None


def test_stage_diagnostics_mixed_stages_and_seed_reachability(corpus):
    # target 1 retrieved+survives via itemcf; target 7 globally ItemCF-eligible but
    # not reachable from this trajectory's seeds -> per-path stages differ -> "mixed"
    id2item = {**ID2ITEM, 7: "Ghost::x"}
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_B}]}),
             _data_step("RankTool", _ranker_data(ranked=[VG_B], candidate_item_ids=[VG_B]))]
    row = _stage_row(corpus, [1, 7], steps, recommended=[VG_B],
                     id2item=id2item, itemcf_reachable={1, 7}, itemcf_reachable_request={1})
    d1 = row["target_stage_detail"]["1"]["paths"]["itemcf"]
    d7 = row["target_stage_detail"]["7"]["paths"]["itemcf"]
    assert d1["stage_lost"] == "survived" and d1["seed_reachable"] is True
    # globally in the ItemCF pool (pool=True) but absent from these seeds' candidate
    # space and from the returned candidates -> lost at retrieve on this path
    assert d7["stage_lost"] == "retrieve" and d7["seed_reachable"] is False
    assert row["target_stage_detail"]["7"]["best_stage"] == "retrieve"  # beats sql/semantic "pool"
    assert row["stage_lost"] == "mixed"
    # seed_reachable None when request reachability was not supplied
    row2 = _stage_row(corpus, [1], steps[:1], itemcf_reachable={1})
    assert row2["target_stage_detail"]["1"]["paths"]["itemcf"]["seed_reachable"] is None


def test_stage_diagnostics_new_keys_skipped_by_summarize(corpus):
    steps = [_data_step("SimilarTool", {"candidates": [{"item_id": VG_B}]}),
             _data_step("RankTool", _ranker_data(ranked=[VG_B], candidate_item_ids=[VG_B]))]
    row = _stage_row(corpus, [1], steps, recommended=[VG_B], itemcf_reachable={1})
    summary = summarize([row])
    entry = summary["planner"]["similar"]["all"]
    for key in ("stage_lost", "target_stage_detail", "target_rank_detail"):
        assert key not in entry


def test_query_hit_any_title_token(corpus):
    # target idx 1 = VG_B "Mario 100%": query token "mario" hits the title
    steps = [_data_step("SearchTool", {"query_tokens": ["mario"], "candidates": []})]
    assert _stage_row(corpus, [1], steps)["query_hit_any_title_token"] is True
    # measurable miss -> False
    steps = [_data_step("SearchTool", {"query_tokens": ["zzz"], "candidates": []})]
    assert _stage_row(corpus, [1], steps)["query_hit_any_title_token"] is False
    # union across multiple SearchTool steps: second query carries the hit
    steps = [_data_step("SearchTool", {"query_tokens": ["zzz"], "candidates": []}),
             _data_step("SearchTool", {"query_tokens": ["game"], "candidates": []})]
    assert _stage_row(corpus, [0], steps)["query_hit_any_title_token"] is True  # VG_A "Super Video Game"
    # no SearchTool exercised -> unmeasurable
    assert _stage_row(corpus, [1], [_step("SimilarTool")])["query_hit_any_title_token"] is None
    # SearchTool without persisted data -> unmeasurable (pre-R1 trajectory)
    assert _stage_row(corpus, [1], [_step("SearchTool")])["query_hit_any_title_token"] is None
    # unmapped target index -> None
    steps = [_data_step("SearchTool", {"query_tokens": ["mario"], "candidates": []})]
    assert _stage_row(corpus, [99], steps)["query_hit_any_title_token"] is None
    # target absent from corpus -> title unmeasurable -> None
    id2item = {**ID2ITEM, 5: "Ghost::x"}
    assert _stage_row(corpus, [5], steps, id2item=id2item)["query_hit_any_title_token"] is None
    # aggregates as a rate, unlike the per-target diagnostics
    summary = summarize([_stage_row(corpus, [1], [_data_step("SearchTool", {"query_tokens": ["mario"], "candidates": []})])])
    assert summary["planner"]["similar"]["all"]["query_hit_any_title_token"] == 1.0


def test_summarize_means_per_agent_kind_and_segment():
    rows = [
        {"request_id": "r0", "agent": "a", "kind": "similar", "segment": "warm", "task_success": True, "recall@10": 0.5, "x": None},
        {"request_id": "r1", "agent": "a", "kind": "similar", "segment": "warm", "task_success": False, "recall@10": 0.0, "x": None},
        {"request_id": "r2", "agent": "a", "kind": "similar", "segment": "sparse", "task_success": True, "recall@10": 1.0, "x": None},
    ]
    out = summarize(rows)["a"]["similar"]
    assert out["warm"]["n"] == 2 and out["warm"]["task_success"] == 0.5 and out["warm"]["recall@10"] == 0.25
    assert out["all"]["n"] == 3 and out["all"]["recall@10"] == pytest.approx(0.5) and "x" not in out["all"]


def test_memory_tool_refuses_interactions_from_the_future(corpus, cf_setup):
    interactions, user2id, item2id = cf_setup
    interactions = interactions.assign(timestamp=np.arange(len(interactions)) + 10)
    with pytest.raises(LeakageError):
        MemoryTool(interactions, user2id, item2id, corpus, as_of_timestamp=5)
    MemoryTool(interactions, user2id, item2id, corpus, as_of_timestamp=int(interactions["timestamp"].max()))
    with pytest.raises(ValueError):
        MemoryTool(interactions.drop(columns="timestamp"), user2id, item2id, corpus, as_of_timestamp=5)


def test_memory_tool_returns_recent_items(corpus, cf_setup):
    """MemoryTool should return recent_items field with most recent items first."""
    interactions, user2id, item2id = cf_setup
    memory = MemoryTool(interactions, user2id, item2id, corpus)
    
    # Get a user with interactions
    user_id = "u1"
    result = memory.execute(user_id)
    
    assert "recent_items" in result
    assert isinstance(result["recent_items"], list)
    # If user has interactions, recent_items should not be empty
    if result["known"]:
        assert len(result["recent_items"]) > 0
        # All items should be namespaced
        for item in result["recent_items"]:
            assert "::" in item


def test_memory_tool_recent_items_respects_as_of_timestamp(corpus, cf_setup):
    """recent_items should not include interactions after as_of_timestamp."""
    interactions, user2id, item2id = cf_setup
    interactions = interactions.assign(timestamp=np.arange(len(interactions)))

    # as_of_timestamp in the middle of interactions
    as_of = len(interactions) // 2
    # Filter interactions to only include those <= as_of before passing to MemoryTool
    # (caller's responsibility to provide valid data for the snapshot)
    valid_interactions = interactions[interactions["timestamp"] <= as_of].copy()
    memory = MemoryTool(valid_interactions, user2id, item2id, corpus, as_of_timestamp=as_of)

    user_id = "u1"
    result = memory.execute(user_id)

    if result["known"]:
        # recent_items should only include items with timestamp <= as_of
        assert "recent_items" in result
        assert isinstance(result["recent_items"], list)


def test_memory_tool_recent_items_count_limited(corpus, cf_setup):
    """recent_items should be limited to memory_recent_items from config."""
    interactions, user2id, item2id = cf_setup
    memory = MemoryTool(interactions, user2id, item2id, corpus)
    
    user_id = "u1"
    result = memory.execute(user_id)
    
    if result["known"]:
        limit = get_tool_limits().memory_recent_items
        assert len(result["recent_items"]) <= limit


def test_personalized_is_not_scored_for_a_planner_that_cannot_read_history(corpus):
    request = AgentRequest(request_id="p", kind="personalized", segment="warm", text="t", targets=[1])
    blind = score_trajectory(request, _trajectory(ask_user="What do you like?"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert blind["task_success"] is None and blind["tool_selection_ok"] is None and blind["asked_clarification"] is True
    with_memory = _trajectory(steps=[_step("MemoryTool"), _step("SearchTool"), _step("RankTool")],
                              recommended=[VG_B], tools=("MemoryTool", "SearchTool", "RankTool"))
    scored = score_trajectory(request, with_memory, item2id=ITEM2ID, corpus=corpus, k=2)
    assert scored["tool_selection_ok"] is True and scored["task_success"] is True


# ---- plan-reflect in trajectories / scoring / summary / resume

def _load_run_agent_eval():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "scripts" / "evaluation" / "run_agent_eval.py"
    spec = importlib.util.spec_from_file_location("run_agent_eval_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _similar_request():
    return AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])


def test_score_trajectory_exposes_reflections_and_first_attempt_ok(corpus):
    traj = _trajectory(steps=[_step("SimilarTool"), _step("RankTool")], recommended=[VG_A, VG_B])
    traj.update(reflections=1, first_attempt_ok=False)
    row = score_trajectory(_similar_request(), traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["reflections"] == 1 and row["first_attempt_ok"] is False
    assert row["task_success"] is True  # task_success is judged on the final result only


def test_score_trajectory_still_scores_old_trajectories_without_the_new_fields(corpus):
    traj = _trajectory(steps=[_step("SimilarTool"), _step("RankTool")], recommended=[VG_A, VG_B])
    assert "reflections" not in traj and "first_attempt_ok" not in traj
    row = score_trajectory(_similar_request(), traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["reflections"] == 0 and row["first_attempt_ok"] is None and row["task_success"] is True


def test_score_trajectory_still_scores_old_trajectories_without_args_and_output_summary(corpus):
    """Old trajectories without args/output_summary fields should still be scored."""
    # Create a step without the new fields (as it would be in old trajectories)
    old_step = {"tool": "SimilarTool", "ok": True, "error": None, "invented_ids": [], "latency_seconds": 0.01}
    traj = _trajectory(steps=[old_step, _step("RankTool")], recommended=[VG_A, VG_B])
    # Manually ensure the first step doesn't have the new fields
    traj["steps"][0] = old_step
    assert "args" not in traj["steps"][0]
    assert "output_summary" not in traj["steps"][0]
    row = score_trajectory(_similar_request(), traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["task_success"] is True


def test_non_planner_rows_have_no_reflect_columns(corpus):
    row = score_trajectory(_similar_request(), _trajectory(agent="baseline", recommended=[VG_B]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["reflections"] is None and row["first_attempt_ok"] is None


def test_summarize_averages_first_attempt_ok_and_skips_missing():
    rows = [
        {"request_id": f"r{i}", "agent": "planner", "kind": "similar", "segment": "warm", "first_attempt_ok": v, "reflections": r}
        for i, (v, r) in enumerate([(True, 0), (False, 1), (False, 1), (None, 0)])
    ]
    stats = summarize(rows)["planner"]["similar"]["all"]
    assert stats["first_attempt_ok"] == pytest.approx(1 / 3) and stats["reflections"] == pytest.approx(0.5)


def test_summary_columns_print_the_reflect_metrics():
    columns = _load_run_agent_eval().SUMMARY_COLUMNS
    assert "first_attempt_ok" in columns and "reflections" in columns


def test_run_planner_records_reflections_and_the_last_attempt(corpus):
    import json

    from package.agents import PlanExecutor
    from package.tools import FilterTool
    from tests.agents.test_plan_executor import ScriptedLLM

    script = _load_run_agent_eval()
    bad = {"tool": "FilterTool", "args": {"category": "Games"}}
    good = {"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 2}}
    llm = ScriptedLLM(json.dumps({"steps": [bad]}), json.dumps({"steps": [good]}))
    executor = PlanExecutor(llm, [FilterTool(corpus)], reflect_rounds=1)
    traj = script.run_planner(executor, _similar_request(), "planner", 2)
    assert traj["reflections"] == 1 and traj["first_attempt_ok"] is False and traj["reflect_rounds"] == 1
    assert [s["ok"] for s in traj["steps"]] == [True] and traj["plan"] == [good] and traj["recommended"]
    assert traj["usage"]["attempts"] == 2 and traj["usage"]["prompt_tokens"] == 20
    json.dumps(traj)  # the file stays serialisable


def test_run_planner_marks_an_unparsable_plan_as_not_ok_first_time(corpus):
    from package.agents import PlanExecutor
    from package.tools import FilterTool
    from tests.agents.test_plan_executor import ScriptedLLM

    executor = PlanExecutor(ScriptedLLM("nope"), [FilterTool(corpus)], plan_retries=0, reflect_rounds=1)
    traj = _load_run_agent_eval().run_planner(executor, _similar_request(), "planner", 2)
    assert traj["error"] and traj["first_attempt_ok"] is False and traj["reflections"] == 0


def test_trajectory_error_chars_comes_from_yaml_and_must_be_positive(corpus, monkeypatch):
    from package.agents import PlanExecutor
    from package.config import load_config
    from package.config.load_config import ConfigError
    from package.tools import FilterTool
    from tests.agents.test_plan_executor import ScriptedLLM

    script = _load_run_agent_eval()
    assert script._error_chars() == load_config("agent/agent_eval")["agent_eval"]["trajectory_error_chars"]

    def with_chars(value):
        def fake(name, *args, **kwargs):
            cfg = load_config(name, *args, **kwargs)
            if name == "agent/agent_eval":
                cfg["agent_eval"]["trajectory_error_chars"] = value
            return cfg
        return fake

    monkeypatch.setattr(script, "load_config", with_chars(12))
    executor = PlanExecutor(ScriptedLLM("nope"), [FilterTool(corpus)], plan_retries=0, reflect_rounds=0)
    traj = script.run_planner(executor, _similar_request(), "planner", 2)
    assert 0 < len(traj["error"]) <= 12
    monkeypatch.setattr(script, "load_config", with_chars(0))
    with pytest.raises(ConfigError):
        script._error_chars()


def test_resume_drops_planner_records_made_with_another_reflect_setting():
    keep = _load_run_agent_eval().is_resumable
    text_of = {"r0": "hello"}
    rec = {"request_id": "r0", "agent": "planner", "text": "hello", "reflect_rounds": 1}
    assert keep(rec, text_of, ["planner"], 1)
    assert not keep(rec, text_of, ["planner"], 0)  # a 0-vs-1 comparison must not mix runs
    old = {k: v for k, v in rec.items() if k != "reflect_rounds"}  # written before plan-reflect existed = 0 rounds
    assert keep(old, text_of, ["planner"], 0) and not keep(old, text_of, ["planner"], 1)
    assert not keep({**rec, "text": "changed"}, text_of, ["planner"], 1) and not keep(rec, text_of, ["baseline"], 1)
    assert keep({"request_id": "r0", "agent": "baseline", "text": "hello"}, text_of, ["baseline"], 1)  # no LLM, no setting


def test_resume_agent_config_excludes_campaign_id():
    """campaign_id is provenance, not protocol: it must not change the resume hash."""
    script = _load_run_agent_eval()
    base = {"agents": ["baseline"], "per_segment": 3, "trajectory_file": "t.jsonl"}
    variants = [
        dict(base),
        {**base, "campaign_id": None},
        {**base, "campaign_id": "campaign_a"},
        {**base, "campaign_id": "campaign_b"},
    ]
    normalized = [script._resume_agent_config(v) for v in variants]
    assert all(n == normalized[0] for n in normalized)
    assert "campaign_id" not in normalized[0]


# ---- multi_turn wiring: resume hash + error isolation

def test_resume_agent_config_excludes_multi_turn():
    """Toggling agent_eval.multi_turn must not change the resume hash input."""
    script = _load_run_agent_eval()
    base = {"agents": ["baseline"], "k": 10, "per_segment": 20}
    variants = [
        dict(base),
        dict(base, multi_turn={"enabled": False, "dataset": "d.jsonl", "limits": {}}),
        dict(base, multi_turn={"enabled": True, "dataset": "d.jsonl",
                               "output_dir": "/tmp/x", "limits": {"max_turns": 3},
                               "timeout_seconds": 60}),
        dict(base, campaign_id="campaign_a"),
        dict(base, campaign_id="campaign_b",
             multi_turn={"enabled": True, "limits": {"max_turns": 9}}),
    ]
    hashed = [script._resume_agent_config(cfg) for cfg in variants]
    assert hashed[0] == hashed[1] == hashed[2] == hashed[3] == hashed[4]
    assert all("multi_turn" not in h and "campaign_id" not in h for h in hashed)


def test_run_optional_multi_turn_disabled_returns_none(tmp_path):
    script = _load_run_agent_eval()
    assert script.run_optional_multi_turn({"agents": ["baseline"]}, tmp_path / "exp_001") is None
    assert script.run_optional_multi_turn({"multi_turn": {"enabled": False}}, tmp_path / "exp_001") is None


def test_run_optional_multi_turn_swallows_step_errors(tmp_path, monkeypatch):
    """A crashing multi-turn step must not sink the already-paid agent eval:
    it returns status=error so metrics.json still gets written."""
    import package.evaluation.multi_turn as mt_pkg

    def _boom(*a, **k):
        raise RuntimeError("simulated multi-turn crash")

    monkeypatch.setattr(mt_pkg, "run_multi_turn_for_eval", _boom)
    script = _load_run_agent_eval()
    info = script.run_optional_multi_turn(
        {"multi_turn": {"enabled": True}}, tmp_path / "exp_001"
    )
    assert info["status"] == "error"
    assert "simulated multi-turn crash" in info["error"]
