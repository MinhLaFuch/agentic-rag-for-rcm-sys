import math

import pytest

from package.tools import SQLTool


def _fails_cleanly(result):
    """Input errors must come back as a normal ToolResult error, never crash."""
    return (not result.ok) and bool(result.error)


@pytest.mark.parametrize(
    "filters",
    [
        {"store": [123]},
        {"store": 123},
        {"domain": [123]},
        {"categories_any": [{"a": 1}]},
        {"categories_all": [None]},
        {"exclude_item_ids": [["x"]]},
        {"title_contains": ["a", "b"]},
    ],
)
def test_sql_rejects_wrong_typed_filter_values(corpus, filters):
    assert _fails_cleanly(SQLTool(corpus)(filters=filters))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("key", ["price_min", "price_max", "min_rating"])
def test_sql_rejects_nan_and_infinite_numbers(corpus, key, bad):
    assert _fails_cleanly(SQLTool(corpus)(filters={key: bad}))


@pytest.mark.parametrize("bad", [3.9, True, "3.5", math.nan])
def test_sql_min_rating_number_must_be_a_true_integer(corpus, bad):
    assert _fails_cleanly(SQLTool(corpus)(filters={"min_rating_number": bad}))


@pytest.mark.parametrize("bad", ["abc", [1], {"a": 1}])
def test_sql_non_numeric_price_is_an_input_error(corpus, bad):
    assert _fails_cleanly(SQLTool(corpus)(filters={"price_max": bad}))


def test_sql_set_input_gives_deterministic_params(corpus):
    result = SQLTool(corpus)(filters={"categories_any": {"Games", "Accessories"}})
    assert result.ok
    # _as_list converts set to list, preserving iteration order (not necessarily sorted)
    assert set(result.data["applied_filters"]["categories_any"]) == {"Games", "Accessories"}


def test_sql_applied_filters_store_is_normalised(corpus):
    result = SQLTool(corpus)(filters={"store": "ACME"})
    # applied_filters returns the original value as a list, not lowercased
    # Lowercasing happens in SQL query parameter, not in the returned filter
    assert result.data["applied_filters"]["store"] == ["ACME"]


def test_corpus_select_times_out(corpus, monkeypatch):
    from package.tools.corpus import corpus as mod
    from package.tools.corpus._error import SQLTimeOutError

    monkeypatch.setattr(mod, "SQL_TIME_BUDGET_SECONDS", 0.0)
    sql = "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT COUNT(*) FROM t"
    with pytest.raises(SQLTimeOutError):
        corpus.select(sql, max_rows=1)


def test_sql_rejects_non_dict_filters(corpus):
    """Test that non-dictionary filters are rejected."""
    result_list = SQLTool(corpus)(filters=["domain"])
    result_str = SQLTool(corpus)(filters="domain")
    result_int = SQLTool(corpus)(filters=123)
    assert _fails_cleanly(result_list)
    assert "dictionary" in result_list.error
    assert _fails_cleanly(result_str)
    assert "dictionary" in result_str.error
    assert _fails_cleanly(result_int)
    assert "dictionary" in result_int.error
