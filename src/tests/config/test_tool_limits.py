import pytest

from package.config.loader import ConfigError, load_config
from package.tools import _limits
from package.tools.base import check_top_k
from package.tools._limits import MAX_CANDIDATES
from package.tools.base import ToolInputError


@pytest.fixture
def fresh_limits():
    _limits.get_tool_limits.cache_clear()
    yield
    _limits.get_tool_limits.cache_clear()


def test_limits_come_from_tools_yaml():
    cfg = load_config("agent/tools")["tools"]
    limits = _limits.get_tool_limits()
    assert limits.max_candidates == cfg["max_candidates"] == MAX_CANDIDATES
    assert limits.max_query_rows == cfg["max_query_rows"]
    assert limits.sql_time_budget_seconds == cfg["sql_time_budget_seconds"]
    assert limits.semantic_default_limit == cfg["semantic_search"]["default_limit"]
    assert limits.semantic_max_query_tokens == cfg["semantic_search"]["max_query_tokens"]


def test_check_top_k_uses_configured_cap():
    assert check_top_k(MAX_CANDIDATES) == MAX_CANDIDATES
    with pytest.raises(ToolInputError):
        check_top_k(MAX_CANDIDATES + 1)


@pytest.mark.parametrize(
    "patch",
    [
        {"max_candidates": 0},
        {"sql_time_budget_seconds": -1},
        {"semantic_search": {"default_limit": 5000, "max_query_tokens": 20}},  # default > cap
    ],
)
def test_invalid_limits_are_rejected(monkeypatch, fresh_limits, patch):
    good = load_config("agent/tools")
    bad = {"tools": {**good["tools"], **patch}}
    monkeypatch.setattr(_limits, "load_config", lambda name: bad)
    with pytest.raises(ConfigError):
        _limits.get_tool_limits()
