"""Agent evaluation pieces: constraint lookups, request building, recommendation extraction, scoring, summary."""

import math

import numpy as np
import pytest

from package.agents.evaluation import (
    AgentRequest,
    build_requests,
    extract_recommendations,
    items_satisfying,
    items_without_price,
    reference_groups,
    score_trajectory,
    summarize,
)
from package.agents.evaluation._helper import _deepest_category
from package.data.leakage import LeakageError
from package.memory.memory_tool import MemoryTool
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
                            "personalized-warm-0", "similar-warm-0"]
    similar = reqs["similar-warm-0"]
    assert similar.seed_item_id == VG_A and VG_A in similar.text and similar.targets == [1, 2] and not similar.oracle
    constrained = reqs["constrained-warm-0"]  # VG_B has no price, so VG_C (5.5, "Accessories") seeds the constraint
    assert constrained.category == "Accessories" and constrained.price_max == math.ceil(5.5 * 1.25 / 5) * 5
    assert constrained.targets == [2] and "Accessories" in constrained.text and "10" in constrained.text and constrained.oracle
    cold = reqs["cold_text-cold-0"]
    assert cold.category == "Electronics" and cold.targets == [3, 4] and cold.oracle
    assert reqs["ambiguous-none-0"].user_id is None and reqs["ambiguous-none-0"].targets == []


def test_build_requests_is_deterministic_and_rejects_unknown_language(corpus):
    assert [r.to_dict() for r in _requests(corpus).values()] == [r.to_dict() for r in _requests(corpus).values()]
    with pytest.raises(ValueError):
        _requests(corpus, language="xx")


def test_extract_recommendations_prefers_ranking_then_retrieval_then_query():
    ranked = {"tool": "RecoModelTool", "ok": True, "data": {"ranked": [{"item_id": "a"}, {"item_id": "b"}, {"item_id": "c"}]}}
    cands = {"tool": "SemanticSearchTool", "ok": True, "data": {"candidates": [{"item_id": "x"}, {"item_id": "y"}]}}
    fetched = {"tool": "QueryTool", "ok": True, "data": {"items": [{"item_id": "z"}]}}
    assert extract_recommendations([cands, ranked, fetched], 2) == ["a", "b"]
    assert extract_recommendations([cands, fetched], 5) == ["x", "y"]
    assert extract_recommendations([fetched], 5) == ["z"]
    assert extract_recommendations([{**ranked, "ok": False}], 5) == []
    assert extract_recommendations([], 5) == []


def test_reference_groups_drop_tools_the_agent_does_not_have():
    assert reference_groups("personalized", {"SemanticSearchTool", "RecoModelTool"}) == [("SemanticSearchTool",), ("RecoModelTool",)]
    assert reference_groups("personalized", {"MemoryTool", "SemanticSearchTool", "RecoModelTool"})[0] == ("MemoryTool",)
    assert reference_groups("ambiguous", {"RecoModelTool"}) == []


def _trajectory(agent="planner", steps=(), recommended=(), error=None, ask_user=None, tools=("ItemCFTool", "RecoModelTool")):
    return {"agent": agent, "plan": [], "ask_user": ask_user, "steps": list(steps), "recommended": list(recommended),
            "usage": {"attempts": 1, "prompt_tokens": 7, "completion_tokens": 3, "latency_seconds": 0.5}, "error": error,
            "truncated": False, "tools_available": list(tools), "wall_seconds": 1.0}


def _step(tool, ok=True):
    return {"tool": tool, "ok": ok, "error": None, "invented_ids": [], "latency_seconds": 0.01}


def test_score_trajectory_ranking_and_tool_selection(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    traj = _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A, VG_B])
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["recall@2"] == 1.0 and row["hit_rate@2"] == 1.0 and row["mrr@2"] == 0.5
    assert row["ndcg@2"] == pytest.approx(1 / math.log2(3))
    assert row["tool_selection_ok"] is True and row["task_success"] is True and row["n_steps"] == 2
    wrong_order = _trajectory(steps=[_step("RecoModelTool"), _step("ItemCFTool")], recommended=[VG_A])
    assert score_trajectory(request, wrong_order, item2id=ITEM2ID, corpus=corpus, k=2)["tool_selection_ok"] is False


def test_failed_plan_scores_zero_not_missing(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    row = score_trajectory(request, _trajectory(error="ValueError: bad json"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["plan_valid"] is False and row["recall@2"] == 0.0 and row["task_success"] is False


def test_constraint_satisfaction_and_unknown_price(corpus):
    request = AgentRequest(request_id="c", kind="constrained", segment="warm", text="t", targets=[2], price_max=20.0, category="Accessories")
    traj = _trajectory(steps=[_step("SemanticSearchTool"), _step("RecoModelTool")], recommended=[VG_C, VG_B], tools=("SemanticSearchTool", "RecoModelTool"))
    row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["constraint_satisfaction"] == 0.5 and row["price_unknown_rate"] == 0.5 and row["task_success"] is False


def test_ambiguous_request_succeeds_only_by_asking(corpus):
    request = AgentRequest(request_id="a", kind="ambiguous", segment="none", text="t")
    asked = score_trajectory(request, _trajectory(ask_user="Which product?"), item2id=ITEM2ID, corpus=corpus, k=2)
    acted = score_trajectory(request, _trajectory(steps=[_step("RecoModelTool")], recommended=[VG_A]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert asked["task_success"] is True and asked["asked_clarification"] is True and asked["recall@2"] is None
    assert acted["task_success"] is False


def test_baseline_rows_have_no_agent_only_metrics(corpus):
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])
    row = score_trajectory(request, _trajectory(agent="baseline", recommended=[VG_B]), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["tool_selection_ok"] is None and row["n_steps"] is None and row["recall@2"] == 1.0


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


def test_personalized_is_not_scored_for_a_planner_that_cannot_read_history(corpus):
    request = AgentRequest(request_id="p", kind="personalized", segment="warm", text="t", targets=[1])
    blind = score_trajectory(request, _trajectory(ask_user="What do you like?"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert blind["task_success"] is None and blind["tool_selection_ok"] is None and blind["asked_clarification"] is True
    with_memory = _trajectory(steps=[_step("MemoryTool"), _step("SemanticSearchTool"), _step("RecoModelTool")],
                              recommended=[VG_B], tools=("MemoryTool", "SemanticSearchTool", "RecoModelTool"))
    scored = score_trajectory(request, with_memory, item2id=ITEM2ID, corpus=corpus, k=2)
    assert scored["tool_selection_ok"] is True and scored["task_success"] is True


# ---- plan-reflect in trajectories / scoring / summary / resume

def _load_run_agent_eval():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluation" / "run_agent_eval.py"
    spec = importlib.util.spec_from_file_location("run_agent_eval_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _similar_request():
    return AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="t", targets=[1])


def test_score_trajectory_exposes_reflections_and_first_attempt_ok(corpus):
    traj = _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A, VG_B])
    traj.update(reflections=1, first_attempt_ok=False)
    row = score_trajectory(_similar_request(), traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["reflections"] == 1 and row["first_attempt_ok"] is False
    assert row["task_success"] is True  # task_success is judged on the final result only


def test_score_trajectory_still_scores_old_trajectories_without_the_new_fields(corpus):
    traj = _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A, VG_B])
    assert "reflections" not in traj and "first_attempt_ok" not in traj
    row = score_trajectory(_similar_request(), traj, item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["reflections"] == 0 and row["first_attempt_ok"] is None and row["task_success"] is True


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
    from package.tools import SQLTool
    from tests.agents.test_plan_executor import ScriptedLLM

    script = _load_run_agent_eval()
    bad = {"tool": "SQLTool", "args": {"category": "Games"}}
    good = {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 2}}
    llm = ScriptedLLM(json.dumps({"steps": [bad]}), json.dumps({"steps": [good]}))
    executor = PlanExecutor(llm, [SQLTool(corpus)], reflect_rounds=1)
    traj = script.run_planner(executor, _similar_request(), "planner", 2)
    assert traj["reflections"] == 1 and traj["first_attempt_ok"] is False and traj["reflect_rounds"] == 1
    assert [s["ok"] for s in traj["steps"]] == [True] and traj["plan"] == [good] and traj["recommended"]
    assert traj["usage"]["attempts"] == 2 and traj["usage"]["prompt_tokens"] == 20
    json.dumps(traj)  # the file stays serialisable


def test_run_planner_marks_an_unparsable_plan_as_not_ok_first_time(corpus):
    from package.agents import PlanExecutor
    from package.tools import SQLTool
    from tests.agents.test_plan_executor import ScriptedLLM

    executor = PlanExecutor(ScriptedLLM("nope"), [SQLTool(corpus)], plan_retries=0, reflect_rounds=1)
    traj = _load_run_agent_eval().run_planner(executor, _similar_request(), "planner", 2)
    assert traj["error"] and traj["first_attempt_ok"] is False and traj["reflections"] == 0


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
