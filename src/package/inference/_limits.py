"""Runtime limits of the Inference layer, loaded from configs/agent/inference.yaml (tunables live in YAML, contracts in code)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.load_config import ConfigError, load_config
from ._schema import MODES


@dataclass(frozen=True)
class InferenceLimits:
    mode: str
    max_items: int
    max_tokens: int
    temperature: float
    llm_retries: int
    check_numbers: bool
    price_tolerance: float


@lru_cache(maxsize=1)
def get_inference_limits() -> InferenceLimits:
    where = "configs/agent/inference.yaml"
    try:
        cfg = load_config("agent/inference")["inference"]
        limits = InferenceLimits(
            mode=cfg["mode"],
            max_items=int(cfg["max_items"]),
            max_tokens=int(cfg["max_tokens"]),
            temperature=float(cfg["temperature"]),
            llm_retries=int(cfg["llm_retries"]),
            check_numbers=cfg["check_numbers"],
            price_tolerance=float(cfg["price_tolerance"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: missing or malformed value ({type(exc).__name__}: {exc})") from exc
    if limits.mode not in MODES:
        raise ConfigError(f"{where}: mode must be one of {list(MODES)}, got {limits.mode!r}")
    if not isinstance(limits.check_numbers, bool):
        raise ConfigError(f"{where}: check_numbers must be true or false, got {limits.check_numbers!r}")
    for name in ("max_items", "max_tokens"):
        if getattr(limits, name) <= 0:
            raise ConfigError(f"{where}: {name} must be > 0")
    for name in ("temperature", "llm_retries", "price_tolerance"):
        if getattr(limits, name) < 0:
            raise ConfigError(f"{where}: {name} must be >= 0")
    return limits
