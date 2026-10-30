"""Contracts of the agent evaluation (fixed in code on purpose; tunables are in configs/agent/agent_eval.yaml)."""

from __future__ import annotations

from functools import lru_cache

from ..config.load_config import load_config

EVAL_SCHEMA_VERSION = 2

SEGMENTS = ("cold", "sparse", "warm")
AGENTS = ("baseline", "type1", "planner", "planner_memory")
PLANNER_AGENTS = ("planner", "planner_memory")
INFERENCE_AGENTS = ("type1", "planner", "planner_memory")  # agents whose result is turned into an answer (the baseline has none)
# Statuses of an Inference answer. Same as package.inference._schema.STATUSES (a test keeps them equal); duplicated because
# package.inference imports this package, so importing it back would be a cycle.
ANSWER_STATUSES = ("ok", "ask_user", "no_result", "tool_error")

# request kind -> user segments it is drawn from ("none" = no user in the request)
KIND_SEGMENTS = {
    "similar": ("sparse", "warm"),       # "I just bought X, suggest similar"         (history only, honest)
    "personalized": ("sparse", "warm"),  # "suggest things that fit my buying habits" (history only, honest; isolates MemoryTool)
    "constrained": ("sparse", "warm"),   # category + price ceiling built from a held-out item   (ORACLE constraints)
    "cold_text": ("cold",),              # new user who only says what they want                 (ORACLE category)
    "ambiguous": ("none",),              # missing information: the right move is to ask back
}
KINDS = tuple(KIND_SEGMENTS)
ORACLE_KINDS = ("constrained", "cold_text")  # built from held-out items: an upper-bound scenario, not a real query log


@lru_cache(maxsize=1)
def get_reference_plans() -> dict[str, tuple[tuple[str, ...], ...]]:
    """
    Load reference plans from configs/agent/reference_plans.yaml.

    Ordered groups of tools a good plan visits (any tool of a group counts, groups in this order).
    Groups are filtered by the tools the agent actually has, so a planner without MemoryTool is not penalised for it.

    Returns:
        dict mapping request kind to tuple of tuples (tool groups)
    """
    cfg = load_config("agent/reference_plans")["reference_plans"]
    # Convert list of lists to tuple of tuples for immutability
    return {kind: tuple(tuple(group) for group in groups) for kind, groups in cfg.items()}


# Backward compatibility: expose REFERENCE_PLANS as a property that loads from config
# This allows existing code to continue working while new code can use get_reference_plans()
def _get_reference_plans_cached() -> dict[str, tuple[tuple[str, ...], ...]]:
    """Cached accessor for reference plans."""
    return get_reference_plans()


# Create a property-like accessor
class _ReferencePlans:
    """Lazy accessor for reference plans."""

    def __getitem__(self, key: str) -> tuple[tuple[str, ...], ...]:
        return get_reference_plans()[key]

    def __iter__(self):
        return iter(get_reference_plans())

    def keys(self):
        return get_reference_plans().keys()

    def values(self):
        return get_reference_plans().values()

    def items(self):
        return get_reference_plans().items()


REFERENCE_PLANS = _ReferencePlans()
