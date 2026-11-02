"""Fake tools for deterministic agent testing (contracts match real tools)."""

from typing import Any

from package.tools.base import Tool, ToolInputError, ToolResult
from package.tools.ranking import SimilarTool, RankTool
from package.tools.sql_query import LookupTool, FilterTool
from package.tools.retrieval import SearchTool
from package.memory.memory_tool import MemoryTool


class FakeSimilarTool(Tool):
    """Fake SimilarTool with contract matching the real tool."""

    name = SimilarTool.name
    description = SimilarTool.description
    input_schema = SimilarTool.input_schema
    output_schema = SimilarTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"candidates": [], "unknown_items": [], "note": "fake tool no data"}


class FakeRankTool(Tool):
    """Fake RankTool with contract matching the real tool."""

    name = RankTool.name
    description = RankTool.description
    input_schema = RankTool.input_schema
    output_schema = RankTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"ranked": [], "model": "fake", "cold_start": True, "excluded_seen": [], "unscored_item_ids": [], "has_personal_signal": False, "note": "fake tool no data"}


class FakeLookupTool(Tool):
    """Fake LookupTool with contract matching the real tool."""

    name = LookupTool.name
    description = LookupTool.description
    input_schema = LookupTool.input_schema
    output_schema = LookupTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"items": [], "missing_item_ids": [], "truncated": False}


class FakeSearchTool(Tool):
    """Fake SearchTool with contract matching the real tool."""

    name = SearchTool.name
    description = SearchTool.description
    input_schema = SearchTool.input_schema
    output_schema = SearchTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"candidates": [], "total_matches": 0, "query_tokens": [], "truncated": False, "applied_filters": {}}


class FakeFilterTool(Tool):
    """Fake FilterTool with contract matching the real tool."""

    name = FilterTool.name
    description = FilterTool.description
    input_schema = FilterTool.input_schema
    output_schema = FilterTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"candidates": [], "total_matches": 0, "truncated": False, "applied_filters": {}}


class FakeMemoryTool(Tool):
    """Fake MemoryTool with contract matching the real tool."""

    name = MemoryTool.name
    description = MemoryTool.description
    input_schema = MemoryTool.input_schema
    output_schema = MemoryTool.output_schema

    def __init__(
        self,
        *,
        fixed_data: dict[str, Any] | None = None,
        fixed_error: str | None = None,
        raise_exception: Exception | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._fixed_data = fixed_data
        self._fixed_error = fixed_error
        self._raise_exception = raise_exception
        self._call_counter = call_counter or [0]
        self._last_args: dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._call_counter[0] += 1
        self._last_args = kwargs
        if self._raise_exception:
            raise self._raise_exception
        if self._fixed_error:
            raise ToolInputError(self._fixed_error)
        if self._fixed_data is not None:
            return self._fixed_data
        return {"user_id": "unknown", "known": False, "n_interactions": 0, "top_categories": [], "price_range": None, "recent_items": []}
