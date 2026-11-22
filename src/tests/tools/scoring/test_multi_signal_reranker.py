"""Tests for DomainCategoryPopularity (B1.2) and MultiSignalReranker (Phase C)."""
from __future__ import annotations

from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from package.corpus import ItemCorpus
from package.tools import RankTool
from package.tools.retrieval.domain_category_popularity import DomainCategoryPopularity
from package.tools.scoring import MultiSignalReranker


class _DummyEstimator:
    def predict_proba(self, X):
        p = np.clip(0.1 + X[:, 4] * 10.0 + X[:, 14] * 0.5, 0.0, 1.0)
        return np.column_stack([1.0 - p, p])


def test_domain_category_popularity_filters_seen_and_computes_affinities():
    meta = pd.DataFrame({
        "parent_asin": ["a", "b", "c", "d", "e"],
        "domain": ["Video_Games", "Video_Games", "Video_Games", "Electronics", "Electronics"],
        "main_category": ["Consoles", "Consoles", "Games", "Audio", "Audio"],
        "title": ["t1", "t2", "t3", "t4", "t5"],
        "first_seen_ts": [1, 1, 1, 1, 1],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    ids = ["Video_Games::a", "Video_Games::b", "Video_Games::c", "Electronics::d", "Electronics::e"]
    dcp = DomainCategoryPopularity.from_corpus(corpus, ids, ids)

    # User bought Video_Games::a (Consoles) -> recommends Video_Games::b first (same cat), then Video_Games::c (same domain), never seen or Electronics
    recs = dcp.recommend(["Video_Games::a"], limit=3)
    assert recs == ["Video_Games::b", "Video_Games::c"]
    assert dcp.recommend([], limit=3) == []

    same_d, dom_aff, cat_aff = dcp.affinity_features(["Video_Games::a"], ["Video_Games::b", "Video_Games::c", "Electronics::d"])
    assert list(same_d) == [1.0, 1.0, 0.0]
    assert list(dom_aff) == [1.0, 1.0, 0.0]
    assert list(cat_aff) == [1.0, 0.0, 0.0]


def test_multi_signal_reranker_extracts_features_scores_and_persists(tmp_path):
    model = SimpleNamespace(
        scores=np.array([1.0, 5.0, 2.0]),
        num_items=3,
        user_items=sparse.csr_matrix([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 1.0]]),
        similarity=sparse.csr_matrix([[0.0, 0.2, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
    )
    est = _DummyEstimator()
    out_dir = tmp_path / "rr_art"
    manifest = MultiSignalReranker.save_estimator(est, out_dir, metadata={"tag": "toy"})
    assert manifest["status"] == "complete"
    loaded_est, loaded_meta = MultiSignalReranker.load_estimator(out_dir)
    assert loaded_meta["tag"] == "toy"

    ids = ["Video_Games::a", "Video_Games::b", "Electronics::c"]
    id2item = dict(enumerate(ids))
    item2id = {v: k for k, v in id2item.items()}
    dcp = DomainCategoryPopularity(
        {"Video_Games::a": "Video_Games", "Video_Games::b": "Video_Games", "Electronics::c": "Electronics"},
        {"Video_Games::a": "Cat1", "Video_Games::b": "Cat1", "Electronics::c": "Cat2"},
        {}, {},
    )
    reranker = MultiSignalReranker(model, loaded_est, id2item=id2item, domain_pop=dcp)
    req = reranker.for_request(
        source_attribution={
            "Video_Games::b": {"score": 0.05, "source_ranks": {"dense": 1, "domain_cat_pop": 2}},
            "Electronics::c": {"score": 0.02, "source_ranks": {"popularity": 1}},
        },
        seen_items=["Video_Games::a"],
    )
    reco = RankTool(req, {"u0": 0}, item2id)
    res = reco(user_id="u0", candidates=["Electronics::c", "Video_Games::b"], top_k=2, exclude_seen=True)
    assert res.ok and res.data["ranked"][0]["item_id"] == "Video_Games::b"

    # Tampering with reranker.pkl must fail checksum validation.
    (out_dir / "reranker.pkl").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum mismatch"):
        MultiSignalReranker.load_estimator(out_dir)
