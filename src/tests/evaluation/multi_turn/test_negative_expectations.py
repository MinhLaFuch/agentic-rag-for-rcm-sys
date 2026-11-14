"""Week-47 multi-turn additions: expect_clarification / expect_no_result,
resolved-config recording, limits plumbing, nested-metric extraction.

No LLM anywhere: the runner is faked at run_turn level; RealAgentRunner is
only touched via __new__ for resolved_config (its __init__ needs credentials).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from package.evaluation.multi_turn import _eval_step
from package.evaluation.multi_turn._schema import TurnInput, Conversation
from package.evaluation.multi_turn._run import load_conversations
from package.evaluation.multi_turn.multi_turn_evaluator import MultiTurnEvaluator
from package.evaluation.multi_turn._agent_runner import RealAgentRunner

DATASET = (
    Path(__file__).parents[3]
    / "package" / "evaluation" / "multi_turn" / "conversations.jsonl"
)


# --- schema round-trip -----------------------------------------------------

def test_turn_input_expect_flags_roundtrip():
    t = TurnInput(
        turn_id="t", position=0, user_request="r",
        expect_clarification=True, expect_no_result=True,
    )
    restored = TurnInput.from_dict(t.to_dict())
    assert restored.expect_clarification is True
    assert restored.expect_no_result is True
    # absent keys default to False (backward compat with old datasets)
    old = TurnInput.from_dict({"turn_id": "x", "position": 0, "user_request": "r"})
    assert old.expect_clarification is False and old.expect_no_result is False


# --- turn scoring -----------------------------------------------------------

def _score(turn_input, turn_output):
    return MultiTurnEvaluator()._score_turn(turn_input, turn_output, {})


def test_expect_no_result_scores_empty_vs_invented():
    ti = TurnInput(turn_id="t", position=0, user_request="r", expect_no_result=True)
    ok = _score(ti, {"items": [], "exclusions": {}, "trace": {"steps": []}})
    bad = _score(ti, {"items": ["Video_Games::vg_a"], "exclusions": {}, "trace": {"steps": []}})
    assert ok["no_result_compliance"] == 1.0
    assert bad["no_result_compliance"] == 0.0


def test_expect_clarification_scores_question_vs_guess():
    ti = TurnInput(turn_id="t", position=0, user_request="r", expect_clarification=True)
    asked = _score(ti, {"items": [], "exclusions": {}, "trace": {"question": "which genre?", "steps": []}})
    guessed = _score(ti, {"items": ["Video_Games::vg_a"], "exclusions": {}, "trace": {"question": None, "steps": []}})
    assert asked["clarification_compliance"] == 1.0
    assert guessed["clarification_compliance"] == 0.0


def test_expect_flags_absent_leave_metrics_none():
    ti = TurnInput(turn_id="t", position=0, user_request="r")
    m = _score(ti, {"items": [], "exclusions": {}, "trace": {"steps": []}})
    assert m["clarification_compliance"] is None
    assert m["no_result_compliance"] is None


def test_conversation_metrics_include_compliance_means():
    ev = MultiTurnEvaluator()
    conv = Conversation(conversation_id="c", turns=[
        TurnInput(turn_id="t1", position=0, user_request="r", expect_no_result=True),
        TurnInput(turn_id="t2", position=1, user_request="r"),
    ])
    results = [
        # t1: empty result as expected; t2: no expectation -> excluded from mean
        SimpleNamespace(metrics={"no_result_compliance": 1.0, "clarification_compliance": None}),
        SimpleNamespace(metrics={"no_result_compliance": None, "clarification_compliance": None}),
    ]
    # _calculate_conversation_metrics reads tr.metrics + tr.success via TurnResult;
    # use real TurnResult objects for safety
    from package.evaluation.multi_turn import TurnResult
    results = [
        TurnResult(turn_id="t1", success=True, metrics={"no_result_compliance": 1.0}),
        TurnResult(turn_id="t2", success=True, metrics={"no_result_compliance": None}),
    ]
    m = ev._calculate_conversation_metrics(results, conv)
    assert m["no_result_compliance"] == 1.0  # mean over the ONE expecting turn
    assert "clarification_compliance" not in m


# --- dataset additions -------------------------------------------------------

def test_new_negative_conversations_load_with_flags():
    convs = {c.conversation_id: c for c in load_conversations(DATASET)}
    negc = convs["conv_neg_clarification_trap"]
    assert negc.turns[0].expect_clarification is True
    assert negc.turns[0].expected_items == []
    assert negc.turns[1].expected_items  # clarified turn expects real items
    negn = convs["conv_neg_no_result"]
    assert negn.turns[0].expect_no_result is True
    assert negn.turns[1].expected_exclusions == {"price_max": 2}


# --- limits plumbing ---------------------------------------------------------

def test_run_multi_turn_eval_forwards_limits_json(tmp_path, monkeypatch):
    out = tmp_path / "mt.json"
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        Path(cmd[cmd.index("--output") + 1]).write_text(
            json.dumps({"turn_success_rate": 1.0}), encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(_eval_step.subprocess, "run", fake_run)
    monkeypatch.setattr(_eval_step, "_llm_configured", lambda: True)
    _eval_step.run_multi_turn_eval(
        dataset="d.jsonl", output_path=out, limits={"max_steps_per_turn": 4}
    )
    assert "--limits-json" in seen["cmd"]
    payload = json.loads(seen["cmd"][seen["cmd"].index("--limits-json") + 1])
    assert payload == {"max_steps_per_turn": 4}


def test_for_eval_block_passes_limits(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        _eval_step, "run_multi_turn_eval",
        lambda **kw: captured.update(kw) or {"status": "success"},
    )
    _eval_step.run_multi_turn_for_eval(
        {"enabled": True, "limits": {"turn_timeout_seconds": 60}},
        tmp_path / "default.json",
    )
    assert captured["limits"] == {"turn_timeout_seconds": 60}


# --- resolved_config ---------------------------------------------------------

def test_resolved_config_shape_without_llm():
    runner = RealAgentRunner.__new__(RealAgentRunner)
    runner.executor = SimpleNamespace(reflect_rounds=1, tools={"FilterTool": 1, "MemoryTool": 2})
    runner.limits = {"max_steps_per_turn": 4}
    cfg = runner.resolved_config()
    assert cfg["reflect_rounds"] == 1
    assert cfg["tools"] == ["FilterTool", "MemoryTool"]
    assert cfg["limits"] == {"max_steps_per_turn": 4}
    assert cfg["limits_enforced"] is False


# --- campaign-level metric extraction ----------------------------------------

def test_extract_multi_turn_metrics_pulls_nested_aggregates():
    summary = {
        "status": "success",
        "turn_success_rate": 1.0,
        "metrics": {
            "avg_item_match_rate_mean": 0.72,
            "exclusion_compliance_mean": 0.95,
            "clarification_compliance_mean": 0.5,
            "unrelated_mean": 0.1,
        },
    }
    out = _eval_step.extract_multi_turn_metrics(summary)
    assert out["avg_item_match_rate_mean"] == 0.72
    assert out["exclusion_compliance_mean"] == 0.95
    assert out["clarification_compliance_mean"] == 0.5
    assert "unrelated_mean" not in out
