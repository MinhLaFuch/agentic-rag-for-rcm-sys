from package.tools import QueryTool


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
