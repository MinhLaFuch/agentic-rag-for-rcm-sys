"""Runtime limits of the tools package, loaded once from configs/agent/tools.yaml.

Everything here is tunable behaviour; the tool *contracts* (columns, filter keys...) are in ``_schema.py``.
Values are read at first import and fixed for the life of the process, because tool descriptions embed them.
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
    sql_default_limit: int
    item_cf_default_top_k: int
    query_default_max_rows: int
    memory_default_top_n_categories: int
    semantic_default_limit: int
    semantic_max_query_tokens: int


@lru_cache(maxsize=1)
def get_tool_limits() -> ToolLimits:
    cfg = load_config("agent/tools")["tools"]
    defaults, search = cfg["defaults"], cfg["semantic_search"]
    limits = ToolLimits(
        max_candidates=int(cfg["max_candidates"]),
        max_query_rows=int(cfg["max_query_rows"]),
        sql_time_budget_seconds=float(cfg["sql_time_budget_seconds"]),
        sql_default_limit=int(defaults["sql_limit"]),
        item_cf_default_top_k=int(defaults["item_cf_top_k"]),
        query_default_max_rows=int(defaults["query_max_rows"]),
        memory_default_top_n_categories=int(defaults["memory_top_n_categories"]),
        semantic_default_limit=int(search["default_limit"]),
        semantic_max_query_tokens=int(search["max_query_tokens"]),
    )
    for name, value in vars(limits).items():
        if value <= 0:
            raise ConfigError(f"configs/agent/tools.yaml: {name} must be > 0, got {value!r}")
    capped_by_candidates = ("sql_default_limit", "item_cf_default_top_k", "semantic_default_limit")
    for name in capped_by_candidates:
        if getattr(limits, name) > limits.max_candidates:
            raise ConfigError(f"configs/agent/tools.yaml: {name} must be <= max_candidates")
    if limits.query_default_max_rows > limits.max_query_rows:
        raise ConfigError("configs/agent/tools.yaml: query_default_max_rows must be <= max_query_rows")
    return limits


_LIMITS = get_tool_limits()
MAX_CANDIDATES = _LIMITS.max_candidates
MAX_QUERY_ROWS = _LIMITS.max_query_rows
SQL_TIME_BUDGET_SECONDS = _LIMITS.sql_time_budget_seconds
SQL_DEFAULT_LIMIT = _LIMITS.sql_default_limit
ITEM_CF_DEFAULT_TOP_K = _LIMITS.item_cf_default_top_k
QUERY_DEFAULT_MAX_ROWS = _LIMITS.query_default_max_rows
MEMORY_DEFAULT_TOP_N_CATEGORIES = _LIMITS.memory_default_top_n_categories
SEMANTIC_DEFAULT_LIMIT = _LIMITS.semantic_default_limit
SEMANTIC_MAX_QUERY_TOKENS = _LIMITS.semantic_max_query_tokens
