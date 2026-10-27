"""Fake tools for deterministic agent testing (contracts match real tools)."""

from typing import Any

from package.tools.base import Tool, ToolInputError, ToolResult
from package.tools.ranking import ItemCFTool, RecoModelTool
from package.tools.sql_query import QueryTool, SQLTool
from package.tools.retrieval import SemanticSearchTool
from package.memory.memory_tool import MemoryTool


class FakeItemCFTool(Tool):
    """Fake ItemCFTool with contract matching the real tool."""

    name = ItemCFTool.name
    description = ItemCFTool.description
    input_schema = ItemCFTool.input_schema
    output_schema = ItemCFTool.output_schema

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


class FakeRecoModelTool(Tool):
    """Fake RecoModelTool with contract matching the real tool."""

    name = RecoModelTool.name
    description = RecoModelTool.description
    input_schema = RecoModelTool.input_schema
    output_schema = RecoModelTool.output_schema

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


class FakeQueryTool(Tool):
    """Fake QueryTool with contract matching the real tool."""

    name = QueryTool.name
    description = QueryTool.description
    input_schema = QueryTool.input_schema
    output_schema = QueryTool.output_schema

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


class FakeSemanticSearchTool(Tool):
    """Fake SemanticSearchTool with contract matching the real tool."""

    name = SemanticSearchTool.name
    description = SemanticSearchTool.description
    input_schema = SemanticSearchTool.input_schema
    output_schema = SemanticSearchTool.output_schema

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


class FakeSQLTool(Tool):
    """Fake SQLTool with contract matching the real tool."""

    name = SQLTool.name
    description = SQLTool.description
    input_schema = SQLTool.input_schema
    output_schema = SQLTool.output_schema

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
