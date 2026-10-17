"""Cut a reason / error text to the configured length."""

from __future__ import annotations

from typing import Any

from ._limits import get_inference_limits


def cut(text: Any, limit: int | None = None) -> str:
    return str(text)[: get_inference_limits().reason_chars if limit is None else limit]
