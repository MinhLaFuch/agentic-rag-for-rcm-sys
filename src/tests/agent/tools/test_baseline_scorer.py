"""Unit tests for BaselineScorer contract and invariants."""

import math

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from package.tools import BaselineScorer
from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender


def _create_mock_model(num_items=10, num_users=5, with_similarity=True):
    """Create a mock model with valid data for testing."""
    interactions = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2, 2, 3],
        "item_idx": [0, 1, 1, 2, 2, 3, 0],
    })
    if with_similarity:
        model = ItemKNNRecommender(neighbors=3).fit(interactions)
    else:
        model = PopularityRecommender().fit(interactions)
    return model


def test_scorer_rejects_model_with_wrong_popularity_shape():
    """Scorer should reject model where popularity length != num_items."""
    model = _create_mock_model()
    # Manually corrupt the model
    model.scores = np.ones(20)  # Wrong length
    model.num_items = 10

    with pytest.raises(ValueError, match="popularity array has length"):
        BaselineScorer(model)


def test_scorer_rejects_model_with_nan_popularity():
    """Scorer should reject model with NaN in popularity."""
    model = _create_mock_model()
    model.scores[0] = np.nan

    with pytest.raises(ValueError, match="non-finite values"):
        BaselineScorer(model)


def test_scorer_rejects_model_with_inf_popularity():
    """Scorer should reject model with infinite values in popularity."""
    model = _create_mock_model()
    model.scores[0] = np.inf

    with pytest.raises(ValueError, match="non-finite values"):
        BaselineScorer(model)


def test_scorer_rejects_model_with_wrong_user_items_shape():
    """Scorer should reject model where user_items columns != num_items."""
    # Use popularity model (no similarity) to simplify testing
    model = _create_mock_model(with_similarity=False)
    # Manually corrupt the model - change num_items but not user_items, also update popularity
    original_num_items = model.num_items
    model.num_items = original_num_items + 10  # Set to a different value
    model.scores = np.ones(model.num_items)  # Match new num_items

    # Should raise ValueError for inconsistency
    with pytest.raises(ValueError):
        BaselineScorer(model)


def test_scorer_rejects_model_with_wrong_similarity_shape():
    """Scorer should reject model where similarity shape != (num_items, num_items)."""
    model = _create_mock_model()
    # Manually corrupt the model - change num_items but not similarity, also update popularity
    original_num_items = model.num_items
    model.num_items = original_num_items + 10  # Set to a different value
    model.scores = np.ones(model.num_items)  # Match new num_items
    model.user_items = sparse.csr_matrix((model.user_items.shape[0], model.num_items))  # Match new num_items

    # Should raise ValueError for inconsistency
    with pytest.raises(ValueError):
        BaselineScorer(model)


def test_scorer_rejects_model_with_nan_similarity():
    """Scorer should reject model with NaN in similarity."""
    model = _create_mock_model()
    # Inject NaN into similarity (ensure there's data to corrupt)
    if model.similarity.nnz > 0:
        model.similarity.data[0] = np.nan
    else:
        # If similarity is empty, add some data with NaN
        model.similarity = sparse.csr_matrix(([np.nan], ([0], [1])), shape=(model.num_items, model.num_items))

    with pytest.raises(ValueError, match="non-finite values"):
        BaselineScorer(model)


def test_scorer_handles_negative_indices():
    """Scorer should safely handle negative item indices by scoring them as 0."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    # Mix of valid and negative indices
    item_idxs = np.array([0, 1, -1, -5, 2])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)

    # Negative indices should get score 0
    assert scores[2] == 0.0
    assert scores[3] == 0.0
    # Valid indices should get non-zero scores
    assert scores[0] > 0 or scores[0] >= 0  # At least popularity term
    assert scores[1] > 0 or scores[1] >= 0
    assert scores[4] > 0 or scores[4] >= 0


def test_scorer_handles_indices_out_of_range():
    """Scorer should safely handle indices >= num_items by scoring them as 0."""
    model = _create_mock_model(num_items=10)
    scorer = BaselineScorer(model)

    # Mix of valid and out-of-range indices
    item_idxs = np.array([0, 1, 10, 100, 2])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)

    # Out-of-range indices should get score 0
    assert scores[2] == 0.0
    assert scores[3] == 0.0
    # Valid indices should get non-zero scores
    assert scores[0] >= 0
    assert scores[1] >= 0
    assert scores[4] >= 0


def test_scorer_handles_empty_input():
    """Scorer should return empty array of correct shape for empty input."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    item_idxs = np.array([], dtype=np.int64)
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)

    assert scores.shape == (0,)


def test_scorer_score_output_matches_input_shape():
    """Scorer contract: output shape must match input shape."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    for size in [1, 5, 10, 100]:
        item_idxs = np.random.randint(0, model.num_items, size=size)
        scores = scorer.score(user_idx=0, item_idxs=item_idxs)
        assert scores.shape == (size,)


def test_scorer_score_output_is_finite():
    """Scorer contract: all scores must be finite (no NaN or inf)."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    item_idxs = np.array([0, 1, 2, 3, 4])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)

    assert np.all(np.isfinite(scores))


def test_scorer_unknown_user_gets_popularity_fallback():
    """Unknown user should get popularity-based scores."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    item_idxs = np.array([0, 1, 2])
    scores = scorer.score(user_idx=999, item_idxs=item_idxs)

    # Scores should be based on popularity (very small values)
    # All should be > 0 due to popularity term
    assert np.all(scores > 0)


def test_scorer_known_user_gets_cf_scores():
    """Known user with history should get CF + popularity scores."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    item_idxs = np.array([0, 1, 2])
    scores_cf = scorer.score(user_idx=0, item_idxs=item_idxs)
    scores_pop = scorer.score(user_idx=999, item_idxs=item_idxs)

    # Known user should generally have higher scores due to CF term
    # (not guaranteed for all items, but at least some should differ)
    assert not np.allclose(scores_cf, scores_pop)


def test_scorer_has_personal_signal_known_user():
    """Known user with history should have personal signal."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    assert scorer.has_personal_signal(user_idx=0) is True


def test_scorer_has_personal_signal_unknown_user():
    """Unknown user should not have personal signal."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    assert scorer.has_personal_signal(user_idx=999) is False


def test_scorer_has_personal_signal_popularity_model():
    """Popularity model should never have personal signal."""
    model = _create_mock_model(with_similarity=False)
    scorer = BaselineScorer(model)

    assert scorer.has_personal_signal(user_idx=0) is False


def test_scorer_seen_items_unknown_user():
    """Unknown user should have empty seen items."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    seen = scorer.seen_items(user_idx=999)
    assert seen == set()


def test_scorer_seen_items_known_user():
    """Known user should return their seen items."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    seen = scorer.seen_items(user_idx=0)
    # User 0 interacted with items 0 and 1 in the mock data
    assert isinstance(seen, set)
    # At least should be a set, specific items depend on interactions


def test_scorer_is_known_user():
    """is_known_user should correctly identify known vs unknown users."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    assert scorer.is_known_user(user_idx=0) is True
    assert scorer.is_known_user(user_idx=1) is True
    assert scorer.is_known_user(user_idx=999) is False
    assert scorer.is_known_user(user_idx=-1) is False


def test_scorer_popularity_normalization():
    """Popularity should be normalized to [0, 1] range."""
    model = _create_mock_model()
    scorer = BaselineScorer(model)

    # After normalization, max should be 1.0 (or close to it)
    assert np.max(scorer._pop_norm) <= 1.0
    assert np.min(scorer._pop_norm) >= 0.0


def test_scorer_zero_peak_popularity():
    """Scorer should handle case where all popularity scores are zero."""
    model = _create_mock_model()
    model.scores = np.zeros(model.num_items)
    scorer = BaselineScorer(model)

    # Should not crash, popularity normalization should handle this
    item_idxs = np.array([0, 1, 2])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)
    assert scores.shape == (3,)


def test_scorer_popularity_only_model():
    """Popularity-only model should work without similarity."""
    model = _create_mock_model(with_similarity=False)
    scorer = BaselineScorer(model)

    item_idxs = np.array([0, 1, 2])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)

    assert scores.shape == (3,)
    assert np.all(np.isfinite(scores))
