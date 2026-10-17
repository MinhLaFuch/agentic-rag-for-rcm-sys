"""Helper to create empty usage dict."""

from __future__ import annotations

from ._schema import USAGE_KEYS


def empty_usage() -> dict[str, float]:
    return {key: 0.0 if key == "latency_seconds" else 0 for key in USAGE_KEYS}
