"""Base Tool class for all tools in the system."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from ._dataclass import ToolResult
from ._error import ToolInputError
from ._helper import _hash_input, _simplify_args
from .tool_call_logger import ToolCallLogger


class Tool(ABC):
    """Base class: subclasses implement `execute`; `__call__` adds logging + error handling."""

    name: str = "tool"
    description: str = ""
    input_schema: dict[str, Any] = {}  # JSON-schema-ish, for the Planning module / function calling
    output_schema: dict[str, Any] = {}  # top-level keys of the result data: the only paths a "$N.path" reference may use

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Enforce that Tool subclasses declare required class attributes."""
        super().__init_subclass__(**kwargs)
        # Check that required attributes are declared (not just inherited from Tool base)
        if cls.name == "tool":
            raise TypeError(f"{cls.__name__} must override `name` class attribute")
        if cls.description == "":
            raise TypeError(f"{cls.__name__} must override `description` class attribute")
        if cls.input_schema == {}:
            raise TypeError(f"{cls.__name__} must override `input_schema` class attribute")
        if cls.output_schema == {}:
            raise TypeError(f"{cls.__name__} must override `output_schema` class attribute")
        # Reject reserved parameter names that conflict with __call__ signature
        reserved = {"agent", "action"}
        if reserved & set(cls.input_schema.keys()):
            raise TypeError(
                f"{cls.__name__} input_schema contains reserved key(s) {reserved & set(cls.input_schema.keys())}. "
                "These are reserved for tool call metadata (agent, action)."
            )

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
        except Exception as exc:
            # Log error record for non-ToolInputError exceptions, then re-raise
            self.logger.log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent": agent,
                    "action": action,
                    "tool": self.name,
                    "input_hash": _hash_input(kwargs),
                    "input": _simplify_args(kwargs),
                    "output": {"ok": False, "error": f"{type(exc).__name__}: {str(exc)}"},
                    "latency_seconds": round(time.perf_counter() - start, 6),
                }
            )
            raise
        # Log simplified output: size/summary instead of full data
        output_summary = {
            "ok": result.ok,
            "error": result.error,
            "data_size": len(str(result.data)) if result.data else 0,
            "data_keys": list(result.data.keys()) if result.data else [],
        }
        self.logger.log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "action": action,
                "tool": self.name,
                "input_hash": _hash_input(kwargs),
                "input": _simplify_args(kwargs),
                "output": output_summary,
                "latency_seconds": round(time.perf_counter() - start, 6),
            }
        )
        return result
