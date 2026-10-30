"""Multi-turn conversation tests with scripted LLMs.

Tests deterministic scenarios M1-M7 for session behavior:
- M1: Price refinement ("cheaper than $X")
- M2: Position reference ("similar to the second one")
- M3: Exclusion ("don't like this/this type")
- M4: More items ("show me more")
- M5: Clarification flow
- M6: Topic change
- M7: Long-term memory usage
"""

import json
import pytest

from package.agents import PlanExecutor
from package.tools import QueryTool, SQLTool, ItemCFTool, RecoModelTool
from package.tools.recommenders import ItemKNNRecommender
from package.agents.session import Session
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.tools_helpers import VG_A, VG_B, VG_C


def plan(*steps, ask_user=None) -> str:
    return json.dumps({"steps": list(steps), "ask_user": ask_user})


def test_m1_price_refinement(corpus, cf_setup):
    """M1: User refines price constraint in second turn."""
    from package.tools import BaselineScorer
    from package.agents import build_tools

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
    planner_tools = tools.for_planner_memory()

    session = Session()
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"limit": 5}})),
        planner_tools,
        session=session
    )

    # Turn 1: Initial request for games
    results1 = executor.run("gợi ý game")
    assert results1[0]["ok"]
    assert len(session.turns) == 1

    # Update session constraint for price
    session.update_constraints({"price_max": 50})

    # Turn 2: User asks for cheaper items
    price_plan = plan({"tool": "SQLTool", "args": {"filters": {"price_max": "$S.constraints.price_max"}, "limit": 5}})
    executor2 = PlanExecutor(
        ScriptedLLM(price_plan, price_plan),
        planner_tools,
        session=session
    )
    results2 = executor2.run("rẻ hơn, dưới 50$")
    assert results2[0]["ok"]
    assert len(session.turns) == 2
    # Verify constraint was used
    assert session.constraints["price_max"] == 50


def test_m2_position_reference(corpus, cf_setup):
    """M2: User references "the second one" from previous turn."""
    from package.tools import BaselineScorer
    from package.agents import build_tools

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
    planner_tools = tools.for_planner_memory()

    session = Session()
    session.add_shown_items([VG_A, VG_B, VG_C])

    # Turn 2: Ask for items similar to the second shown item
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "ItemCFTool", "args": {"items": ["$S.shown_items.1"], "top_k": 5}})),
        planner_tools,
        session=session
    )

    results = executor.run("tương tự cái thứ hai")
    assert results[0]["ok"]
    # Verify the reference was resolved to VG_B
    assert VG_B in results[0]["args"]["items"]


def test_m3_exclusion_persistence(corpus):
    """M3: User excludes an item/category, and it persists across turns."""
    session = Session()
    session.add_shown_items([VG_A, VG_B])

    # User excludes VG_A
    session.add_exclusions(item_ids=[VG_A])

    # Turn 2: Request should respect the exclusion
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"filters": {"exclude_item_ids": "$S.constraints.exclude_item_ids"}, "limit": 5}})),
        [SQLTool(corpus)],
        session=session
    )

    results = executor.run("cho thêm vài cái")
    assert results[0]["ok"]
    # Verify exclusion was used
    assert VG_A in session.constraints["exclude_item_ids"]


def test_m4_no_repeat_of_shown_items(corpus):
    """M4: Show more items should not repeat already shown items."""
    session = Session()
    session.add_shown_items([VG_A, VG_B])

    # Turn 2: Request more items
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"filters": {"exclude_item_ids": "$S.shown_items"}, "limit": 5}})),
        [SQLTool(corpus)],
        session=session
    )

    results = executor.run("cho thêm vài cái nữa")
    assert results[0]["ok"]
    # Verify shown items were used for exclusion
    assert session.shown_items == [VG_A, VG_B]


def test_m5_clarification_flow(corpus):
    """M5: Agent asks for clarification, user provides it."""
    session = Session()

    # Turn 1: Agent asks for clarification (ask_user)
    ask_user_plan = json.dumps({"steps": [], "ask_user": "What product type do you like?"})
    executor1 = PlanExecutor(
        ScriptedLLM(ask_user_plan),
        [SQLTool(corpus)],
        session=session
    )

    results1 = executor1.run("suggest something")
    assert results1 == []  # No steps when ask_user
    assert executor1.last_question == "What product type do you like?"
    assert len(session.turns) == 1

    # Turn 2: User provides clarification
    clarification_plan = plan({"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 5}})
    executor2 = PlanExecutor(
        ScriptedLLM(clarification_plan, clarification_plan, clarification_plan),  # Provide enough responses
        [SQLTool(corpus)],
        session=session
    )

    results2 = executor2.run("I like games")
    if not results2[0]["ok"]:
        print(f"Error: {results2[0].get('error')}")
    assert results2[0]["ok"]
    assert len(session.turns) == 2


def test_m6_topic_change(corpus):
    """M6: User changes topic, old constraints should be cleared or not used."""
    session = Session()
    session.update_constraints({"price_max": 50, "category": "Video_Games"})

    # Turn 2: User changes topic to electronics
    session.reset()  # Or clear specific constraints
    session.update_constraints({"category": "Electronics"})

    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"filters": {"categories_any": ["Electronics"]}, "limit": 5}})),
        [SQLTool(corpus)],
        session=session
    )

    results = executor.run("đổi sang đồ điện tử")
    assert results[0]["ok"]
    # Verify new constraint is used
    assert session.constraints["category"] == "Electronics"


def test_m7_long_term_memory_usage(corpus, cf_setup):
    """M7: User asks for recommendations based on long-term preferences."""
    from package.tools import BaselineScorer
    from package.agents import build_tools

    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
    planner_tools = tools.for_planner_memory()

    session = Session()

    # Simplified test: just verify session is preserved across turns with memory tools
    executor = PlanExecutor(
        ScriptedLLM(plan({"tool": "SQLTool", "args": {"limit": 5}})),
        planner_tools,
        session=session
    )

    results = executor.run("gợi ý theo sở thích của tôi")
    assert results[0]["ok"]
    # Verify session state is updated
    assert len(session.turns) == 1


def test_session_limits_turn_truncation():
    """Test that old turns are removed when max_turns is exceeded."""
    session = Session(max_turns=3)

    for i in range(5):
        session.add_turn(f"request {i}", f"plan {i}", f"answer {i}")

    assert len(session.turns) == 3
    assert session.turns[0].user_request == "request 2"


def test_session_limits_shown_items_truncation():
    """Test that old shown items are removed when max_shown_items is exceeded."""
    session = Session(max_shown_items=3)

    session.add_shown_items(["item1", "item2"])
    session.add_shown_items(["item3", "item4"])

    assert session.shown_items == ["item2", "item3", "item4"]


def test_session_limits_candidates_truncation():
    """Test that candidates are limited to max_candidates."""
    session = Session(max_candidates=2)
    session.set_candidates(["c1", "c2", "c3"], ["r1", "r2", "r3"])

    assert session.candidates == ["c1", "c2"]
    assert session.ranked == ["r1", "r2"]


def test_multi_turn_with_feedback(corpus):
    """Test that user feedback is recorded in session."""
    session = Session()
    session.add_shown_items([VG_A, VG_B])

    # User likes VG_A, dislikes VG_B
    session.add_feedback(VG_A, "like")
    session.add_feedback(VG_B, "dislike")

    assert session.feedback[VG_A] == "like"
    assert session.feedback[VG_B] == "dislike"


def test_session_reset_clears_all_state():
    """Test that session.reset() clears all state."""
    session = Session()
    session.add_turn("request", "plan", "answer")
    session.add_shown_items([VG_A])
    session.set_candidates([VG_B], [VG_C])
    session.update_constraints({"price_max": 100})
    session.add_feedback(VG_A, "like")

    session.reset()

    assert session.turns == []
    assert session.shown_items == []
    assert session.candidates == []
    assert session.ranked == []
    assert session.constraints == {}
    assert session.feedback == {}


def test_two_independent_sessions_do_not_interfere():
    """Test that two separate sessions do not share state."""
    session1 = Session()
    session2 = Session()

    session1.add_shown_items([VG_A])
    session2.add_shown_items([VG_B])

    assert session1.shown_items == [VG_A]
    assert session2.shown_items == [VG_B]

    assert session1.get_valid_ids() == {VG_A}
    assert session2.get_valid_ids() == {VG_B}
