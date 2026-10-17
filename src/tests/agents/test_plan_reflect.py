"""plan-reflect: after a plan runs with failed steps (or no items), PlanExecutor asks the LLM for a corrected plan once more."""

import pytest

from package.agents import PlanExecutor
from package.agents import _limits
from package.config.load_config import ConfigError
from package.tools import QueryTool, SQLTool
from package.tools.base import Tool
from package.tools.corpus import _error as corpus_error
from tests.agents.test_plan_executor import ScriptedLLM, plan
from tests.tools_helpers import VG_A

GOOD = {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 2}}
BAD_ARG = {"tool": "SQLTool", "args": {"category": "Games", "limit": 2}}  # filter key outside `filters`
BAD_REF = {"tool": "QueryTool", "args": {"item_ids": "$1.summary"}}  # $1.summary does not exist
NO_ITEMS = {"tool": "SQLTool", "args": {"filters": {"title_contains": "zzz-no-such-title"}}}


class TimeoutTool(Tool):
    name = "SlowTool"
    description = "always exceeds the SQL time budget"
    input_schema = {"q": "str"}
    output_schema = {"candidates": "list"}

    def execute(self, **kwargs):
        raise corpus_error.SQLTimeOutError("query exceeded the time budget")


def make(corpus, llm, **kw):
    return PlanExecutor(llm, [SQLTool(corpus), QueryTool(corpus), TimeoutTool()], reflect_rounds=kw.pop("reflect_rounds", 1), **kw)


def test_failed_step_is_reflected_and_the_fixed_plan_wins(corpus):
    llm = ScriptedLLM(plan(BAD_ARG), plan(GOOD))
    ex = make(corpus, llm)
    results = ex.run("find games")
    assert [r["ok"] for r in results] == [True]
    assert ex.last_reflections == 1 and ex.last_first_attempt_ok is False
    assert len(llm.calls) == 2
    notice = llm.calls[1][-1]
    assert notice.role == "user" and "unknown arg" in notice.content and "SQLTool" in notice.content
    assert llm.calls[1][-2].role == "assistant"  # the old plan is replayed as the assistant turn
    assert ex.last_plan == [GOOD] and ex.last_attempt_plans == [[BAD_ARG], [GOOD]]


def test_broken_reference_is_reflected(corpus):
    llm = ScriptedLLM(plan(GOOD, BAD_REF), plan(GOOD, {"tool": "QueryTool", "args": {"item_ids": "$1.candidates.*.item_id"}}))
    ex = make(corpus, llm)
    assert all(r["ok"] for r in ex.run("find games"))
    assert ex.last_reflections == 1
    assert "summary" in llm.calls[1][-1].content


def test_notice_lists_keys_of_ok_steps_not_their_data(corpus):
    llm = ScriptedLLM(plan(GOOD, BAD_REF), plan(GOOD))
    make(corpus, llm).run("find games")
    notice = llm.calls[1][-1].content
    assert "candidates" in notice and "total_matches" in notice
    assert "Video_Games::" not in notice  # no item data leaks into the notice


def test_first_attempt_ok_means_no_second_llm_call(corpus):
    llm = ScriptedLLM(plan(GOOD))
    ex = make(corpus, llm)
    assert ex.run("find games")[0]["ok"]
    assert len(llm.calls) == 1 and ex.last_reflections == 0 and ex.last_first_attempt_ok is True
    assert ex.last_attempt_plans == [[GOOD]]


def test_reflect_rounds_zero_keeps_the_old_behaviour(corpus):
    llm = ScriptedLLM(plan(BAD_ARG))
    ex = make(corpus, llm, reflect_rounds=0)
    results = ex.run("find games")
    assert not results[0]["ok"] and len(llm.calls) == 1
    assert ex.last_reflections == 0 and ex.last_first_attempt_ok is False


def test_stops_at_reflect_rounds_and_returns_the_last_attempt(corpus):
    llm = ScriptedLLM(plan(BAD_ARG), plan(BAD_REF), plan(GOOD))  # the third reply must never be requested
    ex = make(corpus, llm, reflect_rounds=1)
    results = ex.run("find games")
    assert len(llm.calls) == 2 and ex.last_reflections == 1
    assert not results[0]["ok"] and ex.last_plan == [BAD_REF]


def test_two_rounds_accumulate_the_conversation(corpus):
    llm = ScriptedLLM(plan(BAD_ARG), plan(BAD_REF), plan(GOOD))
    ex = make(corpus, llm, reflect_rounds=2)
    assert ex.run("find games")[0]["ok"] and ex.last_reflections == 2 and len(llm.calls) == 3
    assert [m.role for m in llm.calls[2]] == ["system", "user", "assistant", "user", "assistant", "user"]


def test_non_json_reflect_reply_keeps_the_previous_result(corpus):
    llm = ScriptedLLM(plan(GOOD, BAD_ARG), "sorry, I cannot")
    ex = make(corpus, llm)
    results = ex.run("find games")  # must not raise
    assert [r["ok"] for r in results] == [True, False]
    assert ex.last_plan == [GOOD, BAD_ARG] and ex.last_first_attempt_ok is False
    assert len(llm.calls) == 2  # no JSON retry inside reflect


def test_invented_ids_are_never_reflected(corpus):
    llm = ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::made_up"]}}), plan(GOOD))
    ex = make(corpus, llm)
    results = ex.run(f"tell me about {VG_A}")
    assert results[0]["invented_ids"] and len(llm.calls) == 1 and ex.last_reflections == 0
    assert ex.last_first_attempt_ok is False


def test_ask_user_is_never_reflected(corpus):
    llm = ScriptedLLM(plan(ask_user="Which product type?"), plan(GOOD))
    ex = make(corpus, llm)
    assert ex.run("recommend something") == []
    assert len(llm.calls) == 1 and ex.last_reflections == 0 and ex.last_first_attempt_ok is True


def test_time_budget_error_is_never_reflected(corpus):
    llm = ScriptedLLM(plan({"tool": "SlowTool", "args": {"q": "x"}}), plan(GOOD))
    ex = make(corpus, llm)
    results = ex.run("find games")
    assert not results[0]["ok"] and "time budget" in results[0]["error"]
    assert len(llm.calls) == 1 and ex.last_reflections == 0


def test_ok_plan_without_any_item_is_reflected(corpus):
    llm = ScriptedLLM(plan(NO_ITEMS), plan(GOOD))
    ex = make(corpus, llm)
    results = ex.run("find games")
    assert results[0]["ok"] and results[0]["data"]["candidates"]
    assert ex.last_reflections == 1 and ex.last_first_attempt_ok is False
    assert "no step returned any item" in llm.calls[1][-1].content


def test_usage_sums_both_calls(corpus):
    ex = make(corpus, ScriptedLLM(plan(BAD_ARG), plan(GOOD)))
    ex.run("find games")
    u = ex.last_usage
    assert u["attempts"] == 2 and u["prompt_tokens"] == 20 and u["completion_tokens"] == 10
    assert u["latency_seconds"] == pytest.approx(0.2)


def test_reflected_plan_is_cut_to_max_steps(corpus):
    llm = ScriptedLLM(plan(BAD_ARG), plan(GOOD, GOOD, GOOD))
    ex = make(corpus, llm, max_steps=2)
    assert len(ex.run("find games")) == 2 and ex.last_truncated


def test_state_is_reset_between_requests(corpus):
    ex = make(corpus, ScriptedLLM(plan(BAD_ARG), plan(GOOD), plan(GOOD)))
    ex.run("one")
    ex.run("two")
    assert ex.last_reflections == 0 and ex.last_first_attempt_ok is True and ex.last_attempt_plans == [[GOOD]]


def test_reflect_rounds_default_comes_from_yaml(corpus):
    assert PlanExecutor(ScriptedLLM(), [SQLTool(corpus)]).reflect_rounds == _limits.get_agent_limits().reflect_rounds


def test_negative_reflect_rounds_is_a_config_error(monkeypatch):
    from package.config import load_config

    cfg = load_config("agent/agent")
    cfg["agent"]["reflect_rounds"] = -1
    monkeypatch.setattr(_limits, "load_config", lambda name: cfg)
    _limits.get_agent_limits.cache_clear()
    try:
        with pytest.raises(ConfigError):
            _limits.get_agent_limits()
    finally:
        _limits.get_agent_limits.cache_clear()


def test_reflect_error_chars_comes_from_yaml_and_must_be_positive(monkeypatch):
    from package.config import load_config

    assert _limits.get_agent_limits().reflect_error_chars == load_config("agent/agent")["agent"]["reflect_error_chars"]
    cfg = load_config("agent/agent")
    cfg["agent"]["reflect_error_chars"] = 0
    monkeypatch.setattr(_limits, "load_config", lambda name: cfg)
    _limits.get_agent_limits.cache_clear()
    try:
        with pytest.raises(ConfigError):
            _limits.get_agent_limits()
    finally:
        _limits.get_agent_limits.cache_clear()


def test_provider_error_during_reflect_keeps_the_previous_result(corpus):
    from package.api import LLMProviderError

    class FailsSecondCall(ScriptedLLM):
        def complete(self, messages, **kw):
            if self.calls:
                raise LLMProviderError("endpoint down")
            return super().complete(messages, **kw)

    ex = make(corpus, FailsSecondCall(plan(GOOD, BAD_ARG)))
    results = ex.run("find games")  # must not raise: the first run's results are not lost
    assert [r["ok"] for r in results] == [True, False] and ex.last_reflections == 1
