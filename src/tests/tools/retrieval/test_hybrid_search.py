import numpy as np
import pandas as pd

from package.embeddings import TextEncoder, VectorStore
from package.corpus import ItemCorpus
from package.tools.retrieval import SearchTool


def test_vector_store_normalizes_and_searches_deterministically():
    store = VectorStore(["D::b", "D::a", "D::c"], np.asarray([[0, 2], [0, 1], [1, 0]], dtype=np.float32))
    assert store.dimension == 2
    assert [item for item, _ in store.search(np.asarray([0, 1], dtype=np.float32), 3)] == ["D::a", "D::b", "D::c"]
    assert [item for item, _ in store.search(np.asarray([0, 1], dtype=np.float32), 3, {"D::c"})] == ["D::c"]


def test_text_encoder_validates_callable_output():
    encoder = TextEncoder(lambda texts: np.ones((len(texts), 3), dtype=np.float32), dimension=3)
    assert encoder.encode(["one", "two"]).shape == (2, 3)


def test_search_tool_keeps_bm25_behavior_without_vectors(world):
    result = SearchTool(world.corpus)(query="wireless gaming mouse")
    assert result.ok and result.data["candidates"][0]["item_id"] == "Games::B2"
    assert "retrieval" not in result.data


def test_search_tool_rrf_fuses_dense_and_lexical_with_filters():
    meta = pd.DataFrame({
        "parent_asin": ["a", "b", "c"], "domain": ["D"] * 3,
        "title": ["quiet keyboard", "wireless mouse", "quiet mouse"],
        "store": ["One", "Two", "Three"],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    store = VectorStore(["D::a", "D::b", "D::c"], np.asarray([[1, 0], [0, 1], [0.8, 0.2]], dtype=np.float32))
    encoder = TextEncoder(lambda texts: np.tile(np.asarray([[1, 0]], dtype=np.float32), (len(texts), 1)), dimension=2)
    result = SearchTool(corpus, vector_store=store, query_encoder=encoder)(query="mouse", limit=3)
    assert result.ok and result.data["retrieval"] == "rrf"
    assert {row["item_id"] for row in result.data["candidates"]} == {"D::a", "D::b", "D::c"}
    assert any(row["retrieval_sources"] == ["dense"] for row in result.data["candidates"])
    filtered = SearchTool(corpus, vector_store=store, query_encoder=encoder)(query="mouse", filters={"store": "Two"}, limit=3)
    assert [row["item_id"] for row in filtered.data["candidates"]] == ["D::b"]
