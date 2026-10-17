"""Builders shared by the tests/inference suites (items, outcomes, scripted LLMs)."""

from __future__ import annotations

import json
from typing import Any

from package.api._error import LLMProviderError
from package.api.llm_provider import LLMProvider
from package.inference import AgentOutcome
from tests.agents.test_plan_executor import ScriptedLLM

__all__ = ["FailingLLM", "ScriptedLLM", "good_reply", "item", "outcome", "reply"]


class FailingLLM(LLMProvider):
    provider_name = "failing"

    def __init__(self) -> None:
        self.calls: list[list] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=512, response_format_json=False):
        self.calls.append(list(messages))
        raise LLMProviderError("endpoint down: " + "x" * 1000)


def item(item_id: str, title: str | None = "Some Title", price: float | None = 9.99, rating: float | None = 4.5,
         store: str | None = "Acme", rating_number: float | None = 100, domain: str | None = None) -> dict[str, Any]:
    return {
        "item_id": item_id, "domain": domain or item_id.split("::")[0], "title": title, "store": store, "price": price,
        "average_rating": rating, "rating_number": rating_number, "main_category": None,
    }


def outcome(items: list[dict[str, Any]] | None = None, **kw: Any) -> AgentOutcome:
    base: dict[str, Any] = dict(request_text="recommend something", items=items or [], question=None, errors=[],
                                invented_ids=[], cold_start=None, n_steps=1)
    base.update(kw)
    return AgentOutcome(**base)


def reply(answer: str, ids: list[str]) -> str:
    return json.dumps({"answer": answer, "mentioned_item_ids": ids}, ensure_ascii=False)


def good_reply(items: list[dict[str, Any]]) -> str:
    """A reply that satisfies every grounding rule for `items` (ids in order, only data from the items)."""
    lines = [f"{n}. {it['title']} ({it['item_id']})" for n, it in enumerate(items, 1)]
    return reply("\n".join(lines), [it["item_id"] for it in items])
