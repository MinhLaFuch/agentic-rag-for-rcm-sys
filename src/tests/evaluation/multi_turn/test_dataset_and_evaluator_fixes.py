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
