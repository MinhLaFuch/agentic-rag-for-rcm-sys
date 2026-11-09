"""Intent search path tests — adapted from tools-building-2 for the TB layout.

The intent path is OPT-IN via ``demo.intent_path_enabled`` (default false), so
backend-level tests enable it explicitly; ``recommend_from_intent`` unit tests
need no flag.
"""
from unittest.mock import MagicMock

import pytest

from package.agents.type1.recommend_from_intent import recommend_from_intent
from package.demo import DemoRequest, LiveBackend
from package.tools import SearchTool, LookupTool
from tests.tools.conftest import world


@pytest.fixture
def tools(world):
    return SearchTool(world.corpus), LookupTool(world.corpus)


@pytest.fixture
def intent_enabled(monkeypatch):
    """Enable the intent path through the REAL config gate (not by patching the gate itself)."""
    from package.demo.backend import live_backend as module
    real_load_config = module.load_config

    def fake_load_config(key, *args, **kwargs):
        if key == "agent/demo":
            return {"demo": {"intent_path_enabled": True}}
        return real_load_config(key, *args, **kwargs)

    monkeypatch.setattr(module, "load_config", fake_load_config)


def test_actual_search_filters_and_metadata(tools):
    search, query = tools
    out = recommend_from_intent(search, query, "keyboard", filters={"domain": "Games", "price_max": 50})
    assert out["status"] == "ok"
    assert [r["item_id"] for r in out["items"]] == ["Games::A1"]
    assert out["items"][0]["price"] == 49.99
    assert [s["tool"] for s in out["steps"]] == ["SearchTool", "LookupTool"]
    assert all(s["ok"] for s in out["steps"])


def test_no_relaxation_when_budget_excludes_matches(tools):
    out = recommend_from_intent(*tools, "keyboard", filters={"price_max": 49})
    assert out["status"] == "no_result" and not out["items"]
    assert len(out["steps"]) == 1


def test_seen_items_and_existing_exclusions_are_combined_without_mutation(tools):
    filters = {"exclude_item_ids": ["Games::C3"]}
    out = recommend_from_intent(*tools, "keyboard", filters=filters, seen_items=["Games::A1"])
    assert out["status"] == "no_result"
    assert filters == {"exclude_item_ids": ["Games::C3"]}


@pytest.mark.parametrize("query", [None, "", "   ", "keyboard under 50", "keyboard $50", "keyboard 50 USD", "keyboard at most 50", "keyboard up to 50"])
def test_incomplete_or_embedded_price_asks_before_any_tool(query):
    search, fetch = MagicMock(), MagicMock()
    out = recommend_from_intent(search, fetch, query)
    assert out["status"] == "ask_user" and out["question"]
    search.assert_not_called(); fetch.assert_not_called()


@pytest.mark.parametrize("filters", [{"domain": "does-not-exist"}, {"price_max": -1}, {"price_min": 50, "price_max": 20}, {"price_max": float("nan")}, {"price_max": True}])
def test_invalid_filters_fail_without_unconstrained_fallback(tools, filters):
    out = recommend_from_intent(*tools, "keyboard", filters=filters)
    assert out["status"] == "tool_error" and out["error"] and not out["items"]


@pytest.mark.parametrize("k", [0, True, 101])
def test_invalid_result_budget_is_reported_before_tools(k):
    search, fetch = MagicMock(), MagicMock()
    out = recommend_from_intent(search, fetch, "keyboard", top_k=k)
    assert out["status"] == "tool_error"
    search.assert_not_called(); fetch.assert_not_called()


def test_fetch_failure_is_visible_and_no_ungrounded_items(tools):
    search, _ = tools
    fetch = MagicMock(name="fetch")
    fetch.name = "LookupTool"
    fetch.side_effect = TimeoutError("fixture deadline")
    out = recommend_from_intent(search, fetch, "keyboard")
    assert out["status"] == "tool_error" and not out["items"]
    assert "TimeoutError" in out["error"]
    assert out["steps"][-1]["ok"] is False
    assert fetch.call_count == 1


def test_incomplete_metadata_fails_closed(tools):
    search, _ = tools
    fetch = MagicMock(); fetch.name = "LookupTool"
    fetch.return_value.ok = True; fetch.return_value.data = {"items": []}
    out = recommend_from_intent(search, fetch, "keyboard")
    assert out["status"] == "tool_error" and out["steps"][-1]["ok"] is False


def test_demo_no_history_user_can_search_without_llm(world, tools, monkeypatch, intent_enabled):
    from package.demo.backend import live_backend as module
    factory = MagicMock(side_effect=AssertionError("must not call LLM"))
    monkeypatch.setattr(module, "build_llm_provider", factory)
    b = LiveBackend(); b._initialized = True; b._fit_df = world.interactions.assign(timestamp=1)
    b._user_id_to_internal_id = world.user2id; b._internal_id_to_item_id = {v: k for k, v in world.item2id.items()}
    b._intent_search, b._intent_query = tools; b._type1_agent = MagicMock()
    request = DemoRequest("new-account", "", 0, False, "type1", intent_query="keyboard", intent_filters={"price_max": 50})
    out = b.respond(request)
    assert out.status == "ok" and out.items[0].item_id == "Games::A1"
    assert out.recommendation_source == "intent_bm25"
    assert not out.usage and len(out.trace.steps) == 2
    b._type1_agent.recommend.assert_not_called(); factory.assert_not_called()


def test_cold_free_text_is_not_silently_treated_as_keywords(world, intent_enabled):
    b = LiveBackend(); b._initialized = True; b._fit_df = world.interactions
    b._type1_agent = MagicMock()
    out = b.respond(DemoRequest(None, "gợi ý sản phẩm dưới 500 nghìn", 0, False, "type1"))
    assert out.status == "ask_user" and not out.items and out.trace.ask_user
    b._type1_agent.recommend.assert_not_called()


def test_existing_user_explicit_intent_excludes_seen(world, tools, intent_enabled):
    b = LiveBackend(); b._initialized = True; b._fit_df = world.interactions
    b._type1_agent = MagicMock(); b._user_id_to_internal_id = world.user2id
    b._internal_id_to_item_id = {v: k for k, v in world.item2id.items()}
    b._intent_search, b._intent_query = tools
    out = b.respond(DemoRequest("u1", "", 0, False, "type1", intent_query="keyboard"))
    assert out.status == "no_result" and not out.items
    b._type1_agent.recommend.assert_not_called()


def test_known_user_without_cf_candidates_is_asked_for_intent(world, intent_enabled):
    b = LiveBackend(); b._initialized = True; b._fit_df = world.interactions.assign(timestamp=1)
    b._user_id_to_internal_id = world.user2id
    b._internal_id_to_item_id = {v: k for k, v in world.item2id.items()}
    b._type1_agent = MagicMock()
    b._type1_agent.recommend.return_value = {"ok": False, "stage": "retrieve", "error": "no candidates returned"}
    out = b.respond(DemoRequest("u1", "recommend", 0, False, "type1"))
    assert out.status == "ask_user" and out.error is None and not out.items


def test_planner_structured_fields_are_not_silently_ignored():
    b = LiveBackend(); b.initialize = MagicMock(side_effect=AssertionError("must validate before initialization"))
    out = b.respond(DemoRequest(None, "recommend", 0, False, "planner", intent_query="keyboard"))
    assert out.status == "ask_user"
    b.initialize.assert_not_called()


def test_intent_path_disabled_by_default(world, tools):
    """Default yaml keeps legacy behavior: intent fields -> ask_user, empty history -> no_result."""
    b = LiveBackend(); b._initialized = True; b._fit_df = world.interactions.assign(timestamp=1)
    b._user_id_to_internal_id = world.user2id
    b._internal_id_to_item_id = {v: k for k, v in world.item2id.items()}
    b._intent_search, b._intent_query = tools; b._type1_agent = MagicMock()
    out = b.respond(DemoRequest("new-account", "", 0, False, "type1", intent_query="keyboard"))
    assert out.status == "ask_user" and "intent_path_enabled" in out.text
    out2 = b.respond(DemoRequest("u0", "recommend", 0, False, "type1"))
    assert out2.status in ("no_result", "tool_error")  # u0 has no history -> legacy no_result path needs user found
    b._type1_agent.recommend.assert_not_called()
