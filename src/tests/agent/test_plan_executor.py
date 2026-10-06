"""PlanExecutor: retry on bad JSON, max_steps cut, invented-id guard, reference chaining, ask_user."""

import json

import pytest

from package.agents import PlanExecutor
from package.llm.base import LLMProvider
from package.llm._dataclass import LLMResponse
from package.tools import QueryTool, SQLTool, ToolCallLogger
from tests.tools_helpers import VG_A


class ScriptedLLM(LLMProvider):
    provider_name = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=512, response_format_json=False):
        self.calls.append(list(messages))
        return LLMResponse(text=self.replies.pop(0), prompt_tokens=10, completion_tokens=5, latency_seconds=0.1,
                           provider_name="scripted", model_name="scripted-0")


def plan(*steps, ask_user=None) -> str:
    return json.dumps({"steps": list(steps), "ask_user": ask_user})


def test_retries_once_on_invalid_json_then_succeeds(corpus):
    llm = ScriptedLLM("not json at all", plan({"tool": "SQLTool", "args": {"limit": 2}}))
    executor = PlanExecutor(llm, [SQLTool(corpus)], plan_retries=1)
    results = executor.run("list some items")
    assert results[0]["ok"]
    assert executor.last_usage["attempts"] == 2
    assert executor.last_usage["prompt_tokens"] == 20 and executor.last_usage["completion_tokens"] == 10
    retry_messages = llm.calls[1]
    assert retry_messages[-2].role == "assistant" and "rejected" in retry_messages[-1].content


def test_raises_when_retries_are_exhausted(corpus):
    executor = PlanExecutor(ScriptedLLM("nope", "still nope"), [SQLTool(corpus)], plan_retries=1)
    with pytest.raises(ValueError):
        executor.run("list some items")
    assert executor.last_usage["attempts"] == 2


def test_no_retry_when_disabled(corpus):
    llm = ScriptedLLM("nope")
    with pytest.raises(ValueError):
        PlanExecutor(llm, [SQLTool(corpus)], plan_retries=0).run("x")
    assert len(llm.calls) == 1


def test_plan_is_cut_to_max_steps(corpus):
    step = {"tool": "SQLTool", "args": {"limit": 1}}
    executor = PlanExecutor(ScriptedLLM(plan(step, step, step)), [SQLTool(corpus)], max_steps=2)
    results = executor.run("list items")
    assert len(results) == 2 and executor.last_truncated


def test_invented_id_is_reported_and_the_tool_is_not_run(corpus):
    logger = ToolCallLogger()
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::made_up"]}})), [QueryTool(corpus, logger=logger)]
    )
    results = executor.run(f"tell me about {VG_A}")
    assert not results[0]["ok"] and results[0]["invented_ids"] == ["Video_Games::made_up"]
    assert logger.records == []  # never executed


def test_id_copied_from_the_request_is_executed(corpus):
    executor = PlanExecutor(ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": [VG_A]}})), [QueryTool(corpus)])
    results = executor.run(f"tell me about {VG_A}")
    assert results[0]["ok"] and results[0]["invented_ids"] == []


def test_reference_to_an_earlier_step_is_resolved(corpus):
    steps = [
        {"tool": "SQLTool", "args": {"limit": 2}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.candidates.*.item_id"}},
    ]
    results = PlanExecutor(ScriptedLLM(plan(*steps)), [SQLTool(corpus), QueryTool(corpus)]).run("show me items")
    assert [r["ok"] for r in results] == [True, True] and len(results[1]["data"]["items"]) == 2


def test_ask_user_gives_an_empty_plan_and_a_question(corpus):
    executor = PlanExecutor(ScriptedLLM(plan(ask_user="Which product type?")), [SQLTool(corpus)])
    assert executor.run("recommend something") == []
    assert executor.last_question == "Which product type?"
