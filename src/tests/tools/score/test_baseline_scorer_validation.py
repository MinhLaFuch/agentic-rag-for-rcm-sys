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


    # At least should be a set, specific items depend on interactions


def test_scorer_zero_peak_popularity():
    """Scorer should handle case where all popularity scores are zero."""
    model = _create_mock_model()
    model.scores = np.zeros(model.num_items)
    scorer = BaselineScorer(model)

    # Should not crash, popularity normalization should handle this
    item_idxs = np.array([0, 1, 2])
    scores = scorer.score(user_idx=0, item_idxs=item_idxs)
    assert scores.shape == (3,)
