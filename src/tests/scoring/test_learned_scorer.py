"""Unit tests for LearnedScorer (affine [pop, cf] reranker)."""

import numpy as np
import pandas as pd
import pytest

from package.tools import BaselineScorer, LearnedScorer
from package.recommenders import ItemKNNRecommender


def _model():
    interactions = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2, 2, 3, 4],
        "item_idx": [0, 1, 1, 2, 2, 3, 4, 4],
    })
    return ItemKNNRecommender(neighbors=3).fit(interactions)


def test_learned_scorer_contract_shape_and_finite():
    scorer = LearnedScorer(_model())
    idxs = np.arange(10)
    scores = scorer.score(0, idxs)
    assert scores.shape == idxs.shape
    assert np.isfinite(scores).all()


def test_learned_scorer_unknown_user_gets_popularity_fallback():
    """Cold/unknown users must still get a finite score (popularity ordering)."""
    scorer = LearnedScorer(_model())
    idxs = np.arange(10)
    scores = scorer.score(999, idxs)
    assert np.isfinite(scores).all()
    # cf is all-zero -> cf_n is all-zero; ranking reduces to w_pop * pop_n.
    assert scorer.is_known_user(999) is False


def test_learned_scorer_differs_from_baseline():
    model = _model()
    base = BaselineScorer(model)
    learned = LearnedScorer(model)
    idxs = np.arange(10)
    assert not np.allclose(base.score(0, idxs), learned.score(0, idxs))


def test_learned_scorer_rejects_bad_weights():
    with pytest.raises(ValueError, match="finite"):
        LearnedScorer(_model(), weights=(1.0, np.nan, 0.0))
    with pytest.raises(ValueError, match="finite"):
        LearnedScorer(_model(), weights=(1.0, 2.0))


def test_learned_scorer_custom_weights_affine():
    """score() must equal w_pop*pop_n + w_cf*cf_n + w_bias on min-max features."""
    model = _model()
    w = (2.0, -1.0, 0.5)
    scorer = LearnedScorer(model, weights=w)
    idxs = np.arange(model.num_items)
    scores = scorer.score(0, idxs)
    # recompute expected signals independently
    pop = scorer._pop_norm[idxs]
    cf_row = (scorer.user_items.getrow(0) @ scorer.similarity).tocsr()
    cf = cf_row[:, idxs].toarray().ravel()

    def mm(a):
        lo, hi = a.min(), a.max()
        return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)

    expected = w[0] * mm(pop) + w[1] * mm(cf) + w[2]
    assert np.allclose(scores, expected, atol=1e-6)
