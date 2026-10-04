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
