import pandas as pd
import pytest

from package.tools import ItemCorpus, SemanticSearchTool


def _ids(result):
    return [c["item_id"] for c in result.data["candidates"]]


@pytest.fixture
def kb_corpus():
    meta = pd.DataFrame(
        {
            "parent_asin": ["k1", "k2", "k3", "g1"],
            "domain": ["Electronics", "Electronics", "Electronics", "Video_Games"],
            "title": [
                "Quiet Mechanical Keyboard for Coding",
                "Wireless Gaming Mouse",
                "Mechanical Keyboard Keycap Set",
                "Keyboard Typing Adventure Game",
            ],
            "price": [45.0, 25.0, 15.0, 30.0],
            "average_rating": [4.6, 4.4, 4.0, 4.1],
            "rating_number": [500, 900, 50, 20],
            "store": ["Keychron", "Logitech", "Acme", "Indie"],
            "main_category": ["Keyboards", "Mice", "Accessories", "Games"],
            "categories": [["Keyboards"], ["Mice"], ["Keyboards", "Accessories"], ["Games"]],
        }
    )
    return ItemCorpus.from_dataframe(meta)


def test_search_applies_structured_filters(kb_corpus):
    tool = SemanticSearchTool(kb_corpus)
    cheap = tool(query="keyboard", filters={"price_max": 20})
    assert _ids(cheap) == ["Electronics::k3"]
    games = tool(query="keyboard", filters={"domain": "Video_Games"})
    assert _ids(games) == ["Video_Games::g1"]


def test_search_query_cannot_inject_fts_syntax(kb_corpus):
    tool = SemanticSearchTool(kb_corpus)
    for q in ['keyboard" OR title:mouse', "keyboard NOT mouse *", "NEAR(keyboard mouse)", "col:keyboard"]:
        assert tool(query=q).ok  # treated as plain words, never as FTS5 operators


def test_search_rejects_unknown_filter_and_bad_limit(kb_corpus):
    tool = SemanticSearchTool(kb_corpus)
    assert not tool(query="keyboard", filters={"colour": "red"}).ok
    assert not tool(query="keyboard", limit=0).ok


def test_search_respects_limit_and_is_logged(kb_corpus):
    tool = SemanticSearchTool(kb_corpus)
    result = tool(query="keyboard", limit=1, agent="unit", action="search")
    assert len(result.data["candidates"]) == 1 and result.data["truncated"]
    assert tool.logger.records[-1]["tool"] == "SemanticSearchTool"


def test_search_hyphenated_tokens_preserved(kb_corpus):
    """Test that hyphenated tokens like 'usb-c' are preserved."""
    meta_usb = pd.DataFrame(
        {
            "parent_asin": ["u1", "u2"],
            "domain": ["Electronics", "Electronics"],
            "title": ["USB-C Cable", "USB Cable"],
            "price": [10.0, 15.0],
            "average_rating": [4.5, 4.0],
            "rating_number": [100, 50],
            "store": ["StoreA", "StoreB"],
            "main_category": ["Cables", "Cables"],
            "categories": [["Cables"], ["Cables"]],
        }
    )
    corpus_usb = ItemCorpus.from_dataframe(meta_usb)
    result = SemanticSearchTool(corpus_usb)(query="usb-c cable")
    assert "Electronics::u1" in _ids(result)


def test_search_empty_lists_in_filters(kb_corpus):
    """Test that empty lists in filters are treated as 'no filter'."""
    tool = SemanticSearchTool(kb_corpus)
    result_empty_any = tool(query="keyboard", filters={"categories_any": []})
    result_empty_all = tool(query="keyboard", filters={"categories_all": []})
    result_empty_domain = tool(query="keyboard", filters={"domain": []})
    # All should return results, not filter out everything
    assert len(result_empty_any.data["candidates"]) > 0
    assert len(result_empty_all.data["candidates"]) > 0
    assert len(result_empty_domain.data["candidates"]) > 0


def test_search_long_exclude_item_ids(kb_corpus):
    """Test that a long list of exclude_item_ids works correctly."""
    tool = SemanticSearchTool(kb_corpus)
    # Exclude 3 out of 4 items
    result = tool(query="keyboard", filters={"exclude_item_ids": ["Electronics::k1", "Electronics::k2", "Electronics::k3"]})
    assert _ids(result) == ["Video_Games::g1"]


def test_search_total_matches_with_filters(kb_corpus):
    """Test that total_matches correctly accounts for filters."""
    tool = SemanticSearchTool(kb_corpus)
    # Filter by price should reduce total_matches
    result_all = tool(query="keyboard")
    result_filtered = tool(query="keyboard", filters={"price_max": 20})
    assert result_all.ok and result_filtered.ok
    assert result_filtered.data["total_matches"] <= result_all.data["total_matches"]


def test_search_rejects_non_dict_filters(kb_corpus):
    """Test that non-dictionary filters are rejected."""
    tool = SemanticSearchTool(kb_corpus)
    result_list = tool(query="keyboard", filters=["domain"])
    result_str = tool(query="keyboard", filters="domain")
    result_int = tool(query="keyboard", filters=123)
    assert not result_list.ok
    assert "dictionary" in result_list.error
    assert not result_str.ok
    assert "dictionary" in result_str.error
    assert not result_int.ok
    assert "dictionary" in result_int.error


def test_search_validates_filter_types(kb_corpus):
    """Test that filter values are validated for correct types."""
    tool = SemanticSearchTool(kb_corpus)
    # Invalid price filter
    result_bad_price = tool(query="keyboard", filters={"price_min": "invalid"})
    assert not result_bad_price.ok
    assert "price_min" in result_bad_price.error
    # Invalid rating_number filter
    result_bad_rating = tool(query="keyboard", filters={"min_rating_number": "abc"})
    assert not result_bad_rating.ok
    assert "min_rating_number" in result_bad_rating.error


def test_search_applied_filters_are_normalized(kb_corpus):
    """Test that applied_filters returns normalized filters, not raw input."""
    tool = SemanticSearchTool(kb_corpus)
    result = tool(query="keyboard", filters={"price_min": "50", "price_max": "100"})
    assert result.ok
    # Normalized filters should have numeric types, not strings
    applied = result.data["applied_filters"]
    assert isinstance(applied.get("price_min"), (int, float))
    assert isinstance(applied.get("price_max"), (int, float))
    assert applied["price_min"] == 50.0
    assert applied["price_max"] == 100.0


def test_search_fts_with_categories_any(kb_corpus):
    """Test that FTS search combined with categories_any filter returns correct results."""
    tool = SemanticSearchTool(kb_corpus)
    # Query for "keyboard" with categories_any filter
    result = tool(query="keyboard", filters={"categories_any": ["Keyboards"]})
    assert result.ok
    # Should return items in Keyboards category
    ids = _ids(result)
    assert "Electronics::k1" in ids  # Quiet Mechanical Keyboard
    assert "Electronics::k3" in ids  # Mechanical Keyboard Keycap Set
    # Should exclude items not in Keyboards category
    assert "Electronics::k2" not in ids  # Wireless Gaming Mouse (Mice category)
    assert "Video_Games::g1" not in ids  # Keyboard Typing Adventure Game (Games category)


def test_search_fts_with_categories_any_multiple(kb_corpus):
    """Test that categories_any with multiple categories works correctly (OR semantics)."""
    tool = SemanticSearchTool(kb_corpus)
    # Query for items in Keyboards OR Accessories categories
    result = tool(query="keyboard", filters={"categories_any": ["Keyboards", "Accessories"]})
    assert result.ok
    ids = _ids(result)
    # Should include items from either category that also match FTS query
    assert "Electronics::k1" in ids  # Keyboards
    assert "Electronics::k3" in ids  # Keyboards + Accessories
    # Should exclude items from other categories (even if they match FTS)
    assert "Video_Games::g1" not in ids  # Games (matches FTS but not category filter)


def test_search_fts_with_categories_any_excludes_unmatched(kb_corpus):
    """Test that categories_any correctly excludes items not matching any specified category."""
    tool = SemanticSearchTool(kb_corpus)
    # Query for a specific category that doesn't match some items
    result = tool(query="keyboard", filters={"categories_any": ["Accessories"]})
    assert result.ok
    ids = _ids(result)
    # Only k3 has Accessories category
    assert "Electronics::k3" in ids
    # Others should be excluded
    assert "Electronics::k1" not in ids
    assert "Electronics::k2" not in ids
    assert "Video_Games::g1" not in ids


def test_search_fts_with_categories_any_empty_list(kb_corpus):
    """Test that empty categories_any list is treated as no filter (already covered but explicit for FTS)."""
    tool = SemanticSearchTool(kb_corpus)
    result = tool(query="keyboard", filters={"categories_any": []})
    assert result.ok
    # Should return all keyboard-matching items regardless of category
    ids = _ids(result)
    assert len(ids) > 0


def test_composite_index_exists_after_corpus_init():
    """Test that the composite index idx_cat_item_cat is created during corpus initialization."""
    meta = pd.DataFrame(
        {
            "parent_asin": ["i1"],
            "domain": ["Electronics"],
            "title": ["Test Item"],
            "price": [10.0],
            "average_rating": [4.0],
            "rating_number": [100],
            "store": ["TestStore"],
            "main_category": ["TestCat"],
            "categories": [["Cat1", "Cat2"]],
        }
    )
    corpus = ItemCorpus.from_dataframe(meta)
    # Check that the composite index exists
    indexes = corpus._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cat_item_cat'"
    ).fetchall()
    assert len(indexes) == 1, "Composite index idx_cat_item_cat should exist after corpus initialization"


def test_search_fts_with_categories_any_correctness_large_corpus():
    """Correctness test: FTS + categories_any on a larger synthetic corpus."""
    # Create a corpus with many items in a large category
    items = []
    for i in range(100):
        items.append({
            "parent_asin": f"item_{i}",
            "domain": "Electronics",
            "title": f"Test Item {i} keyboard",
            "price": 10.0 + i,
            "average_rating": 4.0,
            "rating_number": 100,
            "store": "TestStore",
            "main_category": "Keyboards",
            "categories": ["Keyboards"] if i < 90 else ["Other"],  # 90 items in Keyboards, 10 in Other
        })
    meta = pd.DataFrame(items)
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SemanticSearchTool(corpus)

    # Query with FTS + categories_any targeting the large category
    result = tool(query="keyboard", filters={"categories_any": ["Keyboards"]}, limit=50)
    assert result.ok
    # Should return results from the large category
    assert len(result.data["candidates"]) > 0
    # All returned items should be in Keyboards category
    for candidate in result.data["candidates"]:
        assert candidate["main_category"] == "Keyboards"
    # Total matches should reflect the filter
    assert result.data["total_matches"] >= 90  # At least the 90 items in Keyboards


def test_categories_any_uses_composite_index():
    """Regression test: FTS + categories_any must use idx_cat_item_cat index.
    
    This test checks the query plan to ensure the composite index is used,
    which prevents timeouts on large corpora. Without the composite index,
    SQLite uses idx_cat_cat and repeatedly scans category entries for each FTS match.
    """
    meta = pd.DataFrame(
        {
            "parent_asin": ["k1", "k2", "k3"],
            "domain": ["Electronics", "Electronics", "Electronics"],
            "title": ["Keyboard A", "Keyboard B", "Mouse"],
            "price": [10.0, 20.0, 15.0],
            "average_rating": [4.0, 4.5, 4.2],
            "rating_number": [100, 200, 150],
            "store": ["StoreA", "StoreB", "StoreC"],
            "main_category": ["Keyboards", "Keyboards", "Mice"],
            "categories": [["Keyboards"], ["Keyboards"], ["Mice"]],
        }
    )
    corpus = ItemCorpus.from_dataframe(meta)
    
    # Run EXPLAIN QUERY PLAN on the same SQL pattern that SemanticSearchTool uses
    match = '"keyboard"'
    where = """EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id
AND c.category IN (?))"""
    sql = (
        f"SELECT items.item_id FROM items_fts "
        f"JOIN items ON items.rowid = items_fts.rowid "
        f"WHERE items_fts MATCH ? AND {where}"
    )
    plan = corpus._conn.execute(f"EXPLAIN QUERY PLAN {sql}", [match, "Keyboards"]).fetchall()
    
    # Check that the plan uses the composite index idx_cat_item_cat
    plan_str = " ".join(str(row) for row in plan)
    assert "idx_cat_item_cat" in plan_str, (
        f"Query plan should use composite index idx_cat_item_cat, but got:\n{plan}"
    )
    # Also verify it's a covering index (more efficient)
    assert "COVERING INDEX" in plan_str or "USING COVERING INDEX" in plan_str, (
        f"Query plan should use covering index for efficiency, but got:\n{plan}"
    )
