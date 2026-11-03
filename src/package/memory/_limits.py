"""Runtime limits for MemoryTool, loaded from configs/agent/memory.yaml."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryLimits:
    love_min_rating: int
    hate_max_rating: int
    top_n_loved_items: int
    top_n_hated_items: int
    top_n_categories: int
    recent_items: int
