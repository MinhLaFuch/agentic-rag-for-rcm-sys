"""Factory function for controlled mock tools."""

from typing import Any

from .controlled_filter_tool import ControlledFilterTool
from .controlled_similar_tool import ControlledSimilarTool
from package.tools.base import Tool


def get_controlled_tools(config: dict[str, Any] | None = None) -> list[Tool]:
    """Return controlled mock tools based on config."""
    config = config or {}
    return [
        ControlledFilterTool(
            should_fail=config.get("sql_fail", False),
            should_timeout=config.get("sql_timeout", False),
            should_return_empty=config.get("sql_empty", False),
        ),
        ControlledSimilarTool(
            should_fail=config.get("cf_fail", False),
            should_return_empty=config.get("cf_empty", False),
        ),
    ]