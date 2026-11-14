"""Tests for multi-turn summary turn-count fields and honest reporting.

Covers the Phase-A metric fixes: total_turns_scheduled/executed,
avg_turns_per_conversation, turn_completion_ratio, failed_conversation_ids —
plus _run_all mapping (p95 -> None, failed_cases = failed conversations,
failure_distribution surfaced) and markdown "n/a" rendering.

All offline: stub agent runners, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from package.evaluation.component import _run_all
from package.evaluation.multi_turn._run import load_conversations
from package.evaluation.multi_turn._schema import ConversationSummary
from package.evaluation.multi_turn.multi_turn_evaluator import MultiTurnEvaluator

DATASET = (
    Path(__file__).resolve().parents[3]
    / "package" / "evaluation" / "multi_turn" / "conversations.jsonl"
)


class PerfectRunner:
    """Returns the expected items/exclusions for every turn — all succeed."""

    def run_turn(self, turn_input, session):
        return {
            "items": list(turn_input.expected_items),
            "exclusions": dict(turn_input.expected_exclusions),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "trace": {"steps": []},
        }


class FailOnTurn:
    """Fails when turn_id matches; other turns behave like PerfectRunner."""

    def __init__(self, fail_turn_id: str):
        self._inner = PerfectRunner()
        self._fail_turn_id = fail_turn_id

    def run_turn(self, turn_input, session):
        if turn_input.turn_id == self._fail_turn_id:
            raise RuntimeError("boom")
        return self._inner.run_turn(turn_input, session)


def _summary(runner) -> ConversationSummary:
    convs = load_conversations(DATASET)
    return MultiTurnEvaluator().evaluate_conversations(convs, runner, git_sha="test")


# --- hand-computed expectations over the 11 fixture conversations ---------
# 11 conversations x 2 turns + 2 conversations x 1 turn = 24 scheduled turns (13 convs after week-47 additions).


def test_turn_counts_all_success():
    s = _summary(PerfectRunner())
    assert s.total_turns_scheduled == 24
    assert s.total_turns_executed == 24
    assert s.avg_turns_per_conversation == pytest.approx(24 / 13)
    assert s.turn_completion_ratio == pytest.approx(1.0)
    assert s.failed_conversations == 0
    assert s.failed_conversation_ids == []


def test_turn_counts_fail_on_first_turn():
    # conv_m1_t1 fails -> conv_m1 stops after 1 executed turn; its t2 never runs.
    s = _summary(FailOnTurn("m1_t1"))
    assert s.total_turns_scheduled == 24
    assert s.total_turns_executed == 23
    assert s.turn_completion_ratio == pytest.approx(23 / 24)
    assert s.avg_turns_per_conversation == pytest.approx(23 / 13)
    assert s.failed_conversations == 1
    assert s.failed_conversation_ids == ["conv_m1_price_refinement"]
    # turn_success_rate denominator is EXECUTED turns: 18/19, not 18/20
    assert s.turn_success_rate == pytest.approx(22 / 23)
    assert s.conversation_success_rate == pytest.approx(12 / 13)


def test_turn_counts_fail_on_last_turn():
    # conv_m1_t2 fails -> both turns executed, only the last one failed.
    s = _summary(FailOnTurn("m1_t2"))
    assert s.total_turns_executed == 24
    assert s.turn_completion_ratio == pytest.approx(1.0)
    assert s.turn_success_rate == pytest.approx(23 / 24)
    assert s.failed_conversation_ids == ["conv_m1_price_refinement"]


# --- schema backward compatibility ----------------------------------------


def test_from_dict_old_json_without_new_fields():
    old = {
        "multi_turn_version": "1.0.0",
        "total_conversations": 11,
        "turn_success_rate": 0.9,
        "conversation_success_rate": 0.8,
        "metrics": {},
        "latency": {"mean": 1.0},
    }
    s = ConversationSummary.from_dict(old)
    assert s.total_turns_scheduled == 0
    assert s.total_turns_executed == 0
    assert s.avg_turns_per_conversation is None
    assert s.turn_completion_ratio is None
    assert s.failed_conversation_ids == []
    assert s.failed_conversations == 0


def test_roundtrip_preserves_new_fields():
    s = _summary(FailOnTurn("m1_t1"))
    s2 = ConversationSummary.from_dict(json.loads(json.dumps(s.to_dict())))
    assert s2.total_turns_executed == 23
    assert s2.turn_completion_ratio == pytest.approx(23 / 24)
    assert s2.failed_conversation_ids == ["conv_m1_price_refinement"]


# --- _run_all mapping ------------------------------------------------------


def _write_mt_result(path, **overrides):
    data = {
        "multi_turn_version": "1.0.0",
        "total_conversations": 11,
        "turn_success_rate": 0.95,
        "conversation_success_rate": 0.909,
        "total_turns_scheduled": 20,
        "total_turns_executed": 19,
        "avg_turns_per_conversation": 19 / 11,
        "turn_completion_ratio": 0.95,
        "failed_conversation_ids": ["conv_m1_price_refinement"],
        "failed_conversations": 1,
        "metrics": {"item_match_rate_mean": 0.9},
        "latency": {"mean": 1.2, "min": 0.5, "max": 3.0},  # NOTE: no p95
        "failure_distribution": {"turn_0": 1},
        "git_sha": "abc",
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _info(result_file):
    return {"result_file": result_file, "error": None, "not_implemented": False}


def test_run_all_multi_turn_p95_is_none_not_zero(tmp_path):
    f = _write_mt_result(tmp_path / "mt.json")
    agg = _run_all.aggregate_results({"multi_turn": _info(f)})
    mt = agg["components"]["multi_turn"]
    assert mt["latency"]["p95"] is None
    assert mt["latency"]["mean"] == 1.2


def test_run_all_multi_turn_failed_cases_and_distribution(tmp_path):
    f = _write_mt_result(tmp_path / "mt.json")
    agg = _run_all.aggregate_results({"multi_turn": _info(f)})
    mt = agg["components"]["multi_turn"]
    assert mt["failed_cases"] == 1
    assert mt["failed_conversation_ids"] == ["conv_m1_price_refinement"]
    assert mt["turn_completion_ratio"] == pytest.approx(0.95)
    assert mt["failure_distribution"] == {"turn_0": 1}


def test_run_all_multi_turn_old_result_file_failed_cases_none(tmp_path):
    # Result files written before the metric fixes have no failed_conversations.
    f = _write_mt_result(tmp_path / "mt.json")
    data = json.loads(Path(f).read_text(encoding="utf-8"))
    for k in ("failed_conversations", "failed_conversation_ids",
              "turn_completion_ratio", "total_turns_scheduled",
              "total_turns_executed"):
        data.pop(k, None)
    Path(f).write_text(json.dumps(data), encoding="utf-8")
    agg = _run_all.aggregate_results({"multi_turn": _info(f)})
    mt = agg["components"]["multi_turn"]
    assert mt["failed_cases"] is None  # unknown, not a fake 0
    assert mt["latency"]["p95"] is None


def test_markdown_renders_p95_na_and_failed_ids(tmp_path):
    f = _write_mt_result(tmp_path / "mt.json")
    agg = _run_all.aggregate_results({"multi_turn": _info(f)})
    out = tmp_path / "report.md"
    _run_all.generate_markdown_report(agg, out)
    text = out.read_text(encoding="utf-8")
    assert "P95 latency: n/a" in text
    assert "0.0000s" not in text.split("P95 latency")[1].split("\n")[0]
    assert "conv_m1_price_refinement" in text
    assert "fixture corpus" in text
