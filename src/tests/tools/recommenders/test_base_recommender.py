"""Unit tests for Recommender base class."""

import numpy as np
import pytest
import scipy.sparse as sp

from package.tools.recommenders.recommender import Recommender
from package.tools.recommenders.popularity import PopularityRecommender


class MockRecommender(Recommender):
    """Mock recommender for testing base class functionality."""
    name = "mock"

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        # Mock fit - no actual computation
        pass

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        # Return mock scores - all zeros
        return np.zeros((len(user_idxs), self.num_items))


def test_recommend_validates_k():
    """recommend() should validate k parameter."""
    model = MockRecommender()
    train = sp.csr_matrix((5, 10))
    model.fit(train)

    # k must be positive
    with pytest.raises(ValueError, match="k must be in"):
        model.recommend(np.array([0, 1]), 0)

    with pytest.raises(ValueError, match="k must be in"):
        model.recommend(np.array([0, 1]), -1)

    # k must not exceed num_items
    with pytest.raises(ValueError, match="k must be in"):
        model.recommend(np.array([0, 1]), 15)

    # k must be integer
    with pytest.raises(ValueError, match="k must be in"):
        model.recommend(np.array([0, 1]), 5.5)


def test_recommend_validates_user_idxs_type():
    """recommend() should validate user_idxs is numpy array."""
    model = MockRecommender()
    train = sp.csr_matrix((5, 10))
    model.fit(train)

    with pytest.raises(TypeError, match="user_idxs must be a numpy array"):
        model.recommend([0, 1], 5)  # List instead of array

    with pytest.raises(TypeError, match="user_idxs must be a numpy array"):
        model.recommend((0, 1), 5)  # Tuple instead of array


def test_recommend_validates_user_idxs_dimension():
    """recommend() should validate user_idxs is 1-dimensional."""
    model = MockRecommender()
    train = sp.csr_matrix((5, 10))
    model.fit(train)

    with pytest.raises(ValueError, match="user_idxs must be 1-dimensional"):
        model.recommend(np.array([[0, 1]]), 5)  # 2D array


def test_recommend_validates_user_idxs_not_empty():
    """recommend() should validate user_idxs is not empty."""
    model = MockRecommender()
    train = sp.csr_matrix((5, 10))
    model.fit(train)

    with pytest.raises(ValueError, match="user_idxs cannot be empty"):
        model.recommend(np.array([]), 5)


def test_recommend_validates_user_idxs_bounds():
    """recommend() should validate user_idxs are within valid range."""
    model = MockRecommender()
    train = sp.csr_matrix((5, 10))
    model.fit(train)

    # Negative index
    with pytest.raises(ValueError, match="out-of-range"):
        model.recommend(np.array([0, -1]), 5)

    # Index >= num_users
    with pytest.raises(ValueError, match="out-of-range"):
        model.recommend(np.array([0, 5]), 5)


def test_recommend_tie_break_prefers_smaller_index():
    """When scores are equal, smaller item_idx should be preferred."""
    model = PopularityRecommender()
    # Create train data where all items have equal popularity
    train = sp.csr_matrix((5, 10))
    for i in range(10):
        train[0, i] = 1  # User 0 has seen all items equally
    model.fit(train)

    # All items have same score for user 1 (no history)
    result = model.recommend(np.array([1]), 5)

    # Should return [0, 1, 2, 3, 4] (smallest indices first)
    expected = np.array([[0, 1, 2, 3, 4]])
    np.testing.assert_array_equal(result, expected)


def test_recommend_padding_with_neg_one():
    """When fewer than k valid items, result should be padded with -1."""
    model = PopularityRecommender()
    train = sp.csr_matrix((5, 10))
    # Only 3 items have interactions
    train[0, 0] = 1
    train[1, 1] = 1
    train[2, 2] = 1
    model.fit(train)

    exclude = sp.csr_matrix((5, 10))
    # Exclude all items except one
    exclude[0, 0] = 1
    exclude[0, 1] = 1
    exclude[0, 2] = 1
    exclude[0, 3] = 1
    exclude[0, 4] = 1
    exclude[0, 5] = 1
    exclude[0, 6] = 1
    exclude[0, 7] = 1
    exclude[0, 8] = 1
    # Only item 9 is not excluded
    exclude[0, 9] = 0

    result = model.recommend(np.array([0]), 5, exclude=exclude)

    # Should have [9, -1, -1, -1, -1]
    assert result[0, 0] == 9
    assert result[0, 1] == -1
    assert result[0, 2] == -1
    assert result[0, 3] == -1
    assert result[0, 4] == -1


def test_recommend_filters_excluded_items():
    """Items in exclude matrix should not be returned."""
    model = PopularityRecommender()
    train = sp.csr_matrix((5, 10))
    train[0, 0] = 1
    train[0, 1] = 1
    train[0, 2] = 1
    model.fit(train)

    exclude = sp.csr_matrix((5, 10))
    exclude[0, 1] = 1  # Exclude item 1

    result = model.recommend(np.array([0]), 5, exclude=exclude)

    # Item 1 should not be in results
    assert 1 not in result[0]


def test_history_sizes_requires_fit():
    """history_sizes() should raise error if fit() not called."""
    model = MockRecommender()

    with pytest.raises(AssertionError, match="call fit"):
        model.history_sizes(np.array([0, 1]))


def test_history_sizes_returns_correct_counts():
    """history_sizes() should return correct interaction counts."""
    model = PopularityRecommender()
    train = sp.csr_matrix((5, 10))
    train[0, 0] = 1
    train[0, 1] = 1
    train[0, 2] = 1
    train[1, 3] = 1
    train[1, 4] = 1
    model.fit(train)

    sizes = model.history_sizes(np.array([0, 1, 2]))

    assert sizes[0] == 3
    assert sizes[1] == 2
    assert sizes[2] == 0


def test_popularity_fallback_when_all_scores_zero():
    """When all valid scores are zero, popularity should be used as tie-break."""
    model = PopularityRecommender()
    train = sp.csr_matrix((5, 10))
    # Item 0 is most popular, item 9 is least popular
    for i in range(5):
        train[i, 0] = 1  # Item 0: 5 interactions
    train[0, 1] = 1  # Item 1: 1 interaction
    model.fit(train)

    # User 2 has no history, so all scores are zero initially
    result = model.recommend(np.array([2]), 5)

    # Should rank item 0 first (most popular), then item 1
    assert result[0, 0] == 0
    assert result[0, 1] == 1


def test_popularity_fallback_with_exclude():
    """Popularity fallback should only consider non-excluded items."""
    model = PopularityRecommender()
    train = sp.csr_matrix((5, 10))
    train[0, 0] = 1
    train[0, 1] = 1
    train[0, 2] = 1
    model.fit(train)

    exclude = sp.csr_matrix((5, 10))
    exclude[2, 0] = 1  # Exclude most popular item for user 2

    result = model.recommend(np.array([2]), 5, exclude=exclude)

    # Item 0 should not be in results
    assert 0 not in result[0]
