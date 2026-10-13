"""Runtime limits of the agents, loaded from configs/agent/agent.yaml (tunables live in YAML, contracts in code)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.loader import ConfigError, load_config


@dataclass(frozen=True)
class AgentLimits:
    max_steps: int
    plan_retries: int
    reflect_rounds: int
    max_tokens: int
    temperature: float
    type1_candidate_multiplier: int
    type1_min_candidates: int


@lru_cache(maxsize=1)
def get_agent_limits() -> AgentLimits:
    cfg = load_config("agent/agent")["agent"]
    limits = AgentLimits(
        max_steps=int(cfg["max_steps"]),
        plan_retries=int(cfg["plan_retries"]),
        reflect_rounds=int(cfg["reflect_rounds"]),
        max_tokens=int(cfg["max_tokens"]),
        temperature=float(cfg["temperature"]),
        type1_candidate_multiplier=int(cfg["type1"]["candidate_multiplier"]),
        type1_min_candidates=int(cfg["type1"]["min_candidates"]),
    )
    positive = ("max_steps", "max_tokens", "type1_candidate_multiplier", "type1_min_candidates")
    for name in positive:
        if getattr(limits, name) <= 0:
            raise ConfigError(f"configs/agent/agent.yaml: {name} must be > 0")
    for name in ("plan_retries", "reflect_rounds"):
        if getattr(limits, name) < 0:
            raise ConfigError(f"configs/agent/agent.yaml: {name} must be >= 0")
    return limits
