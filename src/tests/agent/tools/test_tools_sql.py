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
