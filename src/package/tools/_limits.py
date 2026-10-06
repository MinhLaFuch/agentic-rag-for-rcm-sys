"""Runtime limits for the tools package, loaded once from configs/agent/tools.yaml.

Everything here is tunable behaviour (YAML_CONFIG); the tool *contracts* (columns, filter keys...) are in
``_schema.py``. Values are read at first import and fixed for the life of the process, because tool
descriptions/signatures embed them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config.loader import ConfigError, load_config


@dataclass(frozen=True)
class ToolLimits:
    max_candidates: int
    max_query_rows: int
    sql_time_budget_seconds: float
    semantic_default_limit: int
    semantic_max_query_tokens: int


@lru_cache(maxsize=1)
def get_tool_limits() -> ToolLimits:
    cfg = load_config("agent/tools")["tools"]
    search = cfg["semantic_search"]
    limits = ToolLimits(
        max_candidates=int(cfg["max_candidates"]),
        max_query_rows=int(cfg["max_query_rows"]),
        sql_time_budget_seconds=float(cfg["sql_time_budget_seconds"]),
        semantic_default_limit=int(search["default_limit"]),
        semantic_max_query_tokens=int(search["max_query_tokens"]),
    )
    for name, value in vars(limits).items():
        if value <= 0:
            raise ConfigError(f"configs/agent/tools.yaml: {name} must be > 0, got {value!r}")
    if limits.semantic_default_limit > limits.max_candidates:
        raise ConfigError("configs/agent/tools.yaml: semantic_search.default_limit must be <= max_candidates")
    return limits


_LIMITS = get_tool_limits()
MAX_CANDIDATES = _LIMITS.max_candidates
MAX_QUERY_ROWS = _LIMITS.max_query_rows
SQL_TIME_BUDGET_SECONDS = _LIMITS.sql_time_budget_seconds
SEMANTIC_DEFAULT_LIMIT = _LIMITS.semantic_default_limit
SEMANTIC_MAX_QUERY_TOKENS = _LIMITS.semantic_max_query_tokens
