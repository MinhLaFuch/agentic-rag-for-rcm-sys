"""Fake tools for testing and mock mode.

These tools copy schemas from real tools and add:
- delay_seconds: simulate latency
- fixed_error: always raise ToolInputError with this message
- raise_exception: raise this exception (for testing error handling)
"""

from __future__ import annotations

from typing import Any

from package.tools.base import Tool, ToolInputError
from package.corpus import ItemCorpus


class FakeFilterTool(Tool):
    """Fake FilterTool for testing."""

    name = "FilterTool"
    description = "Retrieve candidate items with structured filters."
    input_schema = {
        "filters": {
            "domain": "str | list[str]",
            "price_min": "float",
            "price_max": "float",
            "include_missing_price": "bool",
            "min_rating": "float",
            "min_rating_number": "int",
            "categories_any": "list[str]",
            "categories_all": "list[str]",
            "store": "str | list[str]",
            "title_contains": "str",
            "exclude_item_ids": "list[str]",
        },
        "order_by": "str",
        "descending": "bool",
        "limit": "int",
    }
    output_schema = {"candidates": "list", "total_matches": "int"}

    def __init__(
        self,
        delay_seconds: float = 0.0,
        fixed_error: str | None = None,
        raise_exception: type[Exception] | None = None,
    ):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.fixed_error = fixed_error
        self.raise_exception = raise_exception

    def execute(self, filters: dict[str, Any] | None = None, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.raise_exception:
            raise self.raise_exception("Simulated exception")
        if self.fixed_error:
            raise ToolInputError(self.fixed_error)
        return {
            "candidates": [
                {"item_id": f"item_{i}", "domain": "Video_Games", "title": f"Fake Item {i}"}
                for i in range(min(limit, 5))
            ],
            "total_matches": 5,
        }


class FakeSearchTool(Tool):
    """Fake SearchTool for testing."""

    name = "SearchTool"
    description = "Search items by keywords."
    input_schema = {
        "query": "str",
        "filters": {
            "domain": "str | list[str]",
            "price_min": "float",
            "price_max": "float",
            "include_missing_price": "bool",
            "min_rating": "float",
            "min_rating_number": "int",
            "categories_any": "list[str]",
            "categories_all": "list[str]",
            "store": "str | list[str]",
            "title_contains": "str",
            "exclude_item_ids": "list[str]",
        },
        "limit": "int",
    }
    output_schema = {"candidates": "list", "total_matches": "int"}

    def __init__(
        self,
        delay_seconds: float = 0.0,
        fixed_error: str | None = None,
        raise_exception: type[Exception] | None = None,
    ):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.fixed_error = fixed_error
        self.raise_exception = raise_exception

    def execute(self, query: str, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.raise_exception:
            raise self.raise_exception("Simulated exception")
        if self.fixed_error:
            raise ToolInputError(self.fixed_error)
        return {
            "candidates": [
                {"item_id": f"search_{i}", "domain": "Video_Games", "title": f"Search Result {i}", "score": 0.9 - i * 0.1}
                for i in range(min(limit, 5))
            ],
            "total_matches": 5,
        }


class FakeRankTool(Tool):
    """Fake RankTool for testing."""

    name = "RankTool"
    description = "Rank a candidate set for a user."
    input_schema = {"user_id": "str", "candidates": "list[str]", "top_k": "int"}
    output_schema = {"ranked": "list", "model": "str"}

    def __init__(
        self,
        delay_seconds: float = 0.0,
        fixed_error: str | None = None,
        raise_exception: type[Exception] | None = None,
    ):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.fixed_error = fixed_error
        self.raise_exception = raise_exception

    def execute(self, user_id: str, candidates: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.raise_exception:
            raise self.raise_exception("Simulated exception")
        if self.fixed_error:
            raise ToolInputError(self.fixed_error)
        return {
            "ranked": [
                {"rank": i + 1, "item_id": item_id, "score": 0.9 - i * 0.05}
                for i, item_id in enumerate(candidates[:top_k])
            ],
            "model": "fake_model",
        }


class FakeSimilarTool(Tool):
    """Fake SimilarTool for testing."""

    name = "SimilarTool"
    description = "Retrieve items similar to given item(s)."
    input_schema = {"items": "list[str]", "top_k": "int", "domain": "str | None", "exclude_input": "bool"}
    output_schema = {"candidates": "list", "unknown_items": "list", "note": "str | None"}

    def __init__(
        self,
        delay_seconds: float = 0.0,
        fixed_error: str | None = None,
        raise_exception: type[Exception] | None = None,
    ):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.fixed_error = fixed_error
        self.raise_exception = raise_exception

    def execute(self, items: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.raise_exception:
            raise self.raise_exception("Simulated exception")
        if self.fixed_error:
            raise ToolInputError(self.fixed_error)
        return {
            "candidates": [{"item_id": f"similar_{i}", "similarity": 0.8 - i * 0.1} for i in range(min(top_k, 5))],
            "unknown_items": [],
        }


class FakeLookupTool(Tool):
    """Fake LookupTool for testing."""

    name = "LookupTool"
    description = "SQL query tool for item details."
    input_schema = {"query": "str", "limit": "int"}
    output_schema = {"items": "list", "total_matches": "int"}

    def __init__(
        self,
        delay_seconds: float = 0.0,
        fixed_error: str | None = None,
        raise_exception: type[Exception] | None = None,
    ):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.fixed_error = fixed_error
        self.raise_exception = raise_exception

    def execute(self, query: str, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.raise_exception:
            raise self.raise_exception("Simulated exception")
        if self.fixed_error:
            raise ToolInputError(self.fixed_error)
        return {
            "items": [
                {"item_id": f"lookup_{i}", "domain": "Video_Games", "title": f"Lookup Result {i}"}
                for i in range(min(limit, 5))
            ],
            "total_matches": 5,
        }
