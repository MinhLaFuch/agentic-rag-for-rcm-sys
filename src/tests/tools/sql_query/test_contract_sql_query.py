"""Contract tests for SQLTool, QueryTool and compile_filters (tiny world, hand-checked expectations)."""

import pytest

from package.tools import QueryTool, SQLTool
from package.tools.sql_query._helper import compile_filters

G_A1, G_B2, G_C3, G_D4, T_A1, T_E5 = "Games::A1", "Games::B2", "Games::C3", "Games::D4", "Toys::A1", "Toys::E5"


def ids(result):
    assert result.ok, result.error
    return [c["item_id"] for c in result.data["candidates"]]


# ---------------------------------------------------------------- SQLTool filters
def test_default_order_is_rating_number_desc_with_nulls_last(world):
    # n_ratings: T_E5 500, T_A1 300, G_A1 120, G_B2 80, G_C3 40, G_D4 NULL
    assert ids(SQLTool(world.corpus)()) == [T_E5, T_A1, G_A1, G_B2, G_C3, G_D4]


def test_domain_filter_and_total_matches(world):
    result = SQLTool(world.corpus)(filters={"domain": "Games"}, limit=2)
    assert ids(result) == [G_A1, G_B2]
    assert result.data["total_matches"] == 4 and result.data["truncated"] is True


def test_price_range_excludes_null_price_unless_asked(world):
    tool = SQLTool(world.corpus)
    assert ids(tool(filters={"domain": "Games", "price_max": 50})) == [G_A1, G_B2]
    assert ids(tool(filters={"domain": "Games", "price_max": 50, "include_missing_price": True})) == [G_A1, G_B2, G_C3]
    assert ids(tool(filters={"price_min": 20, "price_max": 30})) == [T_E5, G_B2]


def test_rating_and_rating_number_filters(world):
    tool = SQLTool(world.corpus)
    assert ids(tool(filters={"min_rating": 4.5})) == [T_E5, T_A1, G_A1]  # NULL rating (G_D4) never passes
    assert ids(tool(filters={"min_rating_number": 100})) == [T_E5, T_A1, G_A1]


def test_categories_any_and_all(world):
    tool = SQLTool(world.corpus)
    assert ids(tool(filters={"categories_any": ["Keyboards", "Audio"]})) == [G_A1, G_C3]
    assert ids(tool(filters={"categories_any": ["Computers"]})) == [G_A1, G_B2]  # B2's category was a plain string
    assert ids(tool(filters={"categories_all": ["Computers", "Keyboards"]})) == [G_A1]
    assert ids(tool(filters={"categories_all": ["Computers", "Computers"]})) == [G_A1, G_B2]  # duplicates count once
    assert ids(tool(filters={"categories_all": ["Computers", "Toys"]})) == []


def test_store_filter_is_case_insensitive_for_ascii(world):
    tool = SQLTool(world.corpus)
    assert ids(tool(filters={"store": "HAPE"})) == [T_E5, T_A1]
    assert ids(tool(filters={"store": ["logi", "keychron"]})) == [G_A1, G_B2, G_C3]


def test_store_filter_non_ascii_names_match_themselves():
    import pandas as pd
    from package.tools import ItemCorpus

    corpus = ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["a", "b"], "domain": "D", "store": ["Ünited Co", "acme"]}))
    assert ids(SQLTool(corpus)(filters={"store": "Ünited Co"})) == ["D::a"]  # used to match nothing (Python vs SQLite lower())


def test_title_contains_and_exclude_ids(world):
    tool = SQLTool(world.corpus)
    assert ids(tool(filters={"title_contains": "gaming"})) == [G_B2, G_C3]
    assert ids(tool(filters={"title_contains": "gaming", "exclude_item_ids": [G_B2]})) == [G_C3]
    assert ids(tool(filters={"exclude_item_ids": [G_A1, "Games::missing"], "domain": "Games"})) == [G_B2, G_C3, G_D4]


def test_combined_filters(world):
    result = SQLTool(world.corpus)(
        filters={"domain": ["Games", "Toys"], "price_max": 30, "min_rating": 4.3, "store": "Logi"}
    )
    assert ids(result) == [G_B2]
    assert result.data["applied_filters"]["store"] == ["Logi"]


@pytest.mark.parametrize("order_by, descending, expected", [
    ("price", False, [T_A1, T_E5, G_B2, G_A1, G_D4, G_C3]),  # NULL price (G_C3) last in both directions
    ("price", True, [G_D4, G_A1, G_B2, T_E5, T_A1, G_C3]),
    ("average_rating", True, [T_A1, T_E5, G_A1, G_B2, G_C3, G_D4]),
])
def test_order_by_and_direction(world, order_by, descending, expected):
    assert ids(SQLTool(world.corpus)(order_by=order_by, descending=descending)) == expected


@pytest.mark.parametrize("kwargs, needle", [
    ({"order_by": "title; DROP TABLE items"}, "order_by"),
    ({"order_by": "item_id"}, "order_by"),
    ({"descending": "false"}, "descending"),
    ({"descending": 0}, "descending"),
    ({"limit": 0}, "limit"),
    ({"limit": -1}, "limit"),
    ({"limit": 10**9}, "limit"),
    ({"limit": 2.5}, "limit"),
    ({"filters": {"nope": 1}}, "unknown filter"),
    ({"filters": {"domain": "Nowhere"}}, "unknown domain"),
    ({"filters": {"include_missing_price": "false", "price_max": 5}}, "include_missing_price"),
    ({"filters": {"min_rating_number": 10**400}}, "min_rating_number"),
    ({"filters": {"price_min": 50, "price_max": 10}}, "price_min"),
])
def test_invalid_input_is_a_clean_error(world, kwargs, needle):
    result = SQLTool(world.corpus)(**kwargs)
    assert not result.ok and needle in result.error


def test_empty_result_is_ok_with_zero_counts(world):
    result = SQLTool(world.corpus)(filters={"min_rating": 5.0})
    assert result.ok and result.data["candidates"] == [] and result.data["total_matches"] == 0
    assert result.data["truncated"] is False


def test_empty_filter_values_mean_no_filter(world):
    assert len(ids(SQLTool(world.corpus)(filters={"domain": "", "store": [], "categories_any": []}))) == 6


# ---------------------------------------------------------------- compile_filters: values are bound, never interpolated
def test_user_values_are_bound_parameters_not_sql_text():
    evil = "x' OR 1=1 --"
    where, params, _ = compile_filters(
        {"title_contains": evil, "store": evil, "categories_any": [evil], "exclude_item_ids": [evil]}, {"D"}
    )
    assert "OR 1=1" not in where and "x'" not in where
    assert where.count("?") == len(params)
    assert any(evil in str(p) for p in params)


def test_injection_attempt_in_filter_is_just_data(world):
    result = SQLTool(world.corpus)(filters={"title_contains": "' OR '1'='1"})
    assert ids(result) == [] and result.data["total_matches"] == 0


# ---------------------------------------------------------------- QueryTool
def test_query_by_ids_preserves_requested_order_and_reports_missing(world):
    result = QueryTool(world.corpus)(item_ids=[T_A1, "Nope::x", G_A1, T_A1])  # duplicate + missing
    assert result.ok
    assert [i["item_id"] for i in result.data["items"]] == [T_A1, G_A1]
    assert result.data["missing_item_ids"] == ["Nope::x"] and result.data["truncated"] is False
    assert [i["domain"] for i in result.data["items"]] == ["Toys", "Games"]  # same asin A1, different domains


def test_query_by_ids_max_rows_truncates_in_requested_order(world):
    result = QueryTool(world.corpus)(item_ids=[G_C3, G_A1, T_E5], max_rows=2)
    assert [i["item_id"] for i in result.data["items"]] == [G_C3, G_A1] and result.data["truncated"] is True


@pytest.mark.parametrize("bad", ["Games::A1", [["x"]], [1, 2], [None], [""], 5, {"a": 1}], ids=repr)
def test_query_item_ids_must_be_a_list_of_non_empty_strings(world, bad):
    result = QueryTool(world.corpus)(item_ids=bad)  # a bare string used to be split into characters
    assert not result.ok and "item_ids" in result.error


def test_query_item_ids_empty_list_is_an_error(world):
    assert not QueryTool(world.corpus)(item_ids=[]).ok


def test_query_modes_are_mutually_exclusive(world):
    tool = QueryTool(world.corpus)
    assert not tool().ok
    assert not tool(query="SELECT 1", item_ids=[G_A1]).ok


def test_query_non_string_sql_is_a_clean_error(world):
    result = QueryTool(world.corpus)(query=5)
    assert not result.ok and "query" in result.error


@pytest.mark.parametrize("bad", [0, -1, 10**6, "5", True, 2.5])
def test_query_max_rows_validation(world, bad):
    assert not QueryTool(world.corpus)(query="SELECT 1", max_rows=bad).ok


def test_query_and_sql_tools_use_the_same_ids_as_the_corpus(world):
    from_sql = set(ids(SQLTool(world.corpus)()))
    from_query = {r["item_id"] for r in QueryTool(world.corpus)(query="SELECT item_id FROM items").data["items"]}
    assert from_sql == from_query == set(world.item2id)
