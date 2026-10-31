"""Runtime limits for MemoryTool, loaded from configs/agent/memory.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.load_config import load_config


@dataclass(frozen=True)
class MemoryLimits:
    love_min_rating: int
    hate_max_rating: int
    top_n_loved_items: int
    top_n_hated_items: int
    top_n_categories: int
    recent_items: int


@lru_cache(maxsize=1)
def get_memory_limits() -> MemoryLimits:
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