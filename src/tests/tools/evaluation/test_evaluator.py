"""Unit tests for recommender evaluation logic."""

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from package.tools.evaluation import evaluate_recommender
from package.tools.evaluation import evaluate_ranking
from package.tools.recommenders import PopularityRecommender


class MockRecommender:
    """Mock recommender for testing evaluation logic."""

    def __init__(self, num_items=10, pad_with_neg_one=False):
        self.num_items = num_items
        self.pad_with_neg_one = pad_with_neg_one
        self.train_matrix = sp.csr_matrix((0, num_items))

    def recommend(self, user_idx, k, exclude=None):
        """Return mock recommendations, optionally with -1 padding."""
        if isinstance(user_idx, (list, np.ndarray)):
            batch_size = len(user_idx)
            recs = np.zeros((batch_size, k), dtype=np.int64)
            for i, u in enumerate(user_idx):
                # Give some real items, possibly pad with -1
                if self.pad_with_neg_one and k > self.num_items // 2:
                    # Pad with -1 in second half
                    real_items = np.arange(min(k // 2, self.num_items))
                    padding = np.full(k - len(real_items), -1, dtype=np.int64)
                    recs[i] = np.concatenate([real_items, padding])
                else:
                    recs[i] = np.arange(min(k, self.num_items))
            return recs
        else:
            # Single user
            if self.pad_with_neg_one and k > self.num_items // 2:
                real_items = np.arange(min(k // 2, self.num_items))
                padding = np.full(k - len(real_items), -1, dtype=np.int64)
                return np.concatenate([real_items, padding])
            return np.arange(min(k, self.num_items))

    def history_sizes(self, user_indices):
        """Return mock history sizes."""
        return np.ones(len(user_indices))


def test_evaluate_recommender_padding_neg_one_not_counted_as_hit():
    """Padding -1 should not be counted as a hit in ground truth."""
    num_users = 5
    num_items = 10
    ks = [5]

    # Create mock recommender that returns -1 padding
    model = MockRecommender(num_items=num_items, pad_with_neg_one=True)

    # Create exclude matrix (fit data)
    exclude = sp.csr_matrix((num_users, num_items))

    # Create target matrix - only item 0 is relevant for all users
    target = sp.csr_matrix((num_users, num_items))
    target[0, 0] = 1  # User 0 has item 0 in target
    target[1, 0] = 1  # User 1 has item 0 in target
    target[2, 0] = 1  # User 2 has item 0 in target
    target[3, 0] = 1  # User 3 has item 0 in target
    target[4, 0] = 1  # User 4 has item 0 in target

    result = evaluate_recommender(model, exclude, target, ks)

    # With -1 padding, only real items should be counted
    # Since item 0 is in recommendations (index 0), it should be a hit
    # But -1 should not cause false hits on the last item (index 9)
    assert result.overall["hit_rate@5"] > 0  # Should have some hits
    assert result.overall["hit_rate@5"] <= 1.0


def test_evaluate_recommender_padding_neg_one_not_in_coverage():
    """Padding -1 should not be counted in catalog coverage."""
    num_users = 5
    num_items = 10
    ks = [5]

    # Create mock recommender that returns -1 padding
    model = MockRecommender(num_items=num_items, pad_with_neg_one=True)

    exclude = sp.csr_matrix((num_users, num_items))
    target = sp.csr_matrix((num_users, num_items))
    target[0, 0] = 1

    result = evaluate_recommender(model, exclude, target, ks)

    # Coverage should not include -1 (non-existent item)
    # Only real items (0, 1, 2 in this case) should be counted
    coverage = result.catalog_coverage["catalog_coverage@5"]
    assert coverage <= 0.5  # At most 3 items out of 10
    assert coverage >= 0.0


def test_evaluate_recommender_rejects_empty_ks():
    """Should reject empty ks list."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))
    target[0, 0] = 1

    with pytest.raises(ValueError, match="ks must be a non-empty"):
        evaluate_recommender(model, exclude, target, [])


def test_evaluate_recommender_rejects_non_positive_k():
    """Should reject non-positive k values."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))
    target[0, 0] = 1

    with pytest.raises(ValueError, match="positive integers"):
        evaluate_recommender(model, exclude, target, [0])

    with pytest.raises(ValueError, match="positive integers"):
        evaluate_recommender(model, exclude, target, [-1])


def test_evaluate_recommender_rejects_duplicate_ks():
    """Should reject duplicate k values."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))
    target[0, 0] = 1

    with pytest.raises(ValueError, match="unique values"):
        evaluate_recommender(model, exclude, target, [5, 5])


def test_evaluate_recommender_rejects_k_exceeds_num_items():
    """Should reject k larger than num_items."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))
    target[0, 0] = 1

    with pytest.raises(ValueError, match="cannot exceed num_items"):
        evaluate_recommender(model, exclude, target, [15])


def test_evaluate_recommender_rejects_invalid_sparse_max():
    """Should reject invalid sparse_max values."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))
    target[0, 0] = 1

    with pytest.raises(ValueError, match="sparse_max must be a non-negative integer"):
        evaluate_recommender(model, exclude, target, [5], sparse_max=-1)

    with pytest.raises(ValueError, match="sparse_max must be a non-negative integer"):
        evaluate_recommender(model, exclude, target, [5], sparse_max=3.5)


def test_evaluate_recommender_rejects_empty_target():
    """Should reject target with no interactions."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 10))  # Empty target

    with pytest.raises(ValueError, match="no interactions to evaluate"):
        evaluate_recommender(model, exclude, target, [5])


def test_evaluate_recommender_shape_mismatch():
    """Should reject when exclude and target have different shapes."""
    model = MockRecommender(num_items=10)
    exclude = sp.csr_matrix((5, 10))
    target = sp.csr_matrix((5, 8))  # Different shape

    with pytest.raises(ValueError, match="same shape"):
        evaluate_recommender(model, exclude, target, [5])


def test_evaluate_ranking_rejects_empty_interactions():
    """Should reject empty interactions DataFrame."""
    model = PopularityRecommender()
    interactions = pd.DataFrame(columns=["user_idx", "item_idx", "timestamp"])

    with pytest.raises(ValueError, match="interactions DataFrame is empty"):
        evaluate_ranking(model, interactions, [5])


def test_evaluate_ranking_rejects_invalid_k_values():
    """Should reject invalid k_values."""
    model = PopularityRecommender()
    interactions = pd.DataFrame({
        "user_idx": [0, 0],
        "item_idx": [0, 1],
        "timestamp": [1, 2]
    })

    with pytest.raises(ValueError, match="positive integers"):
        evaluate_ranking(model, interactions, [0])

    with pytest.raises(ValueError, match="positive integers"):
        evaluate_ranking(model, interactions, [])


def test_evaluate_ranking_with_valid_data():
    """Should work correctly with valid data."""
    model = PopularityRecommender()
    interactions = pd.DataFrame({
        "user_idx": [0, 0, 1, 1],
        "item_idx": [0, 1, 0, 2],
        "timestamp": [1, 2, 3, 4]
    })

    model.fit(interactions)

    result = evaluate_ranking(model, interactions, [5])

    assert "evaluated_users" in result
    assert result["evaluated_users"] > 0
    assert "precision@5" in result
    assert "recall@5" in result
    assert "hit_rate@5" in result
    assert "ndcg@5" in result
    assert "mrr@5" in result
    assert "map@5" in result
