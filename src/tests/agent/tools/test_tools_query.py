import pytest

from src.tools import QueryTool
from tests.tools_helpers import VG_A


def test_query_by_item_ids_reports_missing(corpus):
    result = QueryTool(corpus)(item_ids=[VG_A, "Video_Games::nope"])
    assert result.ok
    assert [r["item_id"] for r in result.data["items"]] == [VG_A]
    assert result.data["missing_item_ids"] == ["Video_Games::nope"]


def test_query_requires_exactly_one_input(corpus):
    tool = QueryTool(corpus)
    assert not tool().ok
    assert not tool(query="SELECT 1", item_ids=[VG_A]).ok


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE items",
        "DELETE FROM items",
        "SELECT 1; DROP TABLE items",
        "WITH x AS (SELECT 1) DELETE FROM items",
        "PRAGMA query_only = OFF",
        "SELECT * FROM does_not_exist",
    ],
)
def test_query_rejects_unsafe_or_invalid_sql(corpus, bad_sql):
    result = QueryTool(corpus)(query=bad_sql)
    assert not result.ok and result.error
    # the corpus must be intact afterwards
    assert QueryTool(corpus)(query="SELECT COUNT(*) AS n FROM items").data["items"][0]["n"] == 5


def test_query_truncates_and_flags_it(corpus):
    result = QueryTool(corpus)(query="SELECT item_id FROM items", max_rows=2)
    assert len(result.data["items"]) == 2
    assert result.data["truncated"] is True


def test_query_max_rows_is_capped(corpus):
    assert not QueryTool(corpus)(query="SELECT 1", max_rows=10_000).ok


def test_query_infinite_recursion_hits_the_row_cap(corpus):
    sql = "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT n FROM t"
    result = QueryTool(corpus)(query=sql, max_rows=3)
    assert result.ok and len(result.data["items"]) == 3 and result.data["truncated"]
