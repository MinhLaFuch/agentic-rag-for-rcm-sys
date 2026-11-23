"""Runtime smoke & regression tests for Step 6 (valid query, cold user, empty query,
missing metadata, tight filters, bad artifact, and unavailable encoder fallback/strict modes).
"""
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
import yaml

from package.agents import build_tools
from package.config import load_config
from package.corpus import ItemCorpus
from package.embeddings import TextEncoder, VectorStore
from package.tools.base import ToolCallLogger
from package.tools.retrieval import SearchTool
from package.tools.scoring import HybridScorer


def _fixture_world():
    meta = pd.DataFrame({
        "parent_asin": ["a", "b", "c", "d"],
        "domain": ["Video_Games", "Video_Games", "Electronics", "Electronics"],
        "title": ["quiet mechanical keyboard", "wireless gaming mouse", None, "usb cable"],
        "store": ["Alpha", "Beta", None, "Alpha"],
        "price": [45.0, 120.0, None, 10.0],
        "first_seen_ts": [1, 1, 1, 1],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    ids = ["Video_Games::a", "Video_Games::b", "Electronics::c", "Electronics::d"]
    vectors = np.asarray([
        [1.0, 0.0],
        [0.0, 1.0],
        [0.8, 0.2],
        [0.2, 0.8],
    ], dtype=np.float32)
    store = VectorStore(ids, vectors)
    encoder = TextEncoder(lambda texts: np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1)), dimension=2)
    knn = SimpleNamespace(
        scores=np.array([1.0, 1.0, 1.0, 3.0], dtype=np.float32),
        num_items=4,
        user_items=sparse.csr_matrix([
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32),
        similarity=sparse.csr_matrix([
            [0.0, 0.2, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
        ], dtype=np.float32),
    )
    user2id = {"u_warm": 0, "u_cold": 1}
    item2id = {item: idx for idx, item in enumerate(ids)}
    interactions = pd.DataFrame({"user_idx": [0], "item_idx": [0], "timestamp": [1]})
    return corpus, store, encoder, knn, user2id, item2id, interactions, ids


def test_runtime_smoke_valid_query_cold_user_missing_metadata_and_tight_filters():
    corpus, store, encoder, knn, user2id, item2id, interactions, ids = _fixture_world()
    scorer = HybridScorer(knn, popularity_weight=4.0)
    tools = build_tools(
        knn, scorer, user2id, item2id, interactions, corpus,
        logger=ToolCallLogger(), vector_store=store, query_encoder=encoder, fallback_to_bm25=True,
    )

    # 1. Valid query -> hybrid RRF runs and proves source attribution.
    res = tools.search(query="mouse", limit=4)
    assert res.ok and res.data["retrieval"] == "rrf" and res.data["dense_backend"] == "exact"
    assert res.data["dense_candidates"] >= 1
    assert any("dense" in row["retrieval_sources"] for row in res.data["candidates"])

    # 2. Cold user (no history) ranked with HybridScorer(w=4.0).
    ranked = tools.reco(user_id="u_cold", candidates=ids, top_k=2, exclude_seen=True)
    assert ranked.ok and len(ranked.data["ranked"]) == 2
    assert ranked.data["ranked"][0]["item_id"] == "Electronics::d"

    # 3. Empty / unsearchable query -> clean ToolInputError, never crashes.
    empty_res = tools.search(query="   ", limit=3)
    assert not empty_res.ok and "non-empty" in empty_res.error

    # 4. Missing metadata item (Electronics::c has None title/store/price) does not break dense/RRF search.
    assert any(row["item_id"] == "Electronics::c" for row in res.data["candidates"])

    # 5. Tight filters + seen exclusion strictly enforced across BM25 and dense results.
    tight = tools.search(
        query="keyboard",
        filters={"domain": "Video_Games", "price_max": 50.0, "exclude_item_ids": ["Video_Games::b"]},
        limit=4,
    )
    assert tight.ok
    assert [r["item_id"] for r in tight.data["candidates"]] == ["Video_Games::a"]

    impossible = tools.search(query="keyboard", filters={"price_max": 1.0}, limit=4)
    assert impossible.ok and impossible.data["candidates"] == []


def test_runtime_encoder_unavailable_strict_vs_fallback():
    corpus, store, _, _, _, _, _, _ = _fixture_world()
    def broken_encode(texts):
        raise RuntimeError("model weights offline")

    # Benchmark/strict mode (default fallback_to_bm25=False): MUST fail, never silently report BM25 as hybrid.
    strict_tool = SearchTool(corpus, vector_store=store, query_encoder=broken_encode, fallback_to_bm25=False)
    with pytest.raises(RuntimeError, match="model weights offline"):
        strict_tool(query="keyboard", limit=3)

    # Runtime fallback mode (fallback_to_bm25=True): explicitly returns retrieval='bm25_fallback' + reason.
    fallback_tool = SearchTool(corpus, vector_store=store, query_encoder=broken_encode, fallback_to_bm25=True)
    fb_res = fallback_tool(query="keyboard", limit=3)
    assert fb_res.ok
    assert fb_res.data["retrieval"] == "bm25_fallback"
    assert "model weights offline" in fb_res.data["fallback_reason"]
    assert fb_res.data["candidates"][0]["item_id"] == "Video_Games::a"


def test_runtime_dense_search_ann_callback():
    corpus, store, encoder, _, _, _, _, _ = _fixture_world()
    called = []
    def fake_ann(vec, k):
        called.append((vec.shape, k))
        return [("Video_Games::a", 0.99)]
    tool = SearchTool(corpus, dense_search=fake_ann, query_encoder=encoder)
    res = tool(query="mouse", limit=2)
    assert res.ok and res.data["retrieval"] == "rrf" and res.data["dense_backend"] == "ann"
    assert len(called) == 1


def test_runtime_winning_overlay_validates_against_schema(monkeypatch):
    overlay = (Path(__file__).resolve().parents[3] / "configs" / "profiles" /
               "multi_domain_v2_audit_20261030.runtime_winning.overlay.yaml")
    monkeypatch.setenv(
        "CONFIG_OVERLAY_PATH",
        str(overlay),
    )
    cfg = load_config("agent/demo")["demo"]
    assert cfg["scorer_mode"] == "hybrid"
    assert cfg["scorer_popularity_weight"] == 4.0
    assert cfg["retrieval_mode"] == "hybrid"
    assert cfg["fallback_to_bm25"] is True


def test_dense_refills_after_domain_filter_discards_initial_neighbors():
    corpus, _, encoder, *_ = _fixture_world()
    calls = []

    def ann(vec, k):
        calls.append(k)
        return [(iid, 1.0) for iid in [
            "Video_Games::a", "Video_Games::b", "Electronics::d",
        ][:k]]

    tool = SearchTool(corpus, dense_search=ann, query_encoder=encoder)
    result = tool(query="unmatchedword", filters={"domain": "Electronics"}, limit=1)
    assert result.ok
    assert calls == [2, 4]
    assert [r["item_id"] for r in result.data["candidates"]] == ["Electronics::d"]
    assert result.data["dense_fetch_limited"] is False


def test_live_backend_bad_artifact_fallback_and_strict(tmp_path, monkeypatch):
    from package.demo.backend import live_backend as lb_mod
    corpus, _, _, _, user2id, item2id, _, _ = _fixture_world()
    train = pd.DataFrame({"user_idx": [0, 0], "item_idx": [0, 1], "timestamp": [1, 2]})
    val = pd.DataFrame({"user_idx": [0, 1], "item_idx": [2, 3], "timestamp": [3, 4]})
    test = val.assign(timestamp=5)
    fake_paths = SimpleNamespace(
        tag="toy", splits_dir=tmp_path, mapped_dir=tmp_path,
        corpus_dir=tmp_path, corpus_path=tmp_path / "missing.sqlite",
    )
    monkeypatch.setattr(lb_mod, "get_data_paths", lambda **k: fake_paths)
    monkeypatch.setattr(lb_mod, "build_meta_files", lambda *a, **k: [])
    monkeypatch.setattr(lb_mod, "load_splits", lambda *a, **k: (train, val, test))
    monkeypatch.setattr(lb_mod, "load_mappings", lambda *a, **k: (user2id, item2id))
    monkeypatch.setattr(lb_mod, "build_corpus", lambda *a, **k: (corpus, None, 1.0, {"build": 0.01}))

    missing_art = tmp_path / "corrupt_or_missing_artifact"

    # Fallback enabled -> logs explicit bm25_fallback provenance and activates HybridScorer(w=4.0).
    overlay_fb = tmp_path / "ov_fb.yaml"
    overlay_fb.write_text(yaml.safe_dump({"agent/demo": {"demo": {
        "scorer_mode": "hybrid", "scorer_popularity_weight": 4.0,
        "retrieval_mode": "hybrid", "embeddings_path": str(missing_art), "fallback_to_bm25": True,
    }}}), encoding="utf-8")
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_fb))
    backend = lb_mod.LiveBackend(use_prebuilt=False)
    backend.initialize(initialize_planner=False)
    assert backend._scorer_provenance["name"] == "hybrid_item_knn_w4"
    assert backend._retrieval_provenance["requested"] == "hybrid"
    assert backend._retrieval_provenance["active"] == "bm25_fallback"
    assert backend._retrieval_provenance["reason"]

    # Fallback disabled -> MUST raise rather than silently serving BM25 under hybrid label.
    overlay_strict = tmp_path / "ov_strict.yaml"
    overlay_strict.write_text(yaml.safe_dump({"agent/demo": {"demo": {
        "scorer_mode": "hybrid", "scorer_popularity_weight": 4.0,
        "retrieval_mode": "hybrid", "embeddings_path": str(missing_art), "fallback_to_bm25": False,
    }}}), encoding="utf-8")
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_strict))
    strict_backend = lb_mod.LiveBackend(use_prebuilt=False)
    with pytest.raises(RuntimeError, match="Hybrid retrieval initialization failed"):
        strict_backend.initialize(initialize_planner=False)
