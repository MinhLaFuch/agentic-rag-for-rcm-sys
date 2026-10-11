"""Contract tests for SemanticSearchTool (lexical SQLite FTS5 / BM25 search - NOT embeddings)."""

import pandas as pd
import pytest

from package.tools import ItemCorpus, SemanticSearchTool
from package.tools.retrieval._helper import _tokenize


@pytest.mark.parametrize("query, tokens", [
    ("quiet keyboard", ["quiet", "keyboard"]),
    ("USB-C cable", ["usb-c", "cable"]),
    ("keyboard keyboard KEYBOARD", ["keyboard"]),  # duplicates collapse, order kept
    ("the best cheap keyboard for me", ["keyboard"]),  # stopwords dropped
    ("keyboard under 50 dollars", ["keyboard", "dollars"]),  # 'under' stopword, pure number dropped
    ("123 4.5 1,000 $20", []),  # numbers only
    ("4k tv 2tb ssd 1080p 20-inch", ["4k", "tv", "2tb", "ssd", "1080p", "20-inch"]),  # digit-leading model tokens kept whole
    ('say "hello" OR AND NOT (x*)', ["say", "hello", "not"]),  # quotes / FTS operators are just punctuation
    ("a b c", []),  # single letters
    ("", []),
])
def test_tokenizer(query, tokens):
    assert _tokenize(query) == tokens


def test_tokenizer_caps_length():
    from package.tools._limits import SEMANTIC_MAX_QUERY_TOKENS

    assert len(_tokenize(" ".join(f"word{i}" for i in range(100)))) == SEMANTIC_MAX_QUERY_TOKENS


def test_non_ascii_query_is_rejected_with_a_clear_message(world):
    result = SemanticSearchTool(world.corpus)(query="bàn phím")
    assert not result.ok and "ASCII" in result.error and "Translate" in result.error


@pytest.mark.parametrize("query", ["", "   ", "the and or", "123 456", None, 5])
def test_unsearchable_queries_are_clean_errors(world, query):
    assert not SemanticSearchTool(world.corpus)(query=query).ok


def test_best_match_first_and_scores_descend(world):
    result = SemanticSearchTool(world.corpus)(query="wireless gaming mouse")
    cands = result.data["candidates"]
    assert cands[0]["item_id"] == "Games::B2"  # only title with all three words
    assert [c["score"] for c in cands] == sorted((c["score"] for c in cands), reverse=True)
    assert result.data["query_tokens"] == ["wireless", "gaming", "mouse"]


def test_matches_fields_other_than_title(world):
    tool = SemanticSearchTool(world.corpus)
    assert [c["item_id"] for c in tool(query="Hape").data["candidates"]] == ["Toys::E5", "Toys::A1"]  # store; tie -> rating_number desc
    assert {c["item_id"] for c in tool(query="keyboards").data["candidates"]} == {"Games::A1"}  # category list entry (+stemming)
    assert {c["item_id"] for c in tool(query="audio").data["candidates"]} == {"Games::C3"}


def test_no_match_is_ok_and_empty(world):
    result = SemanticSearchTool(world.corpus)(query="submarine")
    assert result.ok and result.data["candidates"] == [] and result.data["total_matches"] == 0


def test_domain_filter_restricts_results(world):
    tool = SemanticSearchTool(world.corpus)
    games = tool(query="game", filters={"domain": "Games"})
    toys = tool(query="game", filters={"domain": "Toys"})
    assert {c["domain"] for c in games.data["candidates"]} <= {"Games"}
    assert [c["item_id"] for c in toys.data["candidates"]] == ["Toys::A1"]  # 'Wooden Puzzle Game'


def test_ties_are_broken_deterministically_by_rating_number_then_item_id():
    meta = pd.DataFrame({
        "parent_asin": ["z", "y", "x", "w"], "domain": "D", "title": ["same words"] * 4,
        "rating_number": [10, 10, 99, None],
    })
    tool = SemanticSearchTool(ItemCorpus.from_dataframe(meta))
    first = [c["item_id"] for c in tool(query="same words").data["candidates"]]
    assert first == ["D::x", "D::y", "D::z", "D::w"]  # 99, then 10 (y<z by id), NULL last
    assert first == [c["item_id"] for c in tool(query="same words").data["candidates"]]


def test_missing_metadata_does_not_break_search():
    meta = pd.DataFrame({"parent_asin": ["a", "b"], "domain": "D", "title": [None, "Cafe Table"], "store": ["Zed", None]})
    tool = SemanticSearchTool(ItemCorpus.from_dataframe(meta))
    assert [c["item_id"] for c in tool(query="zed").data["candidates"]] == ["D::a"]
    assert [c["item_id"] for c in tool(query="cafe").data["candidates"]] == ["D::b"]


def test_accented_documents_are_found_by_ascii_queries():
    meta = pd.DataFrame({"parent_asin": ["a"], "domain": "D", "title": ["Café Crème"]})
    assert [c["item_id"] for c in SemanticSearchTool(ItemCorpus.from_dataframe(meta))(query="cafe creme").data["candidates"]] == ["D::a"]


def test_limit_total_matches_and_truncation(world):
    result = SemanticSearchTool(world.corpus)(query="gaming game games toys", limit=1)
    assert len(result.data["candidates"]) == 1
    assert result.data["total_matches"] >= 2 and result.data["truncated"] is True


@pytest.mark.parametrize("limit", [0, -1, 10**9, 1.5, "3", True])
def test_limit_validation(world, limit):
    assert not SemanticSearchTool(world.corpus)(query="game", limit=limit).ok


def test_candidates_have_unique_namespaced_ids_usable_by_other_tools(world):
    cands = SemanticSearchTool(world.corpus)(query="gaming game games toys keyboard").data["candidates"]
    item_ids = [c["item_id"] for c in cands]
    assert len(item_ids) == len(set(item_ids)) and all(i in world.item2id for i in item_ids)


def test_description_says_lexical_not_embedding():
    import package.tools.retrieval.semantic_search_tool as mod

    doc = mod.__doc__ or ""
    assert "lexical" in doc and "BM25" in doc and "not embedding" in doc
