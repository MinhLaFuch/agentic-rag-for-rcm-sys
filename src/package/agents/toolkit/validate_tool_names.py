"""Validate danh sách tên tool cho tool subset (config exclude_tools / YAML overlay)."""

from __future__ import annotations

from collections.abc import Iterable

from ...memory.memory_tool import MemoryTool
from ...tools import SimilarTool, LookupTool, RankTool, SearchTool, FilterTool

_VALID_TOOL_NAMES = frozenset(
    cls.__name__
    for cls in (SimilarTool, RankTool, LookupTool, SearchTool, FilterTool, MemoryTool)
)


def validate_tool_names(names: Iterable[str]) -> list[str]:
    """Validate danh sách tên tool; raise ValueError kèm tên hợp lệ nếu sai."""
    out = [str(n) for n in names]
    unknown = sorted(set(out) - _VALID_TOOL_NAMES)
    if unknown:
        raise ValueError(
            f"Unknown tool name(s) {unknown}; valid: {sorted(_VALID_TOOL_NAMES)}"
        )
    return out
