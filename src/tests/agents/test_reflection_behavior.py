"""Test reflection behavior with ScriptedLLM and fake tools."""

import pytest

from package.agents import PlanExecutor
from package.api import LLMProviderError
from package.tools.corpus import _error as corpus_error
from tests.agents.fakes.fake_tools import (
    FakeSQLTool,
    FakeQueryTool,
    FakeItemCFTool,
    FakeRecoModelTool,
    FakeMemoryTool,
)
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.agents.fakes.sample_data import build_plan_json, build_items


def test_empty_plan_triggers_reflection_then_succeeds():
    """Reflection when plan runs ok but returns no items (empty candidates)."""
    # QueryTool returns empty items on first attempt
    tool = FakeQueryTool(fixed_data={"items": [], "missing_item_ids": [], "truncated": False})

    plan1 = build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["test_id"]}})
    plan2 = build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["test_id"]}})

    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    # Include test_id in request to avoid invented_ids check
    results = executor.run("tell me about test_id")

    # Empty items should trigger reflection
    assert executor.last_reflections == 1
    assert executor.last_first_attempt_ok is False
    assert len(executor.last_attempt_plans) == 2
    # The step ran ok but with no items
    assert len(results) == 1
    assert results[0]["ok"]


def test_failed_step_triggers_reflection():
    """Step fails → reflect."""
    tool1 = FakeSQLTool(fixed_error="test error")
    tool2 = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})

    plan1 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    plan2 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})

    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool1, tool2], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 1
    assert executor.last_first_attempt_ok is False
    assert len(results) == 1
    assert results[0]["ok"]  # plan 2 succeeded


def test_failed_step_due_to_bad_reference_triggers_reflection():
    """Step fails due to bad reference → reflect."""
    tool1 = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    tool2 = FakeQueryTool()

    plan1 = build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.abc"}},  # bad reference
    )
    plan2 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})

    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool1, tool2], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 1
    assert len(results) == 1
    assert results[0]["ok"]


def test_no_reflect_with_invented_ids():
    """No reflect when there are invented_ids."""
    tool = FakeQueryTool()
    plan = build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["invented_id"]}})
    request = "test"
    llm = ScriptedLLM(plan, build_plan_json({"tool": "QueryTool", "args": {"item_ids": ["real_id"]}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    results = executor.run(request)

    assert executor.last_reflections == 0
    assert not results[0]["ok"]
    assert "invented_ids" in results[0]


def test_no_reflect_with_time_budget_error():
    """No reflect when error contains 'time budget' or 'SQLTimeOutError'."""
    class TimeoutTool(FakeSQLTool):
        def execute(self, **kwargs):
            raise corpus_error.SQLTimeOutError("query exceeded the time budget")

    tool = TimeoutTool()
    plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(plan, build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 0
    assert not results[0]["ok"]
    assert "time budget" in results[0]["error"]


def test_no_reflect_when_reflect_rounds_is_zero():
    """No reflect when reflect_rounds=0."""
    tool = FakeSQLTool(fixed_error="test error")
    plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(plan, build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=0)
    results = executor.run("test")

    assert executor.last_reflections == 0
    assert not results[0]["ok"]


def test_no_reflect_for_ask_user():
    """No reflect when plan is ask_user."""
    tool = FakeSQLTool()
    plan = build_plan_json(ask_user="Which product?")
    llm = ScriptedLLM(plan, build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}}))
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 0
    assert executor.last_first_attempt_ok is True
    assert results == []


def test_no_reflect_when_first_attempt_ok():
    """No reflect when first attempt already ok."""
    # Plan with items (candidates with item_id)
    tool = FakeSQLTool(fixed_data={"candidates": build_items("item1"), "total_matches": 1, "truncated": False, "applied_filters": {}})
    plan = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(plan)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 0
    assert executor.last_first_attempt_ok is True


def test_bad_reflect_reply_keeps_old_result():
    """Reflect reply not usable (empty, non-JSON, LLMProviderError, empty plan) → keep old result."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    plan1 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    # Reflect reply is not JSON
    llm = ScriptedLLM(plan1, "sorry, I cannot")
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    results = executor.run("test")

    assert executor.last_reflections == 1  # counts the attempt
    assert len(results) == 1
    assert results[0]["ok"]  # keeps old result


def test_reflect_rounds_limited_stops_correctly():
    """reflect_rounds=2 with plan 2 still empty → exactly 2 rounds then stop."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    plan1 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    plan2 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    plan3 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(plan1, plan2, plan3)
    executor = PlanExecutor(llm, [tool], reflect_rounds=2)
    results = executor.run("test")

    assert executor.last_reflections == 2
    assert len(executor.last_attempt_plans) == 3
    assert len(llm.calls) == 3  # initial + 2 reflects


def test_negative_reflect_rounds_raises_value_error():
    """reflect_rounds < 0 → ValueError."""
    tool = FakeSQLTool()
    with pytest.raises(ValueError, match="reflect_rounds must be >= 0"):
        PlanExecutor(ScriptedLLM(), [tool], reflect_rounds=-1)


def test_reflected_plan_truncated_to_max_steps():
    """Reflected plan longer than max_steps → truncated, last_truncated reflects final plan."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    plan1 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    plan2 = build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}},
    )
    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1, max_steps=2)
    results = executor.run("test")

    assert executor.last_reflections == 1
    assert executor.last_truncated
    assert len(results) == 2


def test_usage_accumulates_across_reflect():
    """last_usage accumulates across reflect calls."""
    tool = FakeSQLTool(fixed_data={"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}})
    plan1 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    plan2 = build_plan_json({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}}})
    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)
    executor.run("test")

    u = executor.last_usage
    assert u["attempts"] == 2
    assert u["prompt_tokens"] == 20
    assert u["completion_tokens"] == 10
    assert u["latency_seconds"] == 0.2
