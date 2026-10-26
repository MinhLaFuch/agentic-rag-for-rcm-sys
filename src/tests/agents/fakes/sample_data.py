"""Sample data builders for fake tools (contracts match real tool outputs)."""

import json
from typing import Any


def build_item_cf_candidates(*items: str, similarity: float = 0.9, domain: str = "Video_Games") -> list[dict[str, Any]]:
    """Build ItemCFTool candidates output."""
    return [{"item_id": item, "similarity": similarity, "domain": domain} for item in items]


def build_reco_ranked(*items: str, score: float = 0.8, domain: str = "Video_Games") -> list[dict[str, Any]]:
    """Build RecoModelTool ranked output."""
    return [{"rank": i + 1, "item_id": item, "score": score, "domain": domain} for i, item in enumerate(items)]


def build_items(*items: str, domain: str = "Video_Games", title: str = "Test Item", store: str = "TestStore", price: float = 99.99, average_rating: float = 4.5, rating_number: int = 100, main_category: str = "Test") -> list[dict[str, Any]]:
    """Build QueryTool/SQLTool/SemanticSearchTool items output."""
    return [
        {
            "item_id": item,
            "domain": domain,
            "title": title,
            "store": store,
            "price": price,
            "average_rating": average_rating,
            "rating_number": rating_number,
            "main_category": main_category,
        }
        for item in items
    ]


def build_memory_output(
    user_id: str = "user1",
    known: bool = True,
    n_interactions: int = 5,
    top_categories: list[str] | None = None,
    price_range: dict[str, float] | None = None,
    recent_items: list[str] | None = None,
) -> dict[str, Any]:
    """Build MemoryTool output."""
    return {
        "user_id": user_id,
        "known": known,
        "n_interactions": n_interactions,
        "top_categories": top_categories or [],
        "price_range": price_range,
        "recent_items": recent_items or [],
    }


def build_plan_json(*steps: dict[str, Any], ask_user: str | None = None) -> str:
    """Build plan JSON string for LLM responses."""
    plan = {"steps": list(steps)}
    if ask_user:
        plan["ask_user"] = ask_user
    return json.dumps(plan)
