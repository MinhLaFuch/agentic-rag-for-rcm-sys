import pandas as pd
import pytest

from package.tools import ItemCorpus, SemanticSearchTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


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


def test_search_ranks_best_text_match_first(kb_corpus):
    result = SemanticSearchTool(kb_corpus)(query="quiet mechanical keyboard coding")
    assert result.ok
    assert _ids(result)[0] == "Electronics::k1"
    scores = [c["score"] for c in result.data["candidates"]]
    assert scores == sorted(scores, reverse=True) and scores[0] > 0


def test_search_applies_structured_filters(kb_corpus):
    tool = SemanticSearchTool(kb_corpus)
    cheap = tool(query="keyboard", filters={"price_max": 20})
    assert _ids(cheap) == ["Electronics::k3"]
    games = tool(query="keyboard", filters={"domain": "Video_Games"})
    assert _ids(games) == ["Video_Games::g1"]


def test_search_stems_words(kb_corpus):
    assert "Electronics::k2" in _ids(SemanticSearchTool(kb_corpus)(query="mouse"))
    assert "Electronics::k1" in _ids(SemanticSearchTool(kb_corpus)(query="keyboards"))


def test_search_output_feeds_other_tools(kb_corpus):
    from package.tools.base import candidate_ids

    result = SemanticSearchTool(kb_corpus)(query="keyboard")
    assert candidate_ids(result.data["candidates"])  # accepted as-is by RecoModelTool


def test_search_no_match_returns_empty_not_error(kb_corpus):
    result = SemanticSearchTool(kb_corpus)(query="submarine")
    assert result.ok and result.data["candidates"] == []


@pytest.mark.parametrize("bad", ["", "   ", "the a of", "!!!"])
def test_search_rejects_queries_without_words(kb_corpus, bad):
    result = SemanticSearchTool(kb_corpus)(query=bad)
    assert not result.ok


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


def test_search_on_shared_fixture_corpus(corpus):
    # the 5-item corpus used by the other tool tests also gets an index
    ids = _ids(SemanticSearchTool(corpus)(query="accessories"))
    assert {VG_C, EL_A, EL_D} <= set(ids)


def test_search_tie_breaker_by_rating_number(kb_corpus):
    """Test that when BM25 scores tie, ranking uses rating_number DESC."""
    # Add items with same title but different rating_number
    from package.tools import ItemCorpus
    meta_tie = pd.DataFrame(
        {
            "parent_asin": ["t1", "t2"],
            "domain": ["Electronics", "Electronics"],
            "title": ["Test Item", "Test Item"],
            "price": [10.0, 10.0],
            "average_rating": [4.0, 4.0],
            "rating_number": [100, 500],  # t2 should rank higher
            "store": ["StoreA", "StoreA"],
            "main_category": ["Test", "Test"],
            "categories": [["Test"], ["Test"]],
        }
    )
    corpus_tie = ItemCorpus.from_dataframe(meta_tie)
    result = SemanticSearchTool(corpus_tie)(query="test item")
    ids = _ids(result)
    assert ids[0] == "Electronics::t2"  # Higher rating_number wins


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


def test_search_pure_numbers_dropped(kb_corpus):
    """Test that pure numbers are dropped from tokenization."""
    result = SemanticSearchTool(kb_corpus)(query="keyboard 123 456")
    # Should not error, and should still find keyboard
    assert result.ok
    assert "123" not in result.data["query_tokens"]
    assert "456" not in result.data["query_tokens"]


def test_search_drops_under_over_below(kb_corpus):
    """Test that 'under', 'over', 'below' are dropped as stopwords."""
    result = SemanticSearchTool(kb_corpus)(query="keyboard under 50 dollars")
    assert "under" not in result.data["query_tokens"]
    assert "50" not in result.data["query_tokens"]  # pure number also dropped


def test_search_non_ascii_raises_error(kb_corpus):
    """Test that non-ASCII queries raise ToolInputError."""
    tool = SemanticSearchTool(kb_corpus)
    result_vietnamese = tool(query="bàn phím")
    assert not result_vietnamese.ok
    assert "ASCII" in result_vietnamese.error
    assert "Translate" in result_vietnamese.error


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


def test_search_duplicate_categories_all(kb_corpus):
    """Test that duplicate categories in categories_all are handled correctly."""
    tool = SemanticSearchTool(kb_corpus)
    result = tool(query="keyboard", filters={"categories_all": ["Keyboards", "Keyboards"]})
    # Should not error, and should find keyboard items
    assert result.ok
    assert len(result.data["candidates"]) > 0


def test_search_long_exclude_item_ids(kb_corpus):
    """Test that a long list of exclude_item_ids works correctly."""
    tool = SemanticSearchTool(kb_corpus)
    # Exclude 3 out of 4 items
    result = tool(query="keyboard", filters={"exclude_item_ids": ["Electronics::k1", "Electronics::k2", "Electronics::k3"]})
    assert _ids(result) == ["Video_Games::g1"]


def test_search_total_matches_in_output(kb_corpus):
    """Test that total_matches is included in output."""
    result = SemanticSearchTool(kb_corpus)(query="keyboard")
    assert "total_matches" in result.data
    assert isinstance(result.data["total_matches"], int)
    assert result.data["total_matches"] >= len(result.data["candidates"])
