from package.tools import SQLTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


def _ids(result):
    return [c["item_id"] for c in result.data["candidates"]]


def test_sql_domain_filter_and_unknown_domain(corpus):
    tool = SQLTool(corpus)
    assert set(_ids(tool(filters={"domain": "Electronics"}))) == {EL_A, EL_D}
    assert set(_ids(tool(filters={"domain": ["Electronics", "Video_Games"]}))) == {VG_A, VG_B, VG_C, EL_A, EL_D}
    bad = tool(filters={"domain": "Books"})
    assert not bad.ok and "Books" in bad.error


def test_sql_rejects_unknown_filter_key_instead_of_ignoring_it(corpus):
    result = SQLTool(corpus)(filters={"colour": "red"})
    assert not result.ok and "colour" in result.error


def test_sql_title_search_treats_like_wildcards_literally(corpus):
    tool = SQLTool(corpus)
    assert _ids(tool(filters={"title_contains": "100%"})) == [VG_B]
    assert tool(filters={"title_contains": "%"}).data["total_matches"] == 1  # only "Mario 100%"
    assert tool(filters={"title_contains": "'; DROP TABLE items; --"}).data["total_matches"] == 0


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


def test_sql_price_min_greater_than_max_suggests_fix(corpus):
    """Test that price_min > price_max returns a helpful error message."""
    tool = SQLTool(corpus)
    result = tool(filters={"price_min": 100, "price_max": 50})
    assert not result.ok
    assert "price_min" in result.error and "price_max" in result.error
    assert "Swap the values" in result.error
