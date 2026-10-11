"""Contract tests for BaselineScorer: formula, tie-breaking, cold users, and the near-tie-breaker caveat."""

import numpy as np
import pytest
import scipy.sparse as sp

from package.tools import BaselineScorer
from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender


class FakeModel:  # the attributes BaselineScorer needs from a fitted legacy model
    def __init__(self, sim, pop, user_items):
        self.similarity = sp.csr_matrix(sim)
        self.scores = np.asarray(pop, dtype=float)
        self.user_items = sp.csr_matrix(user_items)
        self.num_items = len(pop)


def test_formula_is_cf_plus_tiny_normalised_popularity(world):
    knn = ItemKNNRecommender(neighbors=5).fit(world.interactions)
    scorer = BaselineScorer(knn)
    scores = scorer.score(1, np.arange(6))  # u1 saw item 0
    cf = np.array([0, 4 / np.sqrt(20), 2 / np.sqrt(10), 1 / np.sqrt(5), 4 / np.sqrt(20), 3 / np.sqrt(15)])
    # legacy orientation: (history @ S)[i] = S[0, i]; neighbours are all kept, so this equals sim(0, i)
    assert scores == pytest.approx(cf + np.array([5, 4, 2, 1, 4, 3]) / 5 * 1e-6, abs=1e-7)


def test_users_without_history_get_popularity_only(world):
    scorer = BaselineScorer(ItemKNNRecommender(neighbors=5).fit(world.interactions))
    expected = np.array([5, 4, 2, 1, 4, 3]) / 5 * 1e-6
    for user in (0, -1, 10_000):  # cold, negative, out of range
        assert scorer.score(user, np.arange(6)) == pytest.approx(expected)
        assert not scorer.is_known_user(user) and scorer.seen_items(user) == set() and not scorer.has_personal_signal(user)


def test_seen_items_and_signal_match_the_history(world):
    scorer = BaselineScorer(ItemKNNRecommender(neighbors=5).fit(world.interactions))
    assert scorer.seen_items(2) == {0, 1, 4, 5} and scorer.seen_items(5) == {0, 1, 2, 3, 4, 5}
    assert scorer.is_known_user(2) and scorer.has_personal_signal(2)
    assert scorer.is_known_user(0) is False


def test_popularity_only_model_has_no_personal_signal(world):
    scorer = BaselineScorer(PopularityRecommender().fit(world.interactions))
    assert scorer.is_known_user(2) and not scorer.has_personal_signal(2)  # known user, but no CF signal exists


def test_equal_cf_scores_are_ordered_by_popularity():
    sim = np.zeros((3, 3)); sim[0, 1] = sim[0, 2] = 0.5
    scorer = BaselineScorer(FakeModel(sim, [1, 1, 100], [[1, 0, 0]]))
    s = scorer.score(0, np.array([1, 2]))
    assert s[1] > s[0]  # true tie in CF -> the more popular item wins


@pytest.mark.parametrize("gap, popularity_wins", [(1e-3, False), (1e-5, False), (1e-7, True)])
def test_popularity_is_a_NEAR_tie_breaker_not_an_exact_one(gap, popularity_wins):
    """Documents the real behaviour: the popularity term is <= 1e-6, so it overrides CF only when the CF scores
    differ by less than that. Item 1 has the higher CF score (0.5 + gap); item 2 is far more popular."""
    sim = np.zeros((3, 3)); sim[0, 1] = 0.5 + gap; sim[0, 2] = 0.5
    scorer = BaselineScorer(FakeModel(sim, [1, 1, 1000], [[1, 0, 0]]))
    s = scorer.score(0, np.array([1, 2]))
    assert bool(s[1] > s[0]) == popularity_wins


def test_positive_cf_below_the_popularity_term_loses_to_a_popular_zero_cf_item():
    """Known limitation of the additive tie-breaker (CF 1e-9 < 1e-6 * pop_norm)."""
    sim = np.zeros((3, 3)); sim[0, 1] = 1e-9
    scorer = BaselineScorer(FakeModel(sim, [1, 1, 1000], [[1, 0, 0]]))
    s = scorer.score(0, np.array([1, 2]))
    assert s[1] > s[0]


def test_scores_have_input_shape_and_are_finite(world):
    scorer = BaselineScorer(ItemKNNRecommender(neighbors=5).fit(world.interactions))
    for idxs in (np.array([], dtype=np.int64), np.array([3]), np.array([5, 5, 0, -1, 99])):
        out = scorer.score(2, idxs)
        assert out.shape == idxs.shape and np.isfinite(out).all()
    assert scorer.score(2, np.array([-1, 6, 99])).tolist() == [0.0, 0.0, 0.0]  # out-of-vocabulary items score 0
