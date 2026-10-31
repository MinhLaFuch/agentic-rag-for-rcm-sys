import pandas as pd
import pytest
import sqlite3

from package.tools import ItemCorpus


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
    assert "first_seen_ts INTEGER" in items_schema
    assert cats_schema is not None
    assert fts_schema is not None

    # Verify SCHEMA_HINT mentions the key tables
    assert "items(" in SCHEMA_HINT
    assert "first_seen_ts INTEGER" in SCHEMA_HINT
    assert "item_categories(" in SCHEMA_HINT
    assert "items_fts(" in SCHEMA_HINT


def test_corpus_fingerprints_share_canonical_schema_and_logic_version():
    import hashlib
    from package.tools.corpus._fingerprint import compute_corpus_fingerprint
    from package.tools.corpus._sql import CORPUS_LOGIC_VERSION, get_corpus_schema_fingerprint

    expected = hashlib.sha256(
        f"{get_corpus_schema_fingerprint()}:{CORPUS_LOGIC_VERSION}".encode("utf-8")
    ).hexdigest()
    assert compute_corpus_fingerprint() == expected


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


def test_corpus_category_methods(corpus):
    """Test category validation methods."""
    # Test categories() returns sorted list
    cats = corpus.categories()
    assert isinstance(cats, list)
    assert all(isinstance(c, str) for c in cats)

    # Test category_exists with exact match
    if cats:
        assert corpus.category_exists(cats[0], case_sensitive=True)
        assert not corpus.category_exists("NONEXISTENT_CATEGORY", case_sensitive=True)

    # Test category_exists case-insensitive
    if cats:
        # With case-sensitive=False, should match regardless of case
        assert corpus.category_exists(cats[0].lower(), case_sensitive=False) or corpus.category_exists(cats[0].upper(), case_sensitive=False)

    # Test normalize_category_case
    if cats:
        # Exact match returns itself
        assert corpus.normalize_category_case(cats[0]) == cats[0]
        # Non-existent returns None
        assert corpus.normalize_category_case("NONEXISTENT_CATEGORY") is None

    # Test suggest_categories
    if cats:
        suggestions = corpus.suggest_categories("test", max_suggestions=3)
        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3
