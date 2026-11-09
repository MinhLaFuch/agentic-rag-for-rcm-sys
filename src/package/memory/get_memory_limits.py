"""Runtime limits for MemoryTool, loaded from configs/agent/memory.yaml."""

from __future__ import annotations

from functools import lru_cache

from ..config import config_signature
from ..config.load_config import load_config
from ._limits import MemoryLimits


@lru_cache(maxsize=1)
def _cached_memory_limits() -> MemoryLimits:
    """Load memory limits from configs/agent/memory.yaml."""
    cfg = load_config("agent/memory")["memory"]
    return MemoryLimits(
        love_min_rating=int(cfg["love_min_rating"]),
        hate_max_rating=int(cfg["hate_max_rating"]),
        top_n_loved_items=int(cfg["top_n_loved_items"]),
        top_n_hated_items=int(cfg["top_n_hated_items"]),
        top_n_categories=int(cfg["top_n_categories"]),
        recent_items=int(cfg["recent_items"]),
    )


_limits_signature: tuple | None = None


def get_memory_limits() -> MemoryLimits:
    """Memory limits, refreshed when configs/agent/memory.yaml or the config overlay changes."""
    global _limits_signature
    signature = config_signature("agent/memory")
    if signature != _limits_signature:
        _limits_signature = signature
        _cached_memory_limits.cache_clear()
    return _cached_memory_limits()


def _clear_memory_limits_cache() -> None:
    """Clear the memory limits cache when config files change."""
    _cached_memory_limits.cache_clear()
