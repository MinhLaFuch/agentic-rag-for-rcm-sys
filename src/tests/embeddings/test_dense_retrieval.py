"""
Tests for package.embeddings and SearchTool hybrid retrieval.
"""

from __future__ import annotations

import numpy as np
import pytest

from package.corpus import ItemCorpus
from package.embeddings import TextEncoder, VectorStore
from package.tools.retrieval.search_tool import SearchTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


def test_vector_store_search_and_persistence(tmp_path):
    item_ids = [VG_A, VG_B, VG_C]
    # Distinct orthogonal vectors
    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32)

    store = VectorStore(item_ids=item_ids, embeddings=embeddings)
    assert len(store) == 3
    assert store.dimension() == 3

    # Query matching VG_A exactly
    results = store.search(np.array([1.0, 0.0, 0.0]), top_k=2)
    assert len(results) == 2
    assert results[0][0] == VG_A
    assert pytest.approx(results[0][1], 1e-5) == 1.0

    # Restricted candidate search
    restricted = store.search(np.array([1.0, 0.0, 0.0]), top_k=2, candidate_ids=[VG_B, VG_C])
    assert len(restricted) == 2
    assert VG_A not in [r[0] for r in restricted]

    # Test save and load
    save_file = tmp_path / "test_store.npz"
    store.save(save_file)
    loaded = VectorStore.load(save_file)
    assert len(loaded) == 3
    assert loaded.item_ids.tolist() == item_ids


def test_text_encoder_contract():
    # Valid callable
    encoder = TextEncoder(lambda texts: [[1.0, 0.0] for _ in texts], dimension=2)
    vecs = encoder.encode(["hello", "world"])
    assert vecs.shape == (2, 2)

    # Invalid callable
    with pytest.raises(TypeError):
        TextEncoder("not_callable")

    # Invalid input text type
    with pytest.raises(TypeError):
        encoder.encode("single_string_instead_of_sequence")

    # Dimension mismatch
    wrong_dim_encoder = TextEncoder(lambda texts: [[1.0, 0.0, 0.0] for _ in texts], dimension=2)
    with pytest.raises(ValueError):
        wrong_dim_encoder.encode(["test"])


def test_search_tool_validation(corpus):
    # vector_store not VectorStore
    with pytest.raises(TypeError, match="vector_store must be a VectorStore or None"):
        SearchTool(corpus, vector_store="invalid")

    # vector_store set but query_encoder missing
    store = VectorStore([VG_A], np.array([[1.0, 0.0]]))
    with pytest.raises(ValueError, match="query_encoder is required when vector_store is configured"):
        SearchTool(corpus, vector_store=store, query_encoder=None)

    # invalid rrf_k
    encoder = TextEncoder(lambda texts: [[1.0, 0.0] for _ in texts], dimension=2)
    with pytest.raises(ValueError, match="rrf_k must be a positive integer"):
        SearchTool(corpus, vector_store=store, query_encoder=encoder, rrf_k=0)


def test_search_tool_lexical_fallback(corpus):
    tool = SearchTool(corpus)
    res = tool(query="video game")
    assert res.ok
    data = res.data
    assert "candidates" in data
    assert data.get("retrieval") is None  # standard lexical mode
    assert len(data["candidates"]) > 0


def test_search_tool_hybrid_rrf(corpus):
    # All 5 items from tools_helpers corpus
    item_ids = [VG_A, VG_B, VG_C, EL_A, EL_D]
    # Make EL_A strongly match the query vector [0, 1]
    embeddings = np.array([
        [1.0, 0.0],  # VG_A
        [1.0, 0.0],  # VG_B
        [1.0, 0.0],  # VG_C
        [0.0, 1.0],  # EL_A (dense top match)
        [0.0, 1.0],  # EL_D
    ], dtype=np.float32)

    store = VectorStore(item_ids=item_ids, embeddings=embeddings)
    encoder = TextEncoder(lambda texts: [[0.0, 1.0] for _ in texts], dimension=2)

    tool = SearchTool(corpus, vector_store=store, query_encoder=encoder, rrf_k=60)
    # Query for "video game" - BM25 matches VG_A, while dense matches EL_A, EL_D
    res = tool(query="video game", limit=5)
    assert res.ok
    data = res.data

    assert data["retrieval"] == "rrf"
    assert data["dense_candidates"] > 0
    candidate_ids = [c["item_id"] for c in data["candidates"]]

    # Fused candidates should contain both BM25 and dense matches
    assert VG_A in candidate_ids
    assert EL_A in candidate_ids or EL_D in candidate_ids

    # Each candidate must have retrieval_sources and score
    for c in data["candidates"]:
        assert "retrieval_sources" in c
        assert "score" in c
        assert c["score"] > 0.0


def test_search_tool_hybrid_with_filters(corpus):
    item_ids = [VG_A, VG_B, VG_C, EL_A, EL_D]
    embeddings = np.ones((5, 2), dtype=np.float32)
    store = VectorStore(item_ids=item_ids, embeddings=embeddings)
    encoder = TextEncoder(lambda texts: [[1.0, 1.0] for _ in texts], dimension=2)

    tool = SearchTool(corpus, vector_store=store, query_encoder=encoder)
    # Filter only domain = Video_Games
    res = tool(query="game", filters={"domain": "Video_Games"}, limit=5)
    assert res.ok
    for c in res.data["candidates"]:
        assert c["domain"] == "Video_Games"

