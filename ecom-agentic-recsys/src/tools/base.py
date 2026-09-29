"""
Shared tool infrastructure: result type, input errors, call logging, base class.

Every tool call is logged: timestamp, agent, action, tool, input hash, output,
latency (architecture.md section 4).  Bad input returns ToolResult(ok=False,
error=...) instead of raising, so the agent can react; real bugs still raise.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ._config import MAX_CANDIDATES


def _hash_input(kwargs: dict[str, Any]) -> str:
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ToolInputError(ValueError):
    """Caller gave invalid input (bad filter, unsafe SQL, unknown domain...)."""


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolCallLogger:
    """Keeps tool-call records in memory and optionally appends them to a JSONL file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.records: list[dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict[str, Any]) -> None:
        self.records.append(record)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


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

def check_top_k(top_k: int, upper: int = MAX_CANDIDATES) -> int:
    if not isinstance(top_k, (int, np.integer)) or not 1 <= top_k <= upper:
        raise ToolInputError(f"top_k must be an integer in [1, {upper}], got {top_k!r}")
    return int(top_k)


def candidate_ids(candidates: Sequence[Any]) -> list[str]:
    """Accept item-id strings or dicts with 'item_id' (i.e. another tool's output as-is)."""
    ids: list[str] = []
    for c in candidates:
        if isinstance(c, str):
            ids.append(c)
        elif isinstance(c, dict) and isinstance(c.get("item_id"), str):
            ids.append(c["item_id"])
        else:
            raise ToolInputError(f"candidate must be an item_id string or dict with 'item_id': {c!r}")
    return list(dict.fromkeys(ids))  # de-duplicate, keep order




