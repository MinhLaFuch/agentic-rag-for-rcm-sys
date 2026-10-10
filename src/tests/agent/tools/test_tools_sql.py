from package.tools import SQLTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


def _ids(result):
    return [c["item_id"] for c in result.data["candidates"]]


def test_sql_price_filter_excludes_missing_price_by_default(corpus):
    result = SQLTool(corpus)(filters={"price_max": 20})
    assert VG_B not in _ids(result)  # price is null -> excluded (D-006)
    assert set(_ids(result)) == {VG_A, VG_C, EL_D}


def test_sql_price_filter_can_keep_missing_price(corpus):
    result = SQLTool(corpus)(filters={"price_max": 20, "include_missing_price": True, "domain": "Video_Games"})
    assert set(_ids(result)) == {VG_A, VG_B, VG_C}


def test_sql_categories_any_vs_all(corpus):
    tool = SQLTool(corpus)
    assert set(_ids(tool(filters={"categories_all": ["Video Games", "Games"]}))) == {VG_A, VG_B}
    assert set(_ids(tool(filters={"categories_any": ["Accessories", "Electronics"]}))) == {VG_C, EL_A, EL_D}


def test_sql_domain_filter_and_unknown_domain(corpus):
    tool = SQLTool(corpus)
    assert set(_ids(tool(filters={"domain": "Electronics"}))) == {EL_A, EL_D}
    assert set(_ids(tool(filters={"domain": ["Electronics", "Video_Games"]}))) == {VG_A, VG_B, VG_C, EL_A, EL_D}
    bad = tool(filters={"domain": "Books"})
    assert not bad.ok and "Books" in bad.error


def test_sql_rejects_unknown_filter_key_instead_of_ignoring_it(corpus):
    result = SQLTool(corpus)(filters={"colour": "red"})
    assert not result.ok and "colour" in result.error


def test_sql_rating_store_and_exclusion_filters(corpus):
    tool = SQLTool(corpus)
    assert set(_ids(tool(filters={"min_rating": 4.4}))) == {VG_A, VG_B}
    assert set(_ids(tool(filters={"min_rating_number": 20}))) == {VG_A, VG_B, EL_A}
    assert set(_ids(tool(filters={"store": "Acme"}))) == {VG_C, EL_D}
    assert VG_A not in _ids(tool(filters={"exclude_item_ids": [VG_A]}))


def test_sql_title_search_treats_like_wildcards_literally(corpus):
    tool = SQLTool(corpus)
    assert _ids(tool(filters={"title_contains": "100%"})) == [VG_B]
    assert tool(filters={"title_contains": "%"}).data["total_matches"] == 1  # only "Mario 100%"
    assert tool(filters={"title_contains": "'; DROP TABLE items; --"}).data["total_matches"] == 0


def test_sql_orders_by_rating_number_desc_and_puts_nulls_last_for_price(corpus):
    tool = SQLTool(corpus)
    assert _ids(tool()) == [VG_A, VG_B, EL_A, VG_C, EL_D]
    by_price = _ids(tool(filters={"domain": "Video_Games"}, order_by="price", descending=False))
    assert by_price == [VG_C, VG_A, VG_B]  # null price last
    assert not tool(order_by="title; DROP TABLE items").ok


def test_sql_limit_reports_total_matches_and_truncation(corpus):
    result = SQLTool(corpus)(limit=2)
    assert len(result.data["candidates"]) == 2
    assert result.data["total_matches"] == 5
    assert result.data["truncated"] is True


def test_sql_empty_list_and_string_handling(corpus):
    """Test that empty strings and lists are treated as 'no filter'."""
    tool = SQLTool(corpus)
    # Empty string for domain = no filter
    result_empty_str = tool(filters={"domain": ""})
    assert len(result_empty_str.data["candidates"]) == 5
    # Empty list for categories = no filter
    result_empty_list = tool(filters={"categories_any": []})
    assert len(result_empty_list.data["candidates"]) == 5
    # Whitespace-only string = no filter
    result_whitespace = tool(filters={"store": "   "})
    assert len(result_whitespace.data["candidates"]) == 5


def test_sql_case_insensitive_store_match(corpus):
    """Test that store matching is case-insensitive."""
    tool = SQLTool(corpus)
    # Store "Acme" should match "acme", "ACME", "Acme"
    result_lower = tool(filters={"store": "acme"})
    result_upper = tool(filters={"store": "ACME"})
    result_mixed = tool(filters={"store": "Acme"})
    assert _ids(result_lower) == _ids(result_upper) == _ids(result_mixed)
    assert set(_ids(result_mixed)) == {VG_C, EL_D}


def test_sql_price_min_greater_than_max_suggests_fix(corpus):
    """Test that price_min > price_max returns a helpful error message."""
    tool = SQLTool(corpus)
    result = tool(filters={"price_min": 100, "price_max": 50})
    assert not result.ok
    assert "price_min" in result.error and "price_max" in result.error
    assert "Swap the values" in result.error


def test_sql_duplicate_categories_all_deduped(corpus):
    """Test that duplicate categories in categories_all are deduplicated."""
    tool = SQLTool(corpus)
    # Duplicate "Video Games" should not cause issues
    result = tool(filters={"categories_all": ["Video Games", "Video Games", "Games"]})
    assert set(_ids(result)) == {VG_A, VG_B}


def test_sql_long_exclude_item_ids(corpus):
    """Test that a long list of exclude_item_ids works correctly."""
    tool = SQLTool(corpus)
    # Exclude all but one item
    result = tool(filters={"exclude_item_ids": [VG_A, VG_B, VG_C, EL_D]})
    assert _ids(result) == [EL_A]
