"""Tests for Phase A1 (SparseBM25Index + SQLite builder + SearchTool/HistoryQueryRetriever integration)
and Phase A2 (persisted FAISS HNSW index build/load/checksum verification).
"""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from package.corpus import ItemCorpus
from package.embeddings import SparseBM25Index, TextEncoder, VectorStore
from package.tools.retrieval import SearchTool
from package.tools.retrieval.history_query_retriever import HistoryQueryRetriever
from scripts.data_pipeline.build_sparse_bm25_index import build_sparse_bm25_from_sqlite


def test_sparse_bm25_build_save_load_filtering_and_tamper_guard(tmp_path):
    ids = ["D::a", "D::b", "D::c", "D::d"]
    docs = [
        "quiet mechanical gaming keyboard rgb",
        "wireless gaming mouse ergonomic",
        "quiet keyboard office compact",
        "usb cable charger adapter",
    ]
    idx = SparseBM25Index.build_from_documents(ids, docs, min_df=1)
    out_dir = tmp_path / "bm25_art"
    manifest = idx.save(out_dir, metadata={"corpus_sha256": "deadbeef"})
    assert manifest["status"] == "complete" and manifest["num_items"] == 4

    loaded = SparseBM25Index.load(out_dir, expected_corpus_sha256="deadbeef")
    assert len(loaded) == 4

    # Eligibility + seen exclusion happen strictly before Top-K.
    valid = loaded.eligible_mask(["D::a", "D::c", "D::d"])
    res = loaded.search("quiet keyboard", valid_mask=valid, seen={"D::a"}, limit=2)
    assert res == ["D::c"]

    # Corpus hash mismatch must fail.
    with pytest.raises(ValueError, match="corpus_sha256"):
        SparseBM25Index.load(out_dir, expected_corpus_sha256="wronghash")

    # Tampering with vocab.json must fail checksum check.
    (out_dir / "vocab.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        SparseBM25Index.load(out_dir)


def test_build_sparse_bm25_from_sqlite_and_search_tool_integration(tmp_path):
    db_path = tmp_path / "corpus.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE items (item_id TEXT PRIMARY KEY, domain TEXT NOT NULL, original_item_id TEXT, "
        "first_seen_ts INTEGER, title TEXT, store TEXT, price REAL, average_rating REAL, "
        "rating_number REAL, main_category TEXT)"
    )
    conn.execute("CREATE TABLE item_categories (item_id TEXT, category TEXT)")
    rows = [
        ("Video_Games::a", "Video_Games", "a", 1, "quiet mechanical keyboard", "Alpha", 45.0, 4.5, 100, "Peripherals"),
        ("Video_Games::b", "Video_Games", "b", 1, "wireless gaming mouse", "Beta", 90.0, 4.7, 200, "Peripherals"),
        ("Video_Games::c", "Video_Games", "c", 1, "quiet keyboard pro", "Alpha", 120.0, 4.2, 50, "Peripherals"),
    ]
    conn.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO item_categories VALUES (?,?)", [("Video_Games::a", "Keyboards"), ("Video_Games::c", "Keyboards")])
    conn.commit()
    conn.close()

    bm25_dir = tmp_path / "bm25_out"
    manifest = build_sparse_bm25_from_sqlite(db_path, bm25_dir, tag="toy", min_df=1)
    assert manifest["num_items"] == 3
    bm25_index = SparseBM25Index.load(bm25_dir)

    meta = pd.DataFrame({
        "parent_asin": ["a", "b", "c"],
        "domain": ["Video_Games"] * 3,
        "title": ["quiet mechanical keyboard", "wireless gaming mouse", "quiet keyboard pro"],
        "store": ["Alpha", "Beta", "Alpha"],
        "price": [45.0, 90.0, 120.0],
        "first_seen_ts": [1, 1, 1],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SearchTool(corpus, bm25_index=bm25_index)
    res = tool(query="quiet keyboard", filters={"price_max": 60.0}, limit=5)
    assert res.ok and [r["item_id"] for r in res.data["candidates"]] == ["Video_Games::a"]

    # HistoryQueryRetriever with bm25_index does not invoke SearchTool.
    store = VectorStore(["Video_Games::a", "Video_Games::b", "Video_Games::c"], np.eye(3, dtype=np.float32))
    enc = TextEncoder(lambda texts: np.tile(np.array([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1)), dimension=3)
    def fail_search(*a, **k):
        raise AssertionError("SearchTool must not be called when bm25_index is provided")
    retriever = HistoryQueryRetriever(
        fail_search, store, enc, eligible_ids={"Video_Games::a", "Video_Games::b", "Video_Games::c"},
        bm25_index=bm25_index,
    )
    out = retriever.retrieve([{"item_id": "Video_Games::c", "title": "quiet keyboard", "timestamp": 1}],
                             seen={"Video_Games::c"}, limit=2)
    assert out["bm25"] == ["Video_Games::a"]


def test_persisted_ann_index_build_load_and_guards(tmp_path):
    pytest.importorskip("faiss")
    import hashlib
    from scripts.data_pipeline.build_ann_index import build_and_save_ann_index
    from scripts.evaluation.ann_validation import build_ann_search

    rng = np.random.default_rng(7)
    vecs = rng.standard_normal((250, 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = np.array([f"Video_Games::i{i:03d}" for i in range(250)], dtype="U32")
    emb_dir = tmp_path / "emb"
    emb_dir.mkdir()
    np.save(emb_dir / "vectors.npy", vecs)
    np.save(emb_dir / "item_ids.npy", ids)
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    (emb_dir / "manifest.json").write_text(json.dumps({
        "format_version": 2, "status": "complete", "kind": "full_catalog_embeddings",
        "partial_catalog": False, "count": 250, "catalog_count": 250, "dimension": 8,
        "build_id": "bid123",
        "files": {
            "vectors.npy": {"sha256": sha(emb_dir / "vectors.npy")},
            "item_ids.npy": {"sha256": sha(emb_dir / "item_ids.npy")},
        },
    }), encoding="utf-8")

    ann_dir = tmp_path / "ann_sq8"
    manifest = build_and_save_ann_index(emb_dir, ann_dir, kind="hnsw_sq8", m=8, ef_search=128, train_size=250)
    assert manifest["status"] == "complete" and manifest["embedding_build_id"] == "bid123"

    store = VectorStore(ids.tolist(), vecs)
    search = build_ann_search(store, {
        "index": "hnsw_sq8", "m": 8, "ef_search": 128, "warmup_queries": 5, "warmup_limit": 10,
        "index_path": str(ann_dir), "expected_embedding_build_id": "bid123",
    })
    assert search.build_info["source"] == "persisted"
    valid = np.ones(250, dtype=bool)
    res = search(vecs[0], valid, {str(ids[0])}, 5)
    assert len(res) == 5 and str(ids[0]) not in res

    with pytest.raises(ValueError, match="embedding_build_id"):
        build_ann_search(store, {
            "index": "hnsw_sq8", "m": 8, "ef_search": 128,
            "index_path": str(ann_dir), "expected_embedding_build_id": "other_bid",
        })
