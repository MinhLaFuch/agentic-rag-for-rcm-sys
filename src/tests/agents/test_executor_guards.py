"""Test PlanExecutor._execute guards (deterministic with fake tools)."""

import json
import pytest

from package.agents import PlanExecutor
from package.api import LLMProviderError
from tests.agents.fakes.fake_tools import FakeSQLTool, FakeQueryTool, FakeItemCFTool
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.agents.fakes.sample_data import build_plan_json


def test_unknown_tool_rejected_no_tool_called():
    """Tool not in the list → step ok=False, error 'unknown tool', no tool executed."""
    call_counter = [0]
    tool = FakeSQLTool(call_counter=call_counter)
    llm = ScriptedLLM(build_plan_json({"tool": "UnknownTool", "args": {}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert not results[0]["ok"]
    assert "unknown tool" in results[0]["error"]
    assert call_counter[0] == 0  # tool not called


def test_invented_id_rejected_no_tool_called():
    """Items list contains id not in request → step ok=False, invented_ids=[id], tool not called."""
    call_counter = [0]
    tool = FakeQueryTool(call_counter=call_counter)
    request = "recommend something about Video_Games::real_item"
    # Plan uses an invented id not in request
    llm = ScriptedLLM(build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::invented_id"]}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run(request)
    assert len(results) == 1
    assert not results[0]["ok"]
    assert "invented_ids" in results[0]
    assert "Video_Games::invented_id" in results[0]["invented_ids"]
    assert call_counter[0] == 0  # tool not called


def test_id_from_request_executed():
    """Id from request is in the text → tool is called."""
    call_counter = [0]
    tool = FakeQueryTool(call_counter=call_counter, fixed_data={"items": [], "missing_item_ids": [], "truncated": False})
    request = "tell me about Video_Games::real_item"
    llm = ScriptedLLM(build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::real_item"]}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run(request)
    assert len(results) == 1
    assert results[0]["ok"]
    assert results[0]["invented_ids"] == []
    assert call_counter[0] == 1  # tool was called


def test_unknown_arg_outside_filters_rejected():
    """price_max placed outside filters → error with hint, tool not called."""
    call_counter = [0]
    tool = FakeSQLTool(call_counter=call_counter)
    # price_max should be inside filters
    llm = ScriptedLLM(build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}, "price_max": 100}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert not results[0]["ok"]
    assert "unknown arg" in results[0]["error"]
    assert "price_max" in results[0]["error"]
    assert "filters" in results[0]["error"]  # hint
    assert call_counter[0] == 0


def test_reference_to_future_step_rejected():
    """Reference $5.x when only 3 steps exist → error about step not run yet."""
    tool1 = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    tool2 = FakeQueryTool(fixed_data={"items": [], "missing_item_ids": [], "truncated": False})
    call_counter = [0]
    tool3 = FakeItemCFTool(call_counter=call_counter)
    # Step 3 references $5 which doesn't exist yet
    llm = ScriptedLLM(build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": ["$1.candidates.*.item_id"]}},
        {"tool": "ItemCFTool", "args": {"items": "$5.candidates.*.item_id"}},
    ))
    executor = PlanExecutor(llm, [tool1, tool2, tool3], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 3
    # First two steps run (step 2 will fail because $1.candidates is empty, but that's ok for this test)
    assert results[0]["ok"]
    assert not results[2]["ok"]
    assert "step 5 has not run yet" in results[2]["error"]


def test_reference_to_nonexistent_field_rejected():
    """$1.abc when step 1 output doesn't have abc → error listing available fields."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    llm = ScriptedLLM(build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.abc"}},
    ))
    executor = PlanExecutor(llm, [tool, FakeQueryTool()], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 2
    assert results[0]["ok"]
    assert not results[1]["ok"]
    assert "abc" in results[1]["error"]
    # Should list available fields
    assert "candidates" in results[1]["error"] or "SQLTool" in results[1]["error"]


def test_reference_to_failed_step_rejected():
    """Reference to a step that failed → error 'skipped, step N failed'."""
    tool1 = FakeSQLTool(fixed_error="test error")
    tool2 = FakeQueryTool()
    llm = ScriptedLLM(build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.candidates.*.item_id"}},
    ))
    executor = PlanExecutor(llm, [tool1, tool2], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 2
    assert not results[0]["ok"]
    assert not results[1]["ok"]
    assert "skipped, step 1 failed" in results[1]["error"]


def test_wildcard_on_non_list_rejected():
    """'*' on a value that is not a list → error."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    llm = ScriptedLLM(build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.total_matches.*"}},  # total_matches is int, not list
    ))
    executor = PlanExecutor(llm, [tool, FakeQueryTool()], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 2
    assert results[0]["ok"]
    assert not results[1]["ok"]
    assert "'*' needs a list" in results[1]["error"]


def test_plan_truncated_to_max_steps():
    """Plan longer than max_steps → last_truncated=True, only max_steps run."""
    step = {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}
    call_counter = [0]
    tool = FakeSQLTool(call_counter=call_counter, fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    llm = ScriptedLLM(build_plan_json(step, step, step, step, step))
    executor = PlanExecutor(llm, [tool], max_steps=2, reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 2
    assert executor.last_truncated
    assert call_counter[0] == 2


def test_tool_exception_does_not_crash_executor():
    """Tool raises arbitrary exception → step ok=False, run() doesn't raise."""
    tool1 = FakeSQLTool(raise_exception=RuntimeError("test exception"))
    tool2 = FakeQueryTool(fixed_data={"items": [], "missing_item_ids": [], "truncated": False})
    # Make second step independent of first (no reference)
    llm = ScriptedLLM(build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": ["Video_Games::test"]}},
    ))
    executor = PlanExecutor(llm, [tool1, tool2], reflect_rounds=0)
    results = executor.run("test")  # should not raise
    assert len(results) == 2
    assert not results[0]["ok"]
    assert "RuntimeError" in results[0]["error"]
    # Note: second step still runs because it has no dependency on first step


def test_ask_user_no_steps_sets_last_question():
    """ask_user with question, no steps → last_question set, no tools called."""
    call_counter = [0]
    tool = FakeSQLTool(call_counter=call_counter)
    llm = ScriptedLLM(build_plan_json(ask_user="Which product type?"))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert results == []
    assert executor.last_question == "Which product type?"
    assert call_counter[0] == 0
