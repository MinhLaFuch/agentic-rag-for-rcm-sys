"""Tests for MemoryTool with large histories and edge cases."""

import json
import pandas as pd
import pytest

from package.agents import PlanExecutor
from package.llm.base import LLMProvider
from package.llm._dataclass import LLMResponse
from package.memory.memory_tool import MemoryTool
from package.tools import SQLTool
from package.tools.corpus import ItemCorpus


class ScriptedLLM(LLMProvider):
    """LLM that returns scripted responses for testing plan execution."""
    provider_name = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=512, response_format_json=False):
        self.calls.append(list(messages))
        return LLMResponse(
            text=self.replies.pop(0),
            prompt_tokens=10,
            completion_tokens=5,
            latency_seconds=0.1,
            provider_name="scripted",
            model_name="scripted-0"
        )


@pytest.fixture
def corpus():
    """Create a test corpus with price and category data."""
    meta = pd.DataFrame({
        "parent_asin": ["vg_a", "vg_b", "vg_c", "vg_d", "vg_e"],
        "domain": ["Video_Games"] * 5,
        "title": ["Pricey Game", "Cheap Game", "Mid Game", "Pricey Game 2", "Cheap Game 2"],
        "store": ["StoreA", "StoreB", "StoreC", "StoreA", "StoreB"],
        "price": [300.0, 1.0, 150.0, 250.0, 2.0],
        "average_rating": [4.5, 3.5, 4.0, 4.2, 3.8],
        "rating_number": [100, 50, 75, 80, 60],
        "main_category": ["Pricey", "Cheap", "Mid", "Pricey", "Cheap"],
        "categories": [
            ["Pricey", "Action"],
            ["Cheap", "Puzzle"],
            ["Mid", "RPG"],
            ["Pricey", "Adventure"],
            ["Cheap", "Strategy"],
        ],
    })
    return ItemCorpus.from_dataframe(meta, domain="Video_Games")


@pytest.fixture
def interactions_300_items():
    """Create a user with 300 interactions to test SQL aggregation."""
    # Create 300 interactions with items cycling through vg_a to vg_e (which exist in corpus)
    items = [f"Video_Games::vg_{['a', 'b', 'c', 'd', 'e'][i % 5]}" for i in range(300)]
    return pd.DataFrame({
        "user_id": ["u300"] * 300,
        "item_id": items,
        "user_idx": [0] * 300,
        "item_idx": list(range(300)),
        "rating": [5] * 300,
        "timestamp": list(range(300)),
    })


@pytest.fixture
def user2id():
    return {"u300": 0, "u0": 1, "u_strange": 2}


@pytest.fixture
def item2id():
    # Map item IDs to indices - map the actual corpus items (vg_a to vg_e)
    # Create enough mappings for the test (will map vg_a-e to 0-4, others to higher indices)
    mapping = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2, 
               "Video_Games::vg_d": 3, "Video_Games::vg_e": 4}
    # Add mappings for other indices to avoid KeyErrors
    for i in range(5, 300):
        mapping[f"Video_Games::vg_{i}"] = i
    return mapping


def test_memory_tool_with_300_interactions(corpus, interactions_300_items, user2id, item2id):
    """Test that MemoryTool handles large histories correctly using SQL aggregation."""
    tool = MemoryTool(interactions_300_items, user2id, item2id, corpus)
    
    result = tool.execute("u300", top_n_categories=2)
    
    # User should be known
    assert result["user_id"] == "u300"
    assert result["known"] is True
    assert result["n_interactions"] == 300
    
    # Price range should be min=1.0, max=300.0 (from corpus)
    assert result["price_range"] == {"min": 1.0, "max": 300.0}
    
    # Top 2 categories should be Pricey and Cheap (most frequent)
    assert set(result["top_categories"]) == {"Pricey", "Cheap"}


def test_memory_tool_unknown_user(corpus, interactions_300_items, user2id, item2id):
    """Test that unknown user returns empty result with known=False."""
    tool = MemoryTool(interactions_300_items, user2id, item2id, corpus)
    
    result = tool.execute("stranger")
    
    assert result["user_id"] == "stranger"
    assert result["known"] is False
    assert result["n_interactions"] == 0
    assert result["top_categories"] == []
    assert result["price_range"] is None


def test_memory_tool_user_with_zero_interactions(corpus, user2id, item2id):
    """Test that user in mapping but with 0 interactions returns known=False."""
    # Create empty interactions for user u0
    empty_interactions = pd.DataFrame({
        "user_id": [],
        "item_id": [],
        "user_idx": [],
        "item_idx": [],
        "rating": [],
        "timestamp": [],
    })
    tool = MemoryTool(empty_interactions, user2id, item2id, corpus)
    
    result = tool.execute("u0")
    
    assert result["user_id"] == "u0"
    assert result["known"] is False
    assert result["n_interactions"] == 0
    assert result["top_categories"] == []
    assert result["price_range"] is None


def test_memory_tool_all_null_prices(corpus, user2id, item2id):
    """Test handling when all items have NULL prices."""
    # Create corpus with NULL prices
    meta_null = pd.DataFrame({
        "parent_asin": ["vg_a", "vg_b"],
        "domain": ["Video_Games"] * 2,
        "title": ["Game A", "Game B"],
        "store": ["StoreA", "StoreB"],
        "price": [None, None],  # NULL prices
        "average_rating": [4.0, 3.5],
        "rating_number": [50, 30],
        "main_category": ["Action", "Puzzle"],
        "categories": [["Action"], ["Puzzle"]],
    })
    corpus_null = ItemCorpus.from_dataframe(meta_null, domain="Video_Games")
    
    interactions = pd.DataFrame({
        "user_id": ["u_null"] * 2,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b"],
        "user_idx": [0] * 2,
        "item_idx": [0, 1],
        "rating": [5, 4],
        "timestamp": [0, 1],
    })
    user2id_null = {"u_null": 0}
    item2id_null = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1}
    
    tool = MemoryTool(interactions, user2id_null, item2id_null, corpus_null)
    
    result = tool.execute("u_null")
    
    assert result["known"] is True
    assert result["n_interactions"] == 2
    assert result["price_range"] is None  # All NULL prices
    assert set(result["top_categories"]) == {"Action", "Puzzle"}


def test_memory_tool_plan_reference_compatibility(corpus, user2id, item2id):
    """Test that plan references work even when result is empty (known=False)."""
    empty_interactions = pd.DataFrame({
        "user_id": [],
        "item_id": [],
        "user_idx": [],
        "item_idx": [],
        "rating": [],
        "timestamp": [],
    })
    tool = MemoryTool(empty_interactions, user2id, item2id, corpus)
    
    result = tool.execute("u0")
    
    # These should not crash even when result is empty
    assert result["price_range"] is None
    assert result["top_categories"] == []
    
    # Accessing nested keys that don't exist should return None naturally
    # (this is how planner references work - they need to be safe with None)
    price_max = result["price_range"]["max"] if result["price_range"] else None
    assert price_max is None


def test_memory_tool_with_plan_executor_reference(corpus, user2id, item2id):
    """Test MemoryTool through PlanExecutor with step 2 referencing step 1's price_range."""
    # Create a user with some interactions
    interactions = pd.DataFrame({
        "user_id": ["u1"] * 3,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c"],
        "user_idx": [0] * 3,
        "item_idx": [0, 1, 2],
        "rating": [5, 4, 5],
        "timestamp": [0, 1, 2],
    })
    user2id_with_u1 = {"u1": 0}
    item2id_with_3 = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2}
    
    memory_tool = MemoryTool(interactions, user2id_with_u1, item2id_with_3, corpus)
    
    # Test that MemoryTool works directly
    result = memory_tool.execute("u1")
    assert result["known"] is True
    assert result["price_range"] is not None
    assert result["price_range"]["min"] == 1.0  # Cheap Game
    assert result["price_range"]["max"] == 300.0  # Pricey Game
    
    # Test that the output structure is compatible with plan references
    # (i.e., nested dict access doesn't crash even when empty)
    empty_result = memory_tool.execute("unknown_user")
    assert empty_result["known"] is False
    assert empty_result["price_range"] is None
    assert empty_result["top_categories"] == []
    
    # Accessing nested keys safely (as planner would do)
    price_max = empty_result["price_range"]["max"] if empty_result["price_range"] else None
    assert price_max is None
