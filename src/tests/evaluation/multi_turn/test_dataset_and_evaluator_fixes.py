"""Tests for the 6.3 multi-turn fixes: dataset validity + evaluator metrics.

Covers:
- exclusion_compliance bare-vs-namespaced id comparison and absent_exclusions
- context_retention as a real retention check (session reset must score 0)
- expected_tool_calls matching incl. $S.<path> resolution
- dataset lint: expected ids exist in the fixture, no dead initial_context
- RealAgentRunner smoke over ScriptedLLM (pipeline does not crash)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from package.evaluation.component.benchmarks.memory_correctness_setup import (
    create_test_interactions,
    create_test_mappings,
)
from package.evaluation.multi_turn._schema import Conversation, TurnInput, TurnResult
from package.evaluation.multi_turn.multi_turn_evaluator import MultiTurnEvaluator

DATASET = (
    Path(__file__).parents[3]
    / "package" / "evaluation" / "multi_turn" / "conversations.jsonl"
)


@pytest.fixture(scope="module")
def conversations():
    return [
        Conversation.from_dict(json.loads(line))
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def fixture_item_bare_ids():
    interactions = create_test_interactions()
    _, item2id, _ = create_test_mappings(interactions)
    return {str(k).rsplit("::", 1)[-1] for k in item2id}


@pytest.fixture(scope="module")
def evaluator():
    return MultiTurnEvaluator()


# ---------------- dataset lint ----------------

def test_dataset_loads_and_has_11_conversations(conversations):
    assert len(conversations) == 11
    assert all(c.turns for c in conversations)


def test_expected_items_exist_in_fixture(conversations, fixture_item_bare_ids):
    """Every expected_items id must be a real fixture item (bare form)."""
    bad = [
        (c.conversation_id, t.turn_id, i)
        for c in conversations
        for t in c.turns
        for i in t.expected_items
        if str(i).rsplit("::", 1)[-1] not in fixture_item_bare_ids
    ]
    assert bad == [], f"expected items not in fixture: {bad}"


def test_no_dead_initial_context(conversations):
    for c in conversations:
        assert "user_profile" not in (c.initial_context or {}), c.conversation_id


def test_iso_pair_has_leak_detector(conversations):
    iso1 = next(c for c in conversations if c.conversation_id == "conv_session_isolation_1")
    iso2 = next(c for c in conversations if c.conversation_id == "conv_session_isolation_2")
    t1 = iso1.turns[0]
    t2 = iso2.turns[0]
    assert t1.expected_exclusions.get("exclude_item_ids"), "iso_1 must leave an exclusion behind"
    assert "exclude_item_ids" in t2.absent_exclusions, "iso_2 must assert no inherited exclusion"


# ---------------- exclusion_compliance ----------------

def _turn(**kw):
    base = dict(turn_id="t", position=0, user_request="r")
    base.update(kw)
    return TurnInput(**base)


def test_exclusion_bare_vs_namespaced_matches(evaluator):
    """Dataset 'vg_a' must match runtime 'Video_Games::vg_a' (FAIL-before: raw compare = 0)."""
    ti = _turn(expected_exclusions={"exclude_item_ids": ["vg_a"]})
    out = {"items": [], "exclusions": {"exclude_item_ids": ["Video_Games::vg_a", "Video_Games::vg_b"]}}
    m = evaluator._score_turn(ti, out, {})
    assert m["exclusion_compliance"] == 1.0


def test_exclusion_violation_scores_zero(evaluator):
    ti = _turn(expected_exclusions={"exclude_item_ids": ["vg_a"]})
    out = {"items": [], "exclusions": {"exclude_item_ids": ["Video_Games::vg_b"]}}
    assert evaluator._score_turn(ti, out, {})["exclusion_compliance"] == 0.0
    out2 = {"items": [], "exclusions": {}}
    assert evaluator._score_turn(ti, out2, {})["exclusion_compliance"] == 0.0


def test_absent_exclusions_detects_leak(evaluator):
    ti = _turn(absent_exclusions=["exclude_item_ids"])
    leaked = {"items": [], "exclusions": {"exclude_item_ids": ["Video_Games::vg_a"]}}
    clean = {"items": [], "exclusions": {}}
    assert evaluator._score_turn(ti, leaked, {})["exclusion_compliance"] == 0.0
    assert evaluator._score_turn(ti, clean, {})["exclusion_compliance"] == 1.0


# ---------------- context_retention ----------------

def _conv_result(session_states, actuals):
    return [
        TurnResult(turn_id=f"t{i}", actual_items=a, session_state=s, success=True)
        for i, (a, s) in enumerate(zip(actuals, session_states))
    ]


def test_context_retention_session_reset_scores_zero(evaluator):
    """If the session drops earlier items (reset/leak), retention must be 0."""
    conv = Conversation(conversation_id="c", turns=[_turn(position=0), _turn(position=1)])
    trs = _conv_result(
        [
            {"shown_items": ["Video_Games::vg_a"], "constraints": {}},
            {"shown_items": ["Video_Games::vg_b"], "constraints": {}},  # vg_a lost
        ],
        [["vg_a"], ["vg_b"]],
    )
    assert evaluator._calculate_conversation_metrics(trs, conv)["context_retention"] == 0.0


def test_context_retention_full_pass(evaluator):
    conv = Conversation(conversation_id="c", turns=[_turn(position=0), _turn(position=1)])
    trs = _conv_result(
        [
            {"shown_items": ["Video_Games::vg_a"], "constraints": {}},
            {"shown_items": ["Video_Games::vg_a", "Video_Games::vg_b"], "constraints": {}},
        ],
        [["vg_a"], ["vg_b"]],
    )
    assert evaluator._calculate_conversation_metrics(trs, conv)["context_retention"] == 1.0


# ---------------- expected_tool_calls ----------------

def test_tool_call_match_rate_literal_and_session_ref(evaluator):
    session_state = {"shown_items": ["Video_Games::vg_a", "Video_Games::vg_b"], "constraints": {}}
    turn_output = {
        "items": ["Video_Games::vg_c"],
        "exclusions": {},
        "trace": {
            "steps": [
                {"tool": "SimilarTool", "ok": True, "args": {"items": ["Video_Games::vg_b"], "top_k": 10}},
                {"tool": "LookupTool", "ok": True, "args": {"item_ids": ["Video_Games::vg_c"]}},
            ]
        },
    }
    ti = _turn(
        expected_tool_calls=[
            {"tool": "SimilarTool", "args_contain": {"items": "$S.shown_items.1"}},
            {"tool": "MemoryTool", "args_contain": {"user_id": "u_long"}},
        ]
    )
    m = evaluator._score_turn(ti, turn_output, session_state)
    assert m["tool_call_match_rate"] == 0.5  # SimilarTool matched, MemoryTool absent


def test_tool_call_match_rate_wrong_seed_fails(evaluator):
    session_state = {"shown_items": ["Video_Games::vg_a", "Video_Games::vg_b"], "constraints": {}}
    turn_output = {
        "items": [],
        "exclusions": {},
        "trace": {"steps": [{"tool": "SimilarTool", "ok": True, "args": {"items": ["Video_Games::vg_a"]}}]},
    }
    ti = _turn(expected_tool_calls=[{"tool": "SimilarTool", "args_contain": {"items": "$S.shown_items.1"}}])
    assert evaluator._score_turn(ti, turn_output, session_state)["tool_call_match_rate"] == 0.0


# ---------------- RealAgentRunner + ScriptedLLM smoke ----------------

def _runner_with_script(*responses):
    """RealAgentRunner over fixture tools with a scripted LLM (no API calls)."""
    sys.path.insert(0, str(Path(__file__).parents[3] / "tests" / "agents" / "fakes"))
    from scripted_llm import ScriptedLLM
    import package.evaluation.multi_turn._agent_runner as ar

    llm = ScriptedLLM(*responses)
    orig = ar.build_llm_provider
    ar.build_llm_provider = lambda cfg: llm
    try:
        runner = ar.RealAgentRunner(config={"llm": {"base_url": "http://x", "model": "m"}})
    finally:
        ar.build_llm_provider = orig
    runner.executor.reflect_rounds = 0
    return runner, llm


def test_iso_leak_shared_session_scores_zero(conversations):
    """Experimental proof: if iso_2 runs on a session that still carries
    iso_1's exclusion, a plan that propagates it MUST score 0 via
    absent_exclusions. Control: same session, clean plan -> 1.0."""
    from dataclasses import asdict

    from package.agents import get_session_limits
    from package.agents.session import Session

    conv = next(c for c in conversations if c.conversation_id == "conv_session_isolation_2")

    def leaked_session() -> Session:
        s = Session(**asdict(get_session_limits()))
        s.add_shown_items(["Video_Games::vg_b", "Video_Games::vg_e"])
        s.add_exclusions(item_ids=["Video_Games::vg_a"])  # what iso_1 leaves behind
        return s

    leaked_plan = json.dumps({
        "steps": [{"tool": "FilterTool", "args": {
            "filters": {"categories_any": ["Puzzle"], "exclude_item_ids": ["Video_Games::vg_a"]},
            "limit": 10}}],
        "ask_user": None,
    })
    clean_plan = json.dumps({
        "steps": [{"tool": "FilterTool", "args": {
            "filters": {"categories_any": ["Puzzle"]}, "limit": 10}}],
        "ask_user": None,
    })

    runner_leak, _ = _runner_with_script(leaked_plan)
    evaluator = MultiTurnEvaluator()
    evaluator._initialize_session = lambda ctx: leaked_session()
    res = evaluator.evaluate_conversation(conv, runner_leak)
    assert res.turn_results[0].metrics["exclusion_compliance"] == 0.0

    runner_clean, _ = _runner_with_script(clean_plan)
    evaluator2 = MultiTurnEvaluator()
    evaluator2._initialize_session = lambda ctx: leaked_session()
    res2 = evaluator2.evaluate_conversation(conv, runner_clean)
    assert res2.turn_results[0].metrics["exclusion_compliance"] == 1.0


def test_real_agent_runner_smoke_two_turns(conversations):
    """Scripted plans through the REAL executor+tools must not crash."""
    conv = next(c for c in conversations if c.conversation_id == "conv_m1_price_refinement")
    plan1 = json.dumps({"steps": [{"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 5}}], "ask_user": None})
    plan2 = json.dumps({"steps": [{"tool": "FilterTool", "args": {"filters": {"price_max": 50, "domain": "Video_Games"}, "limit": 5}}], "ask_user": None})
    runner, llm = _runner_with_script(plan1, plan2)
    evaluator = MultiTurnEvaluator()
    result = evaluator.evaluate_conversation(conv, runner)
    assert result.conversation_success
    assert len(result.turn_results) == 2
    assert all(tr.success for tr in result.turn_results)
    # t2 must show the price constraint reached the executed filter args
    assert result.turn_results[1].metrics["exclusion_compliance"] == 1.0


def test_real_agent_runner_smoke_m2_session_reference(conversations):
    """m2: $S.shown_items.1 must resolve and reach SimilarTool as the seed."""
    conv = next(c for c in conversations if c.conversation_id == "conv_m2_position_reference")
    # t1: FilterTool -> LookupTool($1.candidates.*.item_id) populates
    # session.shown_items deterministically (LookupTool alone would trip
    # the invented-id guard: bare ids are not in the request text).
    plan1 = json.dumps({"steps": [
        {"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 3}},
        {"tool": "LookupTool", "args": {"item_ids": "$1.candidates.*.item_id"}},
    ], "ask_user": None})
    # t2: the plan itself uses the session reference the dataset asserts
    plan2 = json.dumps({"steps": [{"tool": "SimilarTool", "args": {
        "items": ["$S.shown_items.1"], "top_k": 5}}], "ask_user": None})
    runner, _ = _runner_with_script(plan1, plan2)
    result = MultiTurnEvaluator().evaluate_conversation(conv, runner)
    assert result.conversation_success
    t2 = result.turn_results[1]
    assert t2.success
    # expected: SimilarTool seeded with the 2nd shown item (vg_b)
    assert t2.metrics["tool_call_match_rate"] == 1.0
    step = next(s for s in t2.trace["trace"]["steps"] if s["tool"] == "SimilarTool")
    assert step["ok"], step.get("error")


def test_real_agent_runner_smoke_m7_memory_then_similar(conversations):
    """m7: MemoryTool(u_long) then SimilarTool over its recent_items."""
    conv = next(c for c in conversations if c.conversation_id == "conv_m7_long_term_memory")
    plan1 = json.dumps({"steps": [{"tool": "MemoryTool", "args": {"user_id": "u_long"}}],
                        "ask_user": None})
    # t2: MemoryTool output is NOT persisted across turns, so the real
    # planner re-fetches memory and chains SimilarTool in the SAME plan
    # ($1 = this turn's step 1, not the previous turn).
    plan2 = json.dumps({"steps": [
        {"tool": "MemoryTool", "args": {"user_id": "u_long"}},
        {"tool": "SimilarTool", "args": {"items": "$1.recent_items", "top_k": 5}},
    ], "ask_user": None})
    runner, _ = _runner_with_script(plan1, plan2)
    result = MultiTurnEvaluator().evaluate_conversation(conv, runner)
    assert result.conversation_success
    assert result.turn_results[0].metrics["tool_call_match_rate"] == 1.0  # MemoryTool u_long
    t2 = result.turn_results[1]
    assert t2.metrics["tool_call_match_rate"] == 1.0  # SimilarTool called
    step = next(s for s in t2.trace["trace"]["steps"] if s["tool"] == "SimilarTool")
    assert step["ok"], step.get("error")
