"""Tests for VietnameseQueryTranslator and SearchTool Vietnamese -> English query bridge."""
from __future__ import annotations

import numpy as np
import pandas as pd

from package.corpus import ItemCorpus
from package.embeddings import SparseBM25Index, TextEncoder, VectorStore
from package.tools.retrieval import SearchTool
from package.tools.retrieval.vietnamese_query_translator import VietnameseQueryTranslator


def test_vietnamese_query_translator_handles_diacritics_nodiac_and_english_passthrough():
    tr = VietnameseQueryTranslator()

    res_vi = tr.translate("tìm tai nghe chống ồn bluetooth sony dưới 2 triệu")
    assert res_vi["is_vietnamese"] is True
    assert "noise" in res_vi["translated"] and "headphones" in res_vi["translated"] and "sony" in res_vi["translated"]
    assert "toi" not in res_vi["translated"] and "duoi" not in res_vi["translated"]

    res_nodiac = tr.translate("ban phim co yen tinh van phong logitech")
    assert res_nodiac["is_vietnamese"] is True
    assert "mechanical" in res_nodiac["translated"] and "keyboard" in res_nodiac["translated"] and "logitech" in res_nodiac["translated"]

    res_en = tr.translate("quiet mechanical keyboard logitech")
    assert res_en["is_vietnamese"] is False
    assert res_en["translated"] == "quiet mechanical keyboard logitech"


def test_search_tool_translates_vietnamese_query_for_bm25_and_dense():
    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "domain": ["Electronics", "Electronics"],
        "title": ["Sony Wireless Noise Cancelling Headphones", "Wired USB Mouse"],
        "store": ["Sony", "Generic"],
        "first_seen_ts": [1, 1],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    bm25 = SparseBM25Index.build_from_documents(
        ["Electronics::a", "Electronics::b"],
        ["Sony Wireless Noise Cancelling Headphones", "Wired USB Mouse"],
        min_df=1,
    )
    store = VectorStore(["Electronics::a", "Electronics::b"], np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    seen_texts = []
    def fake_enc(texts):
        seen_texts.extend(texts)
        return np.array([[1.0, 0.0] if "headphones" in t else [0.0, 1.0] for t in texts], dtype=np.float32)
    enc = TextEncoder(fake_enc, dimension=2)

    tool = SearchTool(corpus, vector_store=store, query_encoder=enc, bm25_index=bm25, translate_vietnamese=True)
    res = tool(query="tìm tai nghe chống ồn bluetooth sony", limit=2)
    assert res.ok
    assert res.data["retrieval"] == "rrf"
    assert "headphones" in res.data["translated_query"]
    assert res.data["candidates"][0]["item_id"] == "Electronics::a"
    assert any("headphones" in t for t in seen_texts)
