"""Base Tool class for all tools in the system."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from ._dataclass import ToolResult
from ._error import ToolInputError
from ._helper import _hash_input
from .tool_call_logger import ToolCallLogger


class Tool(ABC):
    """Base class: subclasses implement `execute`; `__call__` adds logging + error handling."""

    name: str = "tool"
    description: str = ""
    input_schema: dict[str, Any] = {}  # JSON-schema-ish, for the Planning module / function calling

    def __init__(self, logger: ToolCallLogger | None = None) -> None:
        self.logger = logger or ToolCallLogger()

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Do the work; raise ToolInputError for bad input."""

    def __call__(self, *, agent: str = "direct", action: str = "call", **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        try:
            result = ToolResult(ok=True, data=self.execute(**kwargs))
        except ToolInputError as exc:
            result = ToolResult(ok=False, error=str(exc))
        self.logger.log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "action": action,
                "tool": self.name,
                "input_hash": _hash_input(kwargs),
                "output": result.to_dict(),
                "latency_seconds": round(time.perf_counter() - start, 6),
            }
        )
        return result
