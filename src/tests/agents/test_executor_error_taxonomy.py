"""Executor error-taxonomy tests: infra/tool failures → reflection behavior.

These replace the retired executor benchmark's fault-injection cases
(old executor_dataset.jsonl executor_003..executor_034). They are UNIT TESTS,
not benchmark evidence: fake tools inject failures on purpose.

PlanExecutor treats tool-level failures uniformly — every ToolInputError /
ok=False result becomes error_kind="tool_error" and triggers reflection
(except time-budget errors and invented ids, which _blocks_reflect skips).
The parametrized cases below document that the *text* of an infra error
(timeout, rate limit, network, auth, ...) does not change executor behavior;
only the error_kind does.
"""

from typing import Any

import pytest

from package.agents import PlanExecutor
from package.tools.base import ToolInputError
from tests.agents.fakes.fake_tools import FakeFilterTool, FakeLookupTool
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.agents.fakes.sample_data import build_items, build_plan_json

# Infra-failure labels ported from the retired executor_dataset.jsonl.
# PlanExecutor cannot distinguish them — all surface as tool_error.
INFRA_ERRORS = [
    "sql_fail: generic failure",
    "sql_rate_limit: too many requests",
    "sql_network_error: connection reset",
    "sql_auth_error: authentication failed",
    "sql_schema_error: column does not exist",
    "sql_data_error: constraint violation",
    "sql_concurrent_error: deadlock detected",
    "sql_resource_error: out of memory",
    "sql_validation_error: invalid argument",
    "sql_permission_error: access denied",
    "sql_generic_error: unexpected error",
    "sql_random_error: transient fault",
    "sql_malformed: response was not valid JSON",
]

FILTER_ARGS = {"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}}}
OK_DATA = {
    "candidates": build_items("vg_a"),
    "total_matches": 1,
    "truncated": False,
    "applied_filters": {},
}


class _FlakyFilterTool(FakeFilterTool):
    """Fails the first call with a given error, then returns OK_DATA.

    Needed because PlanExecutor keys tools by name — two FakeFilterTool
    instances would collapse into one dict entry.
    """

    def __init__(self, error_text: str):
        super().__init__()
        self._error_text = error_text
        self._calls = 0

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._calls += 1
        if self._calls == 1:
            raise ToolInputError(self._error_text)
        return OK_DATA


@pytest.mark.parametrize("error_text", INFRA_ERRORS)
def test_tool_error_triggers_reflection_and_can_be_rescued(error_text):
    """Any tool-level failure → step fails (tool_error) → reflection → rescue."""
    tool = _FlakyFilterTool(error_text)

    plan1 = build_plan_json(FILTER_ARGS)
    plan2 = build_plan_json(FILTER_ARGS)
    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)

    results = executor.run("test request")

    assert executor.last_reflections == 1
    assert executor.last_first_attempt_ok is False
    assert results[0]["ok"]  # rescued on the reflected retry


@pytest.mark.parametrize("error_text", INFRA_ERRORS)
def test_tool_error_without_rescue_keeps_failure(error_text):
    """Reflection cannot rescue when the retried plan fails again."""
    tool = FakeFilterTool(fixed_error=error_text)

    plan1 = build_plan_json(FILTER_ARGS)
    plan2 = build_plan_json(FILTER_ARGS)
    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [tool], reflect_rounds=1)

    results = executor.run("test request")

    assert executor.last_reflections == 1
    assert results[0]["ok"] is False
    assert results[0]["error_kind"] == "tool_error"


def test_exception_in_tool_is_error_kind_exception_not_tool_error():
    """Non-ToolInputError exceptions surface as error_kind='exception'."""
    tool = FakeFilterTool(raise_exception=RuntimeError("boom"))
    results = PlanExecutor(ScriptedLLM("[]"), [tool], reflect_rounds=0)._execute(
        [FILTER_ARGS], "test"
    )
    assert results[0]["ok"] is False
    assert results[0]["error_kind"] == "exception"


def test_time_budget_error_never_reflected():
    """SQL time-budget errors block reflection (a new plan would not help)."""
    tool = FakeFilterTool(fixed_error="query exceeded SQL time budget")
    llm = ScriptedLLM(build_plan_json(FILTER_ARGS), build_plan_json(FILTER_ARGS))
    executor = PlanExecutor(llm, [tool], reflect_rounds=2)

    results = executor.run("test request")

    assert executor.last_reflections == 0
    assert results[0]["ok"] is False


def test_empty_result_triggers_reflection_and_rescues():
    """Empty tool output (ok=True, no items) → reflection → rescue."""
    empty = FakeLookupTool(fixed_data={"items": [], "missing_item_ids": [], "truncated": False})
    full = FakeLookupTool(fixed_data={"items": build_items("vg_a"), "missing_item_ids": [], "truncated": False})

    step = {"tool": "LookupTool", "args": {"item_ids": ["vg_a"]}}
    llm = ScriptedLLM(build_plan_json(step), build_plan_json(step))
    executor = PlanExecutor(llm, [empty], reflect_rounds=1)

    # Same tool instance: first call empty, second call returns items.
    calls = {"n": 0}
    orig_execute = empty.execute

    def execute_then_full(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return orig_execute(**kwargs)
        return full.execute(**kwargs)

    empty.execute = execute_then_full
    results = executor.run("tell me about vg_a")

    assert executor.last_reflections == 1
    assert results[0]["ok"]
