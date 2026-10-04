"""Tool call logger for recording tool invocations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
