"""Offline tests for multi_turn reporting helpers and dataset loader.

Covers package/evaluation/multi_turn/_reporting.py and the load_conversations
helper in _run.py — none of these paths need an LLM or network.
"""

from __future__ import annotations

import csv
import json

import pytest

from package.evaluation.multi_turn._reporting import (
    generate_csv_export,
    generate_failure_report,
    generate_markdown_report,
)
from package.evaluation.multi_turn._run import load_conversations
from package.evaluation.multi_turn._schema import (
    Conversation,
    ConversationResult,
    ConversationSummary,
    TurnInput,
    TurnResult,
)


def _conversation(cid: str = "c1") -> Conversation:
    return Conversation(
        conversation_id=cid,
        turns=[
            TurnInput(turn_id="t0", position=0, user_request="cheap games"),
            TurnInput(turn_id="t1", position=1, user_request="exclude vg_a"),
        ],
    )


def _result(cid: str = "c1", success: bool = True) -> ConversationResult:
    return ConversationResult(
        conversation_id=cid,
        conversation_success=success,
        turn_results=[
            TurnResult(turn_id="t0", success=True, metrics={"item_match_rate": 1.0}),
            TurnResult(turn_id="t1", success=success, error=None if success else "boom"),
        ],
        metrics={"turn_success_rate": 1.0 if success else 0.5},
        latency_seconds=0.5,
    )


def _summary() -> ConversationSummary:
    return ConversationSummary(
        total_conversations=2,
        turn_success_rate=0.75,
        conversation_success_rate=0.5,
        metrics={"item_match_rate_mean": 0.9},
        latency={"mean": 1.0, "min": 0.5, "max": 1.5},
        failure_distribution={"turn_1": 1},
        context_retention_metrics={"mean": 1.0},
        git_sha="abc123",
    )


# --- load_conversations -------------------------------------------------


def test_load_conversations_jsonl(tmp_path):
    p = tmp_path / "conv.jsonl"
    conv = _conversation("c-jsonl")
    p.write_text(json.dumps(conv.to_dict()) + "\n", encoding="utf-8")
    loaded = load_conversations(p)
    assert len(loaded) == 1
    assert loaded[0].conversation_id == "c-jsonl"
    assert loaded[0].turns[0].user_request == "cheap games"


def test_load_conversations_json_list_and_wrapped(tmp_path):
    p = tmp_path / "conv.json"
    p.write_text(json.dumps([_conversation("a").to_dict()]), encoding="utf-8")
    assert load_conversations(p)[0].conversation_id == "a"

    p2 = tmp_path / "conv2.json"
    p2.write_text(json.dumps({"conversations": [_conversation("b").to_dict()]}), encoding="utf-8")
    assert load_conversations(p2)[0].conversation_id == "b"


def test_load_conversations_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_conversations(tmp_path / "nope.jsonl")


def test_load_conversations_unsupported_suffix_raises(tmp_path):
    p = tmp_path / "conv.txt"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_conversations(p)


# --- generate_markdown_report -------------------------------------------


def test_markdown_report_contains_summary_and_details(tmp_path):
    out = tmp_path / "report.md"
    md = generate_markdown_report(
        _summary(),
        results=[_result("c1", success=True), _result("c2", success=False)],
        output_path=out,
    )
    assert "Multi-Turn Conversation Evaluation Report" in md
    assert "Turn Success Rate" in md
    assert "c2" in md  # failed conversation listed in details
    assert out.read_text(encoding="utf-8") == md


def test_markdown_report_without_results_still_renders():
    md = generate_markdown_report(_summary())
    assert "Total Conversations**: 2" in md
    assert "Detailed Conversation Results" not in md


# --- generate_csv_export -------------------------------------------------


def test_csv_export_writes_one_row_per_turn(tmp_path):
    out = tmp_path / "turns.csv"
    generate_csv_export([_result("c1")], out)
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "conversation_id"
    assert len(rows) == 3  # header + 2 turns
    assert rows[1][0] == "c1" and rows[1][1] == "t0"


# --- generate_failure_report ----------------------------------------------


def test_failure_report_lists_only_failures(tmp_path):
    out = tmp_path / "failures.md"
    generate_failure_report([_result("ok", success=True), _result("bad", success=False)], out)
    text = out.read_text(encoding="utf-8")
    assert "Failed Conversations**: 1" in text
    assert "### bad" in text
    assert "### ok" not in text
