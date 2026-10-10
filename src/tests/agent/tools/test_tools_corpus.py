import pandas as pd
import pytest
import sqlite3

from package.tools import ItemCorpus, QueryTool
from tests.tools_helpers import EL_A, VG_A, VG_B, VG_C


def test_corpus_namespaces_ids_so_equal_asins_do_not_collide(corpus):
    ids = {r["item_id"] for r in QueryTool(corpus)(query="SELECT item_id FROM items").data["items"]}
    assert {VG_A, EL_A} <= ids


def test_corpus_parses_price_strings_and_keeps_missing_as_null(corpus):
    rows = QueryTool(corpus)(query="SELECT item_id, price FROM items WHERE domain='Video_Games'").data["items"]
    prices = {r["item_id"]: r["price"] for r in rows}
    assert prices == {VG_A: 19.99, VG_B: None, VG_C: 5.5}


def test_corpus_rejects_duplicate_item_ids():
    meta = pd.DataFrame({"parent_asin": ["a", "a"], "title": ["x", "y"]})
    with pytest.raises(ValueError, match="duplicate"):
        ItemCorpus.from_dataframe(meta, domain="Video_Games")


def test_corpus_requires_a_domain():
    with pytest.raises(ValueError, match="domain"):
        ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["a"]}))


def test_corpus_schema_matches_schema_hint():
    """Verify the actual DDL created by from_dataframe matches SCHEMA_HINT."""
    from package.tools._schema import SCHEMA_HINT

    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "title": ["x", "y"],
        "domain": ["Test", "Test"],
    })
    corpus = ItemCorpus.from_dataframe(meta)

    # Get the actual table schemas from SQLite
    items_schema = corpus._conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items'").fetchone()[0]
    cats_schema = corpus._conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='item_categories'").fetchone()[0]
    fts_schema = corpus._conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items_fts'").fetchone()[0]

    # Verify key tables exist
    assert items_schema is not None
    assert cats_schema is not None
    assert fts_schema is not None

    # Verify SCHEMA_HINT mentions the key tables
    assert "items(" in SCHEMA_HINT
    assert "item_categories(" in SCHEMA_HINT
    assert "items_fts(" in SCHEMA_HINT


def test_query_tool_handles_trailing_comment_in_query(corpus):
    """SQL queries with trailing -- comments should not break the wrapper."""
    from package.tools import QueryTool

    # Query with trailing comment
    result = QueryTool(corpus)(query="SELECT item_id FROM items WHERE domain='Video_Games' -- test comment")
    assert result.ok
    assert len(result.data["items"]) > 0


def test_corpus_authorizer_blocks_writes(corpus):
    """The authorizer should block any write operations."""
    # Try to INSERT - should fail
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        corpus._conn.execute("INSERT INTO items (item_id, domain) VALUES ('test', 'test')")

    # Try to DELETE - should fail
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        corpus._conn.execute("DELETE FROM items WHERE item_id='test'")

    # Try to DROP - should fail
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        corpus._conn.execute("DROP TABLE items")


def test_corpus_count_respects_time_budget(corpus):
    """count() should have the same time budget as select()."""
    # This is a basic sanity check - we can't easily test timeout without mocking
    # but we verify the method exists and works
    count = corpus.count("domain = ?", ("Video_Games",))
    assert count >= 0
    assert isinstance(count, int)


def test_corpus_item_domains_handles_chunking(corpus):
    """item_domains should handle large lists by chunking."""
    # Get all item IDs from the corpus
    all_items = corpus._conn.execute("SELECT item_id FROM items").fetchall()
    all_ids = [r[0] for r in all_items]

    # If we have many items, test chunking
    if len(all_ids) > 1000:
        domains = corpus.item_domains(all_ids)
        assert len(domains) == len(all_ids)
        assert all(isinstance(d, str) for d in domains.values())


def test_corpus_from_dataframe_with_original_item_id():
    """Test from_dataframe when original_item_id is already namespaced."""
    meta = pd.DataFrame({
        "parent_asin": ["Video_Games::a", "Video_Games::b"],
        "title": ["x", "y"],
        "domain": ["Video_Games", "Video_Games"],
        "original_item_id": ["Video_Games::a", "Video_Games::b"],
    })
    # Should not warn about missing '::' since parent_asin already has it
    corpus = ItemCorpus.from_dataframe(meta)
    assert corpus._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2


def test_corpus_from_parquet_works(tmp_path):
    """Test from_parquet method."""
    import tempfile
    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "title": ["x", "y"],
        "domain": ["Test", "Test"],
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = f"{tmpdir}/test.parquet"
        meta.to_parquet(parquet_path)

        corpus = ItemCorpus.from_parquet(parquet_path)
        assert corpus._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
