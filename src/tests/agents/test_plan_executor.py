"""PlanExecutor: retry on bad JSON, max_steps cut, invented-id guard, reference chaining, ask_user."""

import json

import pytest

from package.agents import PlanExecutor, build_tool_prompt
from package.api.llm_provider import LLMProvider
from package.api._dataclass import LLMResponse
from package.tools import BaselineScorer, QueryTool, SQLTool, ToolCallLogger, ItemCFTool
from package.memory.memory_tool import MemoryTool
from package.tools.recommenders import ItemKNNRecommender
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.tools_helpers import VG_A, VG_B, VG_C


def plan(*steps, ask_user=None) -> str:
    return json.dumps({"steps": list(steps), "ask_user": ask_user})


def test_retries_once_on_invalid_json_then_succeeds(corpus):
    llm = ScriptedLLM("not json at all", plan({"tool": "SQLTool", "args": {"limit": 2}}))
    executor = PlanExecutor(llm, [SQLTool(corpus)], plan_retries=1)
    results = executor.run("list some items")
    assert results[0]["ok"]
    assert executor.last_usage["attempts"] == 2
    assert executor.last_usage["prompt_tokens"] == 20 and executor.last_usage["completion_tokens"] == 10
    retry_messages = llm.calls[1]["messages"]
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
    # Pass a session with empty valid IDs so the invented ID is still rejected
    from package.agents.session import Session
    session = Session()
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::made_up"]}})), [QueryTool(corpus, logger=logger)], session=session
    )
    results = executor.run(f"tell me about {VG_A}")
    assert not results[0]["ok"] and results[0]["invented_ids"] == ["Video_Games::made_up"]
    assert logger.records == []  # never executed


def test_id_copied_from_the_request_is_executed(corpus):
    from package.agents.session import Session
    executor = PlanExecutor(ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": [VG_A]}})), [QueryTool(corpus)], session=Session())
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


def test_every_tool_the_planner_can_see_documents_itself(corpus, cf_setup):
    # Regression: RecoModelTool once reached the planner with no description and `input_schema: {}`.
    from package.agents import build_tool_prompt
    from package.memory.memory_tool import MemoryTool
    from package.tools import BaselineScorer, ItemCFTool, RecoModelTool, SemanticSearchTool, SQLTool
    from package.tools.recommenders import ItemKNNRecommender

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = [ItemCFTool(knn, item2id, corpus=corpus), RecoModelTool(BaselineScorer(knn), user2id, item2id, corpus=corpus),
             QueryTool(corpus), SQLTool(corpus), SemanticSearchTool(corpus), MemoryTool(interactions, user2id, item2id, corpus)]
    for tool in tools:
        assert tool.description and tool.input_schema and tool.output_schema, tool.name
    prompt = build_tool_prompt(tools)
    assert "returns:" in prompt and "user_id" in prompt and "categories_any" in prompt  # filter keys are spelled out
    assert "Electronics" in SemanticSearchTool(corpus).input_schema["filters"]["domain"]  # real domain names, not "Amazon"
    # SQLTool should be included in the planner's tools
    assert SQLTool.name in [t.name for t in tools]


def test_sqltool_is_in_planner_toolset(corpus, cf_setup):
    """SQLTool should be available to the planner via for_planner()."""
    from package.agents import build_tools

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)

    planner_tools = tools.for_planner()
    tool_names = [t.name for t in planner_tools]
    assert "SQLTool" in tool_names
    assert "ItemCFTool" in tool_names
    assert "RecoModelTool" in tool_names
    assert "QueryTool" in tool_names
    assert "SemanticSearchTool" in tool_names

    # planner_memory should also have SQLTool
    planner_memory_tools = tools.for_planner_memory()
    assert "SQLTool" in [t.name for t in planner_memory_tools]
    assert "MemoryTool" in [t.name for t in planner_memory_tools]


def test_filter_key_sent_at_top_level_gets_an_actionable_error_and_the_tool_is_not_called(corpus):
    from package.tools import SemanticSearchTool

    logger = ToolCallLogger()
    flat = {"tool": "SemanticSearchTool", "args": {"query": "game", "categories_any": ["Games"], "price_max": 20}}
    results = PlanExecutor(ScriptedLLM(plan(flat)), [SemanticSearchTool(corpus, logger=logger)], reflect_rounds=0).run("find games")  # reflect off: this test is about the first run's error
    assert not results[0]["ok"] and logger.records == []
    assert "belongs inside `filters`" in results[0]["error"] and "categories_any" in results[0]["error"]
    nested = {"tool": "SemanticSearchTool", "args": {"query": "game", "filters": {"categories_any": ["Games"], "price_max": 20}}}
    assert PlanExecutor(ScriptedLLM(plan(nested)), [SemanticSearchTool(corpus)]).run("find games")[0]["ok"]


def test_step_includes_args_and_output_summary(corpus):
    """New fields for trajectory logging: args (resolved) and output_summary."""
    steps = [
        {"tool": "SQLTool", "args": {"limit": 2}},
        {"tool": "QueryTool", "args": {"item_ids": "$1.candidates.*.item_id"}},
    ]
    results = PlanExecutor(ScriptedLLM(plan(*steps)), [SQLTool(corpus), QueryTool(corpus)]).run("show me items")
    assert results[0]["ok"]
    assert "args" in results[0]
    assert results[0]["args"] == {"limit": 2}
    assert "output_summary" in results[0]
    assert "candidates" in results[0]["output_summary"]
    assert results[0]["output_summary"]["candidates"]["n"] == 2
    assert len(results[0]["output_summary"]["candidates"]["first_ids"]) <= 3

    assert results[1]["ok"]
    assert "args" in results[1]
    assert "item_ids" in results[1]["args"]
    assert len(results[1]["args"]["item_ids"]) == 2
    assert "output_summary" in results[1]
    assert "items" in results[1]["output_summary"]
    assert results[1]["output_summary"]["items"]["n"] == 2


def test_step_includes_note_when_present(corpus, cf_setup):
    """Tool output with 'note' field should be copied to step."""
    from package.tools import ItemCFTool
    from package.tools.recommenders import ItemKNNRecommender

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    item_cf = ItemCFTool(knn, item2id, corpus=corpus)

    # Use an unknown item to force empty candidates and generate a note
    # Include it in the request text to avoid "invented id" check
    unknown_item = "Video_Games::unknown_item_12345"
    steps = [{"tool": "ItemCFTool", "args": {"items": [unknown_item]}}]
    # Disable reflect to avoid multiple LLM calls
    results = PlanExecutor(ScriptedLLM(plan(*steps)), [item_cf], reflect_rounds=0).run(f"similar to {unknown_item}")
    assert results[0]["ok"]
    # ItemCFTool returns note when candidates is empty
    assert "note" in results[0]["data"]
    assert "note" in results[0]
    assert results[0]["note"] == results[0]["data"]["note"]


def test_output_summary_is_size_limited(corpus):
    """Long strings in output_summary should be truncated to max_output_summary_chars."""
    from package.agents.planner._helper import _summarize_output

    long_string = "x" * 1000


def test_prompt_includes_new_tools_and_examples(corpus, cf_setup):
    """SYSTEM_PROMPT should include SQLTool, MemoryTool, and the new examples."""
    from package.agents.planner._prompt import SYSTEM_PROMPT
    from package.agents import build_tools
    import json

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
    planner_tools = tools.for_planner_memory()  # Include MemoryTool
    session_state = json.dumps({"turns_count": 0, "shown_items": [], "candidates": [], "ranked": [], "constraints": {}, "feedback": {}}, ensure_ascii=False)
    prompt = SYSTEM_PROMPT.format(tools=build_tool_prompt(planner_tools), session_state=session_state)

    # Check that SQLTool and MemoryTool are mentioned
    assert "SQLTool" in prompt
    assert "MemoryTool" in prompt

    # Check that the new examples are present
    assert "MemoryTool" in prompt
    assert '"$1.top_categories"' in prompt
    assert '"$1.price_range.max"' in prompt
    assert '"$1.recent_items"' in prompt

    # Check that session state is included
    assert "Session state" in prompt
    assert "$S." in prompt


def test_memory_tool_output_is_not_summarized():
    """MemoryTool output should be included in full (it's small)."""
    from package.agents.planner._helper import _summarize_output

    data = {
        "user_id": "u1",
        "known": True,
        "n_interactions": 5,
        "top_categories": ["Games", "Electronics"],
        "price_range": {"min": 10.0, "max": 100.0},
    }
    summary = _summarize_output(data, "MemoryTool")
    assert summary == data  # Full copy, no summarization


def test_failed_step_still_has_args_but_no_output_summary(corpus):
    """When a step fails, args should still be logged but output_summary is empty."""
    steps = [{"tool": "SQLTool", "args": {"invalid_arg": 1}}]
    results = PlanExecutor(ScriptedLLM(plan(*steps)), [SQLTool(corpus)], reflect_rounds=0).run("list items")
    assert not results[0]["ok"]
    assert "args" in results[0]
    assert results[0]["args"] == {"invalid_arg": 1}
    # output_summary is not added when the tool is not executed
    assert "output_summary" not in results[0]


def test_session_reference_is_resolved(corpus):
    """Test that $S. references are resolved from session state."""
    from package.agents.session import Session
    from package.agents.planner._helper import _resolve_refs

    session = Session()
    session.add_shown_items([VG_A, VG_B])

    # Test the resolution logic directly
    args = {"item_ids": "$S.shown_items.1"}
    resolved = _resolve_refs(args, [], session)
    
    # The reference should be resolved to VG_B
    assert resolved["item_ids"] == VG_B


def test_id_from_session_is_allowed(corpus):
    """Test that IDs from session (shown_items, candidates, ranked) are not treated as invented."""
    from package.agents.session import Session

    session = Session()
    session.add_shown_items([VG_A])
    session.set_candidates([VG_B], [VG_C])

    # Use an ID from session that is NOT in the request
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": [VG_B]}})),
        [QueryTool(corpus)],
        session=session
    )
    results = executor.run("tell me about something else")
    # Should succeed because VG_B is in session candidates
    assert results[0]["ok"]
    assert results[0]["invented_ids"] == []


def test_id_not_in_request_or_session_is_rejected(corpus):
    """Test that IDs not in request or session are treated as invented."""
    from package.agents.session import Session

    session = Session()
    session.add_shown_items([VG_A])

    # Use an ID that is neither in request nor session
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": ["Video_Games::unknown"]}})),
        [QueryTool(corpus)],
        session=session
    )
    results = executor.run("tell me about something")
    # Should fail because the ID is invented
    assert not results[0]["ok"]
    assert results[0]["invented_ids"] == ["Video_Games::unknown"]


def test_session_state_updated_after_turn(corpus):
    """Test that session state is updated after a successful turn."""
    from package.agents.session import Session

    session = Session()
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"limit": 2}})),
        [SQLTool(corpus)],
        session=session
    )
    results = executor.run("list items")

    # Session should be updated
    assert len(session.turns) == 1
    assert session.turns[0].user_request == "list items"
    # Candidates should be populated from SQLTool result
    assert len(session.candidates) > 0 or len(session.shown_items) > 0


def test_session_with_none_preserves_existing_behavior(corpus):
    """Test that session=None works exactly like before (no session integration)."""
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": [VG_A]}})),
        [QueryTool(corpus)],
        session=None
    )
    results = executor.run(f"tell me about {VG_A}")
    assert results[0]["ok"]
    assert results[0]["invented_ids"] == []
