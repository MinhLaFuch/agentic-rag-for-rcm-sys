"""Hardening tests for the SQL layer (SQLTool / QueryTool / ItemCorpus).

Fills the gaps left by test_tools_sql.py, test_tools_query.py and test_tools_corpus.py:
  1. timeout actually fires (select AND count) and the corpus stays usable afterwards
  2. SQLTool input validation: wrong types / NaN / inf must come back as ToolResult(ok=False), never raise
  3. QueryTool: multiple statements, write attempts hidden in CTEs, other authorizer-blocked features,
     and valid-but-complex SELECTs that must keep working
  4. special characters in filter values are data, never SQL
  5. total_matches is independent of limit when combined with filters
"""

import math

import pytest

from package.tools import QueryTool, SQLTool
from package.tools.base import ToolResult
from package.tools.corpus import corpus as corpus_module
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C

ALL_IDS = {VG_A, VG_B, VG_C, EL_A, EL_D}

SLOW_CTE = "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n < 100000000) SELECT count(*) AS n FROM t"


def _ids(result):
    return {c["item_id"] for c in result.data["candidates"]}


def _corpus_is_intact(corpus):
    assert QueryTool(corpus)(query="SELECT COUNT(*) AS n FROM items").data["items"][0]["n"] == 5


# ---------------------------------------------------------------------------------------------
# 1. timeout
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def tiny_time_budget(monkeypatch):
    """corpus.select()/count() read this module-level constant on every call."""
    monkeypatch.setattr(corpus_module, "SQL_TIME_BUDGET_SECONDS", 0.05)


def test_select_is_stopped_by_the_time_budget(corpus, tiny_time_budget):
    result = QueryTool(corpus)(query=SLOW_CTE)
    assert not result.ok
    assert "time budget" in result.error


def test_count_is_stopped_by_the_time_budget(corpus, tiny_time_budget):
    slow_where = f"item_id IN (WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n < 100000000) SELECT n FROM t)"
    with pytest.raises(Exception, match="time budget"):
        corpus.count(slow_where, ())


def test_corpus_is_usable_after_a_timeout(corpus, tiny_time_budget, monkeypatch):
    assert not QueryTool(corpus)(query=SLOW_CTE).ok
    monkeypatch.undo()  # normal budget again
    assert SQLTool(corpus)().ok  # progress handler was removed, normal queries run
    _corpus_is_intact(corpus)


# ---------------------------------------------------------------------------------------------
# 2. SQLTool input validation: bad input must be a clean ok=False, never an exception
# ---------------------------------------------------------------------------------------------
BAD_FILTERS = [
    ({"price_max": "abc"}, "price_max"),
    ({"price_min": [1]}, "price_min"),
    ({"price_max": float("nan")}, "price_max"),
    ({"price_max": float("inf")}, "price_max"),
    ({"price_min": float("-inf")}, "price_min"),
    ({"price_max": True}, "price_max"),
    ({"min_rating": "high"}, "min_rating"),
    ({"min_rating": float("nan")}, "min_rating"),
    ({"min_rating_number": "x"}, "min_rating_number"),
    ({"min_rating_number": 2.7}, "min_rating_number"),  # must not be silently truncated to 2
    ({"min_rating_number": float("nan")}, "min_rating_number"),
    ({"min_rating_number": True}, "min_rating_number"),
    ({"categories_any": [1, 2]}, "categories_any"),
    ({"categories_any": {"a": 1}}, "categories_any"),
    ({"categories_all": ["ok", None]}, "categories_all"),
    ({"store": ["Acme", 5]}, "store"),
    ({"store": 5}, "store"),
    ({"domain": [1]}, "domain"),
    ({"title_contains": ["a"]}, "title_contains"),
    ({"exclude_item_ids": 5}, "exclude_item_ids"),
    ({"exclude_item_ids": [1, 2]}, "exclude_item_ids"),
]


@pytest.mark.parametrize("bad_filters, field", BAD_FILTERS, ids=[f"{list(f)[0]}={list(f.values())[0]!r}" for f, _ in BAD_FILTERS])
def test_sql_rejects_wrongly_typed_filter_values_cleanly(corpus, bad_filters, field):
    result = SQLTool(corpus)(filters=bad_filters)  # must not raise
    assert isinstance(result, ToolResult)
    assert not result.ok, f"accepted invalid filter {bad_filters!r}: applied={result.data.get('applied_filters')}"
    assert field in result.error
    assert "SQL error" not in result.error  # rejected by validation, not by sqlite's parameter binding


@pytest.mark.parametrize("bad_limit", ["abc", None, 0, -1, 1.5, True, 10**6, float("nan")])
def test_sql_rejects_invalid_limit(corpus, bad_limit):
    result = SQLTool(corpus)(limit=bad_limit)
    assert not result.ok and "limit" in result.error


@pytest.mark.parametrize("bad_filters", ["abc", ["price_max"], 5])
def test_sql_rejects_non_dict_filters_cleanly(corpus, bad_filters):
    result = SQLTool(corpus)(filters=bad_filters)
    assert not result.ok and "filters" in result.error


def test_sql_applied_filters_hold_only_validated_normalized_values(corpus):
    result = SQLTool(corpus)(filters={"price_max": "20", "min_rating_number": "20", "store": "  acme "})
    assert result.ok
    applied = result.data["applied_filters"]
    assert applied["price_max"] == 20.0 and isinstance(applied["price_max"], float)
    assert applied["min_rating_number"] == 20 and isinstance(applied["min_rating_number"], int)
    assert set(applied) == {"price_max", "min_rating_number", "store"}
    assert not math.isnan(applied["price_max"])


def test_sql_empty_filter_lists_are_ignored_consistently(corpus):
    tool = SQLTool(corpus)
    empty = {"domain": [], "store": [], "categories_any": [], "categories_all": [], "exclude_item_ids": []}
    result = tool(filters=empty)
    assert result.ok and _ids(result) == ALL_IDS
    assert result.data["applied_filters"] == {}  # nothing was applied, and nothing is reported as applied


# ---------------------------------------------------------------------------------------------
# 3. QueryTool: raw SQL safety
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1;\nDELETE FROM items",
        "SELECT 1 /* x */; DELETE FROM items",
        "SELECT 1 -- ; harmless comment\n; DROP TABLE items",
        "WITH x AS (SELECT 1) INSERT INTO items(item_id, domain) VALUES ('z', 'z')",
        "WITH x AS (SELECT 1) UPDATE items SET title = 'hacked'",
        "SELECT * FROM items; ATTACH DATABASE ':memory:' AS other",
        "SELECT load_extension('nope')",
        "  \n\t drop table items",
        "",
        "   ;  ",
        "SELECT * FROM does_not_exist",  # valid syntax, unknown table (from the old test_tools_query.py)
    ],
    ids=lambda s: repr(s)[:50],
)
def test_query_rejects_multi_statement_hidden_write_and_unsafe_features(corpus, bad_sql):
    result = QueryTool(corpus)(query=bad_sql)  # must not raise
    assert not result.ok and result.error
    _corpus_is_intact(corpus)
    titles = {r["title"] for r in QueryTool(corpus)(query="SELECT title FROM items").data["items"]}
    assert "hacked" not in titles


@pytest.mark.parametrize(
    "good_sql, expected_first_key",
    [
        ("SELECT 'a;b' AS semi", "semi"),  # ';' inside a string literal is data
        ("SELECT item_id FROM items WHERE title LIKE '%--%' OR 1=1", "item_id"),
        ("WITH v AS (SELECT item_id FROM items WHERE domain='Video_Games') SELECT COUNT(*) AS n FROM v", "n"),
        ("SELECT i.item_id, COUNT(c.category) AS n_cat FROM items i JOIN item_categories c USING(item_id) GROUP BY i.item_id", "item_id"),
        ("SELECT item_id, RANK() OVER (ORDER BY rating_number DESC) AS rk FROM items", "item_id"),
        ("SELECT item_id FROM items WHERE item_id IN (SELECT item_id FROM item_categories WHERE category='Games')", "item_id"),
        ("SELECT rowid FROM items_fts WHERE items_fts MATCH 'mario'", "rowid"),
        ("SELECT item_id FROM items;", "item_id"),  # one trailing ';' is fine
    ],
    ids=lambda v: str(v)[:45],
)
def test_query_still_accepts_valid_complex_select(corpus, good_sql, expected_first_key):
    result = QueryTool(corpus)(query=good_sql)
    assert result.ok, result.error
    assert expected_first_key in result.data["items"][0]


def test_query_item_ids_values_are_data_not_sql(corpus):
    evil = ["x' OR '1'='1", "'; DROP TABLE items; --", VG_A]
    result = QueryTool(corpus)(item_ids=evil)
    assert result.ok
    assert [r["item_id"] for r in result.data["items"]] == [VG_A]
    assert result.data["missing_item_ids"] == evil[:2]
    _corpus_is_intact(corpus)


# ---------------------------------------------------------------------------------------------
# 4. special characters in SQLTool filter values are data
# ---------------------------------------------------------------------------------------------
EVIL_STRINGS = ["O'Brien", '"; DROP TABLE items; --', "x' OR '1'='1", "50%", "a_b", "\\", "%%", "Ünïcode 日本語"]


@pytest.mark.parametrize("value", EVIL_STRINGS, ids=repr)
@pytest.mark.parametrize("key", ["store", "title_contains", "categories_any", "categories_all", "exclude_item_ids"])
def test_sql_special_characters_never_change_the_query(corpus, key, value):
    payload = [value] if key.startswith(("categories", "exclude")) else value
    result = SQLTool(corpus)(filters={key: payload})
    assert result.ok, result.error
    if key == "exclude_item_ids":
        assert _ids(result) == ALL_IDS  # nothing matches the evil id, so nothing is excluded
    else:
        assert result.data["total_matches"] == len(result.data["candidates"]) == 0
    _corpus_is_intact(corpus)


def test_sql_title_contains_with_nul_char_does_not_match_everything(corpus):
    """A NUL char truncates the LIKE pattern in sqlite ('%\\x00%' -> '%%'), silently widening the filter to all rows."""
    result = SQLTool(corpus)(filters={"title_contains": "\u0000"})
    assert not (result.ok and result.data["total_matches"] == len(ALL_IDS))


def test_sql_or_true_payload_does_not_widen_the_result(corpus):
    narrow = SQLTool(corpus)(filters={"store": "Acme"})
    injected = SQLTool(corpus)(filters={"store": "Acme' OR '1'='1"})
    assert _ids(narrow) == {VG_C, EL_D}
    assert _ids(injected) == set()


# ---------------------------------------------------------------------------------------------
# 5. count consistency with filters + limit
# ---------------------------------------------------------------------------------------------
def test_sql_total_matches_ignores_limit_but_respects_filters(corpus):
    result = SQLTool(corpus)(filters={"domain": "Video_Games"}, limit=1)
    assert len(result.data["candidates"]) == 1
    assert result.data["total_matches"] == 3  # VG_A, VG_B, VG_C
    assert result.data["truncated"] is True


def test_sql_not_truncated_when_limit_equals_matches(corpus):
    result = SQLTool(corpus)(filters={"domain": "Video_Games"}, limit=3)
    assert len(result.data["candidates"]) == result.data["total_matches"] == 3
    assert result.data["truncated"] is False


def test_sql_total_matches_zero_when_nothing_matches(corpus):
    result = SQLTool(corpus)(filters={"min_rating": 5.0})
    assert result.ok and result.data["candidates"] == []
    assert result.data["total_matches"] == 0 and result.data["truncated"] is False
