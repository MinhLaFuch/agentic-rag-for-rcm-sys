"""Test plan building and retry with ScriptedLLM."""

import json
import pytest

from package.agents import PlanExecutor
from package.api import LLMProviderError
from tests.agents.fakes.fake_tools import FakeSQLTool
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.agents.fakes.sample_data import build_plan_json


def test_empty_text_triggers_retry_with_retry_notice():
    """Empty text → retry with RETRY_NOTICE, succeeds on second attempt."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    good_plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM("", good_plan)  # First empty, then good
    executor = PlanExecutor(llm, [tool], plan_retries=1, reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]
    assert executor.last_usage["attempts"] == 2
    # Check RETRY_NOTICE was sent (via the LLM call count)
    assert len(llm.calls) == 2


def test_none_text_triggers_retry():
    """None → retry with RETRY_NOTICE."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    good_plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(None, good_plan)
    executor = PlanExecutor(llm, [tool], plan_retries=1, reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]
    assert executor.last_usage["attempts"] == 2


def test_non_json_triggers_retry():
    """Not JSON → retry with RETRY_NOTICE."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    good_plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM("not json at all", good_plan)
    executor = PlanExecutor(llm, [tool], plan_retries=1, reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]
    assert executor.last_usage["attempts"] == 2


def test_exhausted_retries_raises_value_error():
    """All retries exhausted → ValueError raised."""
    tool = FakeSQLTool()
    llm = ScriptedLLM("bad", "still bad", "nope")
    executor = PlanExecutor(llm, [tool], plan_retries=2, reflect_rounds=0)
    with pytest.raises(ValueError, match="LLM did not return valid JSON"):
        executor.run("test")
    assert executor.last_usage["attempts"] == 3


def test_json_wrapped_in_code_blocks_is_parsed():
    """JSON wrapped in ```json ... ``` is still parsed."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    wrapped_plan = "```json\n" + build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}) + "\n```"
    llm = ScriptedLLM(wrapped_plan)
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]


def test_json_object_with_plan_key_is_accepted():
    """JSON object with {"plan": [...]} is accepted."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    plan_with_key = json.dumps({"plan": [{"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}]})
    llm = ScriptedLLM(plan_with_key)
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]


def test_bare_list_is_accepted():
    """Bare list [...steps] is accepted."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    bare_list = json.dumps([{"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}])
    llm = ScriptedLLM(bare_list)
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")
    assert len(results) == 1
    assert results[0]["ok"]


def test_usage_accumulates_across_retries():
    """last_usage accumulates correctly across retries."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    good_plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM("", good_plan)
    executor = PlanExecutor(llm, [tool], plan_retries=1, reflect_rounds=0)
    executor.run("test")
    u = executor.last_usage
    assert u["attempts"] == 2
    assert u["prompt_tokens"] == 20  # 10 * 2
    assert u["completion_tokens"] == 10  # 5 * 2
    assert u["latency_seconds"] == 0.2  # 0.1 * 2
