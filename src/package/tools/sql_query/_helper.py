"""Helper functions for sql_query module."""

from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else [value]
