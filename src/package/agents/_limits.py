"""Runtime limits of PlanExecutor, loaded from configs/agent/agent.yaml (tunables live in YAML, contracts in code)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.loader import ConfigError, load_config


@dataclass(frozen=True)
class AgentLimits:
    max_steps: int
    plan_retries: int
    max_tokens: int
    temperature: float


@lru_cache(maxsize=1)
def get_agent_limits() -> AgentLimits:
    cfg = load_config("agent/agent")["agent"]
    limits = AgentLimits(
        max_steps=int(cfg["max_steps"]),
        plan_retries=int(cfg["plan_retries"]),
        max_tokens=int(cfg["max_tokens"]),
        temperature=float(cfg["temperature"]),
    )
    if limits.max_steps <= 0 or limits.max_tokens <= 0:
        raise ConfigError("configs/agent/agent.yaml: max_steps and max_tokens must be > 0")
    if limits.plan_retries < 0:
        raise ConfigError("configs/agent/agent.yaml: plan_retries must be >= 0")
    return limits
