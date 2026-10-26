"""Helper to determine reference plan groups for a request kind."""

from __future__ import annotations

from package.evaluation._schema import REFERENCE_PLANS


def reference_groups(kind: str, available_tools: set[str]) -> list[tuple[str, ...]]:
    groups = (tuple(t for t in group if t in available_tools) for group in REFERENCE_PLANS[kind])
    return [g for g in groups if g]
