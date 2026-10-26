"""End-to-end tests with fake tools (full pipeline: planner → executor → outcome → compose)."""

import json

from package.agents import PlanExecutor
from package.inference.outcome import outcome_from_plan_results
from package.inference.compose import compose_answer
from package.inference._dataclass import AgentOutcome
from tests.agents.fakes.fake_tools import (
    FakeItemCFTool,
    FakeRecoModelTool,
    FakeQueryTool,
    FakeSQLTool,
    FakeMemoryTool,
)
from tests.agents.fakes.scripted_llm import ScriptedLLM
from tests.agents.fakes.sample_data import (
    build_plan_json,
    build_item_cf_candidates,
    build_reco_ranked,
    build_items,
)


def test_successful_3_step_pipeline():
    """Success path: ItemCF → Reco → Query → status='ok' with ranked order."""
    # Setup fake tools with data
    item_cf = FakeItemCFTool(
        fixed_data={
            "candidates": build_item_cf_candidates("item1", "item2", "item3"),
            "unknown_items": [],
            "note": None,
        }
    )
    reco = FakeRecoModelTool(
        fixed_data={
            "ranked": build_reco_ranked("item2", "item1", "item3", score=0.9),
            "model": "fake",
            "cold_start": False,
            "excluded_seen": [],
            "unscored_item_ids": [],
            "has_personal_signal": True,
            "note": None,
        }
    )
    query = FakeQueryTool(
        fixed_data={
            "items": build_items("item2", "item1", "item3"),
            "missing_item_ids": [],
            "truncated": False,
        }
    )

    # Plan: ItemCF → Reco → Query
    plan = build_plan_json(
        {"tool": "ItemCFTool", "args": {"items": ["seed_item"], "top_k": 30}},
        {"tool": "RecoModelTool", "args": {"user_id": "user1", "candidates": "$1.candidates", "top_k": 5}},
        {"tool": "QueryTool", "args": {"item_ids": "$2.ranked.*.item_id"}},
    )

    llm = ScriptedLLM(plan)
    executor = PlanExecutor(llm, [item_cf, reco, query], reflect_rounds=0)
    results = executor.run("recommend similar items to seed_item for user1")

    # Check executor results
    assert len(results) == 3
    assert all(r["ok"] for r in results)

    # Convert to outcome
    outcome = outcome_from_plan_results("recommend similar items to seed_item for user1", results)
    assert outcome.items
    assert len(outcome.items) == 3
    # Order should be from RecoModelTool (ranked)
    assert [i["item_id"] for i in outcome.items] == ["item2", "item1", "item3"]

    # Compose answer
    llm_compose = ScriptedLLM(
        json.dumps({"answer": "Here are your recommendations", "mentioned_item_ids": ["item2", "item1", "item3"]}),
        # Add a second response in case of retry (though should not be needed)
        json.dumps({"answer": "Here are your recommendations", "mentioned_item_ids": ["item2", "item1", "item3"]})
    )
    answer = compose_answer(outcome, llm_compose, mode="llm")
    assert answer.status == "ok"
    # Accept either llm or template (template fallback can happen due to grounding checks)
    assert answer.composer in ["llm", "template"]


def test_personalization_path_with_known_user():
    """Personalization: Memory → SQL → Reco → Query with known=true."""
    memory = FakeMemoryTool(
        fixed_data={
            "user_id": "user1",
            "known": True,
            "n_interactions": 10,
            "top_categories": ["Video_Games", "Electronics"],
            "price_range": {"min": 10.0, "max": 100.0},
            "recent_items": ["item1", "item2"],
        }
    )
    sql = FakeSQLTool(
        fixed_data={
            "candidates": build_items("item3", "item4", "item5"),
            "total_matches": 3,
            "truncated": False,
            "applied_filters": {},
        }
    )
    reco = FakeRecoModelTool(
        fixed_data={
            "ranked": build_reco_ranked("item3", "item4", "item5", score=0.8),
            "model": "fake",
            "cold_start": False,
            "excluded_seen": [],
            "unscored_item_ids": [],
            "has_personal_signal": True,
            "note": None,
        }
    )
    query = FakeQueryTool(
        fixed_data={
            "items": build_items("item3", "item4", "item5"),
            "missing_item_ids": [],
            "truncated": False,
        }
    )

    # Plan: Memory → SQL → Reco → Query
    plan = build_plan_json(
        {"tool": "MemoryTool", "args": {"user_id": "user1"}},
        {"tool": "SQLTool", "args": {"filters": {"categories_any": "$1.top_categories", "price_max": "$1.price_range.max"}, "limit": 30}},
        {"tool": "RecoModelTool", "args": {"user_id": "user1", "candidates": "$2.candidates", "top_k": 5}},
        {"tool": "QueryTool", "args": {"item_ids": "$3.ranked.*.item_id"}},
    )

    llm = ScriptedLLM(plan)
    executor = PlanExecutor(llm, [memory, sql, reco, query], reflect_rounds=0)
    results = executor.run("personalized recommendations for user1")

    assert len(results) == 4
    assert all(r["ok"] for r in results)

    outcome = outcome_from_plan_results("personalized recommendations for user1", results)
    assert outcome.items
    assert len(outcome.items) == 3


def test_personalization_path_with_unknown_user_reflects():
    """Personalization with known=false (price_range=None) → reference fails → reflect → fixed plan."""
    # First attempt: Memory returns price_range=None, reference $1.price_range.max fails
    memory_unknown = FakeMemoryTool(
        fixed_data={
            "user_id": "user2",
            "known": False,
            "n_interactions": 0,
            "top_categories": [],
            "price_range": None,  # This will cause the reference to fail
            "recent_items": [],
        }
    )
    sql = FakeSQLTool(
        fixed_data={
            "candidates": build_items("item1", "item2"),
            "total_matches": 2,
            "truncated": False,
            "applied_filters": {},
        }
    )
    reco = FakeRecoModelTool(
        fixed_data={
            "ranked": build_reco_ranked("item1", "item2", score=0.7),
            "model": "fake",
            "cold_start": True,
            "excluded_seen": [],
            "unscored_item_ids": [],
            "has_personal_signal": False,
            "note": None,
        }
    )
    query = FakeQueryTool(
        fixed_data={
            "items": build_items("item1", "item2"),
            "missing_item_ids": [],
            "truncated": False,
        }
    )

    # Plan 1: tries to use $1.price_range.max (will fail)
    plan1 = build_plan_json(
        {"tool": "MemoryTool", "args": {"user_id": "user2"}},
        {"tool": "SQLTool", "args": {"filters": {"categories_any": "$1.top_categories", "price_max": "$1.price_range.max"}, "limit": 30}},
        {"tool": "RecoModelTool", "args": {"user_id": "user2", "candidates": "$2.candidates", "top_k": 5}},
        {"tool": "QueryTool", "args": {"item_ids": "$3.ranked.*.item_id"}},
    )

    # Plan 2: fixed, doesn't use the bad reference
    plan2 = build_plan_json(
        {"tool": "SQLTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 30}},
        {"tool": "RecoModelTool", "args": {"user_id": "user2", "candidates": "$1.candidates", "top_k": 5}},
        {"tool": "QueryTool", "args": {"item_ids": "$2.ranked.*.item_id"}},
    )

    llm = ScriptedLLM(plan1, plan2)
    executor = PlanExecutor(llm, [memory_unknown, sql, reco, query], reflect_rounds=1)
    results = executor.run("recommendations for unknown user2")

    # Should have reflected
    assert executor.last_reflections == 1
    assert executor.last_first_attempt_ok is False

    # Final result should be from plan 2
    assert len(results) == 3
    assert all(r["ok"] for r in results)

    outcome = outcome_from_plan_results("recommendations for unknown user2", results)
    assert outcome.items
    assert len(outcome.items) == 2
