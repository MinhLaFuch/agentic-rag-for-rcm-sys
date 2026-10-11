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
