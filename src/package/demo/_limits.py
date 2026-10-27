"""Runtime limits cho demo, loaded từ configs/agent/demo.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.load_config import ConfigError, load_config


@dataclass(frozen=True)
class DemoLimits:
    max_error_length: int
    max_items_display: int
    sample_users_per_segment: int
    default_language: str
    max_recent_items_display: int
    max_turn_history_rows: int


@lru_cache(maxsize=1)
def get_demo_limits() -> DemoLimits:
    cfg = load_config("agent/demo")["demo"]
    limits = DemoLimits(
        max_error_length=int(cfg["max_error_length"]),
        max_items_display=int(cfg["max_items_display"]),
        sample_users_per_segment=int(cfg["sample_users_per_segment"]),
        default_language=str(cfg["default_language"]),
        max_recent_items_display=int(cfg["max_recent_items_display"]),
        max_turn_history_rows=int(cfg["max_turn_history_rows"]),
    )
    if limits.max_error_length <= 0:
        raise ConfigError("configs/agent/demo.yaml: max_error_length must be > 0")
    if limits.max_items_display <= 0:
        raise ConfigError("configs/agent/demo.yaml: max_items_display must be > 0")
    if limits.sample_users_per_segment <= 0:
        raise ConfigError("configs/agent/demo.yaml: sample_users_per_segment must be > 0")
    if limits.default_language not in ("vi", "en"):
        raise ConfigError("configs/agent/demo.yaml: default_language must be 'vi' or 'en'")
    if limits.max_recent_items_display <= 0:
        raise ConfigError("configs/agent/demo.yaml: max_recent_items_display must be > 0")
    if limits.max_turn_history_rows <= 0:
        raise ConfigError("configs/agent/demo.yaml: max_turn_history_rows must be > 0")
    return limits
