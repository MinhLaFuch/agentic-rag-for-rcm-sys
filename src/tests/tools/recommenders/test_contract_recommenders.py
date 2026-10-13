"""Contract tests for both recommender API families, the factory, the fallback and BPR negative sampling."""

import inspect

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from package.tools.recommenders import (
    ALL_MODELS, BPRMFRecommender, FallbackRecommender, ItemKNNMatrixRecommender, ItemKNNRecommender,
    ItemKNNRecommenderABC, PopularityMatrixRecommender, PopularityRecommender, Recommender, build_model,
    build_interaction_matrix,
)
from tests.tools.conftest import POPULARITY_ORDER

ALL_USERS = np.arange(6)


class ZeroModel(Recommender):
    """No personal signal at all: every score is 0."""
    name = "zero"

    def _fit(self, train_matrix):
        pass

    def score_batch(self, user_idxs):
        return np.zeros((len(user_idxs), self.num_items), dtype=np.float32)


class FixedScores(Recommender):
    name = "fixed"

    def __init__(self, scores):
        super().__init__()
        self._scores = np.asarray(scores, dtype=np.float32)

    def _fit(self, train_matrix):
        pass

    def score_batch(self, user_idxs):
        return np.tile(self._scores, (len(user_idxs), 1))


# ---------------------------------------------------------------- ranking, padding, exclusions (matrix API)
def test_popularity_scores_and_order(world):
    model = PopularityMatrixRecommender().fit(world.train)
    assert model.score_batch(np.array([0]))[0].tolist() == [5, 4, 2, 1, 4, 3]
    assert model.recommend(np.array([0]), 6)[0].tolist() == POPULARITY_ORDER  # tie 1 vs 4 -> smaller index first


def test_recommend_excludes_seen_and_pads_with_minus_one_only_as_sentinel(world):
    model = PopularityMatrixRecommender().fit(world.train)
    recs = model.recommend(ALL_USERS, 3, world.train)
    assert recs.tolist() == [
        [0, 1, 4],       # u0 cold: nothing excluded
        [1, 4, 5],       # u1 saw {0}
        [2, 3, -1],      # u2 saw {0,1,4,5}: only two recommendable -> one padding slot
        [3, -1, -1],     # u3 saw everything but 3
        [5, 2, 3],       # u4 saw {0,1,4}
        [-1, -1, -1],    # u5 saw everything
    ]
    for u, row in enumerate(recs):  # no excluded item ever returned
        assert not (set(row[row >= 0]) & set(world.train[u].indices))
        assert (row >= 0).sum() == len(set(row[row >= 0]))  # no duplicates among real items


def test_padding_is_always_a_suffix(world):
    recs = PopularityMatrixRecommender().fit(world.train).recommend(ALL_USERS, 6, world.train)
    for row in recs:
        n_valid = int((row >= 0).sum())
        assert (row[:n_valid] >= 0).all() and (row[n_valid:] == -1).all()


def test_tie_break_is_score_desc_then_item_index_asc():
    model = FixedScores([1, 3, 3, 2, 3, 0]).fit(sp.csr_matrix((1, 6), dtype=np.float32))
    assert model.recommend(np.array([0]), 6)[0].tolist() == [1, 2, 4, 3, 0, 5]


def test_repeated_users_in_a_batch_get_identical_rows(world):
    model = PopularityMatrixRecommender().fit(world.train)
    recs = model.recommend(np.array([2, 2, 2]), 3, world.train)
    assert (recs == recs[0]).all()


# ---------------------------------------------------------------- popularity fallback (all non-excluded scores are 0)
def test_zero_signal_user_is_ranked_by_popularity(world):
    recs = ZeroModel().fit(world.train).recommend(np.array([0]), 6)
    assert recs[0].tolist() == POPULARITY_ORDER


def test_fallback_looks_only_at_non_excluded_items(world):
    """-inf exclusions must not hide the 'all remaining scores are 0' condition (u4 saw 0,1,4)."""
    recs = ZeroModel().fit(world.train).recommend(np.array([4]), 3, world.train)
    assert recs[0].tolist() == [5, 2, 3]  # popularity order restricted to unseen items {2,3,5}


def test_fully_excluded_catalog_returns_only_padding(world):
    everything = sp.csr_matrix(np.ones((6, 6), dtype=np.float32))
    recs = ZeroModel().fit(world.train).recommend(np.array([0, 3]), 4, everything)
    assert (recs == -1).all()


def test_partial_signal_keeps_model_scores_and_does_not_use_popularity(world):
    model = FixedScores([0, 0, 9, 0, 0, 0]).fit(world.train)  # one non-zero score: ZeroModel rule must not apply
    assert model.recommend(np.array([0]), 3)[0].tolist() == [2, 0, 1]  # then ties by index, not popularity


def test_popularity_fallback_never_resurrects_excluded_items(world):
    exclude = sp.csr_matrix(([1.0], ([0], [0])), shape=(6, 6))  # u0 may not get item 0 (the most popular)
    recs = ZeroModel().fit(world.train).recommend(np.array([0]), 6, exclude)
    assert recs[0].tolist() == [1, 4, 5, 2, 3, -1]


# ---------------------------------------------------------------- input validation
@pytest.mark.parametrize("k", [0, -1, 7, 2.5, True, None, "3"], ids=repr)
def test_recommend_rejects_bad_k(world, k):
    with pytest.raises(ValueError, match="k must be in"):
        PopularityMatrixRecommender().fit(world.train).recommend(np.array([0]), k)


def test_recommend_accepts_numpy_integer_k(world):
    assert PopularityMatrixRecommender().fit(world.train).recommend(np.array([0]), np.int64(2))[0].tolist() == [0, 1]


@pytest.mark.parametrize("users, exc", [
    (np.array([-1]), ValueError), (np.array([6]), ValueError), (np.array([]), ValueError),
    (np.array([[0]]), ValueError), ([0], TypeError), (np.array([0.0]), TypeError),
])
def test_recommend_rejects_bad_user_idxs(world, users, exc):
    with pytest.raises(exc):
        PopularityMatrixRecommender().fit(world.train).recommend(users, 2)


def test_recommend_rejects_bad_exclude(world):
    model = PopularityMatrixRecommender().fit(world.train)
    with pytest.raises(ValueError, match="shape"):
        model.recommend(np.array([0]), 2, sp.csr_matrix((2, 6)))
    with pytest.raises(TypeError):
        model.recommend(np.array([0]), 2, np.zeros((6, 6)))
    # any sparse format is fine
    assert model.recommend(np.array([1]), 2, sp.coo_matrix(world.train))[0].tolist() == [1, 4]


def test_nan_scores_raise_instead_of_silently_dropping_items(world):
    with pytest.raises(ValueError, match="NaN"):
        FixedScores([1, np.nan, 2, 3, 4, 5]).fit(world.train).recommend(np.array([0]), 3)


def test_wrong_score_shape_raises(world):
    class Bad(ZeroModel):
        def score_batch(self, user_idxs):
            return np.zeros((len(user_idxs), 2))

    with pytest.raises(ValueError, match="shape"):
        Bad().fit(world.train).recommend(np.array([0]), 2)


def test_unfitted_model_gives_a_clear_error():
    with pytest.raises(RuntimeError, match="fit"):
        ZeroModel().recommend(np.array([0]), 1)


# ---------------------------------------------------------------- fit(): canonical training matrix
def test_history_sizes_count_real_interactions_only():
    # built from raw CSR arrays on purpose: row 0 has a stored zero, row 1 has a duplicate entry (non-canonical)
    raw = sp.csr_matrix((np.array([1.0, 0.0, 1.0, 1.0]), np.array([0, 1, 2, 2]), np.array([0, 2, 4, 4])), shape=(3, 3))
    model = ZeroModel().fit(raw)
    assert model.history_sizes(np.array([0, 1, 2])).tolist() == [1, 1, 0]
    assert raw.nnz == 4  # the caller's matrix was not modified


@pytest.mark.parametrize("bad, exc", [
    (np.eye(3), TypeError),
    (sp.csr_matrix(np.array([[1.0, np.nan]])), ValueError),
    (sp.csr_matrix(np.array([[1.0, np.inf]])), ValueError),
    (sp.csr_matrix(np.array([[1.0, -1.0]])), ValueError),
])
def test_fit_rejects_invalid_matrices(bad, exc):
    with pytest.raises(exc):
        PopularityMatrixRecommender().fit(bad)


def test_fit_accepts_any_sparse_format(world):
    for fmt in (sp.coo_matrix, sp.csc_matrix, sp.lil_matrix):
        assert PopularityMatrixRecommender().fit(fmt(world.train)).item_counts.tolist() == [5, 4, 2, 1, 4, 3]


# ---------------------------------------------------------------- ItemKNN (matrix API) numbers
def test_item_knn_similarity_matches_hand_computation(world):
    sim = ItemKNNMatrixRecommender(k=5).fit(world.train).similarity.toarray()
    assert sim[0, 1] == pytest.approx(4 / np.sqrt(5 * 4), abs=1e-6)  # users sharing items 0&1: u2,u3,u4,u5
    assert sim[0, 3] == pytest.approx(1 / np.sqrt(5 * 1), abs=1e-6)
    assert np.allclose(np.diag(sim), 0)  # no self-similarity
    assert np.allclose(sim, sim.T, atol=1e-6)  # symmetric when no neighbour truncation happens


def test_item_knn_scores_for_a_user(world):
    model = ItemKNNMatrixRecommender(k=5).fit(world.train)
    scores = model.score_batch(np.array([1]))[0]  # u1 saw only item 0 -> score(i) = sim(i, 0)
    expected = [0, 4 / np.sqrt(20), 2 / np.sqrt(10), 1 / np.sqrt(5), 4 / np.sqrt(20), 3 / np.sqrt(15)]
    assert scores == pytest.approx(expected, abs=1e-6)


def test_item_knn_rejects_non_positive_k():
    with pytest.raises(ValueError):
        ItemKNNMatrixRecommender(k=0)


# ---------------------------------------------------------------- factory + fallback
@pytest.mark.parametrize("name", ALL_MODELS)
def test_every_registered_model_builds_fits_and_obeys_the_recommend_contract(world, name):
    cfg = {"seed": 7, "item_knn": {"k": 5}, "bpr_mf": {"embedding_dim": 4, "epochs": 2, "batch_size": 8}}
    model = build_model(name, cfg).fit(world.train)
    assert isinstance(model, Recommender) and model.num_items == 6
    recs = model.recommend(ALL_USERS, 4, world.train)
    assert recs.shape == (6, 4) and recs.dtype == np.int64
    for u, row in enumerate(recs):
        real = row[row >= 0]
        assert len(real) == min(4, 6 - world.train[u].nnz)  # exactly as many as are recommendable
        assert not (set(real) & set(world.train[u].indices)) and len(set(real)) == len(real)
        assert (row[len(real):] == -1).all()


def test_registered_names_match_the_factory_branches():
    assert ALL_MODELS == ["random", "popularity", "item_knn", "bpr_mf"]
    with pytest.raises(ValueError, match="Unknown model 'nope'"):
        build_model("nope", {})


def test_factory_fallback_wrapping_and_seed_precedence():
    assert isinstance(build_model("item_knn", {}), FallbackRecommender)
    assert isinstance(build_model("item_knn", {"popularity_fallback": False}), ItemKNNMatrixRecommender)
    assert isinstance(build_model("random", {}), Recommender) and build_model("popularity", {}).name == "popularity"
    assert build_model("bpr_mf", {"seed": 1, "bpr_mf": {"seed": 9}, "popularity_fallback": False}).seed == 9
    assert build_model("bpr_mf", {"seed": 1, "popularity_fallback": False}).seed == 1


@pytest.mark.parametrize("name, cfg, exc", [
    ("item_knn", {"item_knn": {"bogus": 1}}, TypeError),
    ("item_knn", {"item_knn": {"k": 0}}, ValueError),
    ("bpr_mf", {"bpr_mf": {"epochs": 0}}, ValueError),
    ("bpr_mf", {"bpr_mf": {"learning_rate": -1}}, ValueError),
])
def test_factory_invalid_parameters(name, cfg, exc):
    with pytest.raises(exc):
        build_model(name, cfg)


def test_fallback_replaces_scores_only_for_cold_users(world):
    primary = ItemKNNMatrixRecommender(k=5)
    model = FallbackRecommender(primary, PopularityMatrixRecommender()).fit(world.train)
    rows = model.score_batch(ALL_USERS)
    pop = [5, 4, 2, 1, 4, 3]
    assert rows[0].tolist() == pop  # u0 is cold -> popularity scores
    assert np.allclose(rows[1:], primary.score_batch(ALL_USERS[1:]))  # everyone else keeps the primary scores
    assert model.name == "item_knn+popularity_fallback"


def test_random_recommender_is_reproducible_per_seed(world):
    a = build_model("random", {"seed": 3}).fit(world.train).recommend(ALL_USERS, 3)
    b = build_model("random", {"seed": 3}).fit(world.train).recommend(ALL_USERS, 3)
    assert (a == b).all()


# ---------------------------------------------------------------- BPR negative sampling
def _dense_user_matrix():
    m = sp.lil_matrix((2, 10), dtype=np.float32)
    m[0, :9] = 1  # user 0 owns items 0..8: the ONLY valid negative is item 9
    m[1, 0] = 1
    return m.tocsr()


def test_bpr_negatives_are_never_any_of_the_users_positives():
    matrix = _dense_user_matrix()
    model = BPRMFRecommender(embedding_dim=4, epochs=1).fit(matrix)
    rng = np.random.default_rng(0)
    users = np.zeros(500, dtype=np.int64)
    pos = rng.integers(0, 9, 500)
    neg = model._sample_negatives(np.random.default_rng(1), users, pos, matrix)
    assert (neg == 9).all()  # used to return a positive ~88% of the time


def test_bpr_negatives_cover_the_whole_complement_for_normal_users():
    matrix = _dense_user_matrix()
    model = BPRMFRecommender(embedding_dim=4, epochs=1).fit(matrix)
    users = np.ones(400, dtype=np.int64)  # user 1 owns only item 0
    neg = model._sample_negatives(np.random.default_rng(2), users, np.zeros(400, dtype=np.int64), matrix)
    assert 0 not in neg and set(neg) == set(range(1, 10))


def test_bpr_user_who_saw_every_item_gets_sentinel_and_training_finishes():
    m = sp.lil_matrix((3, 4), dtype=np.float32)
    m[0, :] = 1  # saw everything
    m[1, 0] = 1
    m[2, 1] = 1
    matrix = m.tocsr()
    model = BPRMFRecommender(embedding_dim=4, epochs=3, batch_size=2)
    model.fit(matrix)  # must terminate
    assert len(model.loss_history) == 3 and np.isfinite(model.loss_history).all()
    assert np.isfinite(model.score_batch(np.arange(3))).all()


def test_bpr_sampler_returns_minus_one_when_no_negative_exists():
    m = sp.csr_matrix(np.ones((1, 4), dtype=np.float32))
    model = BPRMFRecommender(embedding_dim=2, epochs=1)
    model.num_items = 4
    assert model._sample_negatives(np.random.default_rng(0), np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64), m).tolist() == [-1, -1, -1]


def test_bpr_is_deterministic_for_a_seed(world):
    a = BPRMFRecommender(embedding_dim=4, epochs=3, batch_size=4, seed=5).fit(world.train)
    b = BPRMFRecommender(embedding_dim=4, epochs=3, batch_size=4, seed=5).fit(world.train)
    c = BPRMFRecommender(embedding_dim=4, epochs=3, batch_size=4, seed=6).fit(world.train)
    assert np.array_equal(a.user_factors, b.user_factors) and a.loss_history == b.loss_history
    assert not np.array_equal(a.user_factors, c.user_factors)


def test_bpr_rejects_empty_training_matrix():
    with pytest.raises(ValueError, match="empty"):
        BPRMFRecommender(embedding_dim=2, epochs=1).fit(sp.csr_matrix((3, 3), dtype=np.float32))


# ---------------------------------------------------------------- the two API families
def test_naming_the_abc_aliases_are_concrete_classes():
    """`ItemKNNRecommenderABC` is NOT abstract: it is just an alias of the sparse-matrix ItemKNN implementation."""
    assert ItemKNNRecommenderABC is ItemKNNMatrixRecommender and not inspect.isabstract(ItemKNNRecommenderABC)
    assert ItemKNNRecommender is not ItemKNNMatrixRecommender  # the DataFrame-API class has the plain name


@pytest.fixture
def random_interactions():
    rng = np.random.default_rng(3)
    dense = (rng.random((40, 12)) < 0.3).astype(np.float32)
    dense[dense.sum(1) == 0, 0] = 1
    rows, cols = np.nonzero(dense)
    df = pd.DataFrame({"user_idx": rows, "item_idx": cols})
    return df, build_interaction_matrix(df, 40, 12)


def test_legacy_and_matrix_item_knn_agree_without_neighbour_truncation(random_interactions):
    df, matrix = random_interactions
    legacy, new = ItemKNNRecommender(neighbors=11).fit(df), ItemKNNMatrixRecommender(k=11).fit(matrix)
    assert np.allclose(legacy.similarity.toarray(), new.similarity.toarray(), atol=1e-6)
    for u in range(40):
        got = [i for i in new.recommend(np.array([u]), 5, matrix)[0].tolist() if i >= 0]
        assert legacy.recommend(u, 5) == got


def test_legacy_and_matrix_item_knn_score_in_opposite_orientations_when_truncated(random_interactions):
    """Characterisation of a KNOWN divergence (not a fix): same similarity matrix S, but the legacy API scores
    M @ S (history item's neighbour list) while the matrix API scores M @ S.T (candidate's neighbour list).
    They only coincide while S is symmetric, i.e. when no top-k truncation happened."""
    df, matrix = random_interactions
    legacy, new = ItemKNNRecommender(neighbors=3).fit(df), ItemKNNMatrixRecommender(k=3).fit(matrix)
    S = legacy.similarity
    assert np.allclose(S.toarray(), new.similarity.toarray(), atol=1e-6)
    assert not np.allclose(S.toarray(), S.T.toarray())  # truncation made S asymmetric
    assert np.allclose(new.score_batch(np.arange(40)), (matrix @ S.T).toarray(), atol=1e-5)
    assert not np.allclose((matrix @ S).toarray(), new.score_batch(np.arange(40)), atol=1e-5)


def test_legacy_popularity_api(world):
    model = PopularityRecommender().fit(world.interactions)
    assert model.recommend(0, 6) == POPULARITY_ORDER and model.recommend(4, 3) == [5, 2, 3]
    assert model.recommend(5, 3) == []  # saw everything: legacy API returns a SHORT list, never -1 padding
    assert model.recommend(99, 2) == [0, 1] and model.recommend(-1, 2) == [0, 1]  # unknown users behave like cold users


@pytest.mark.parametrize("top_k", [0, -1, 2.5, True, None])
def test_legacy_recommend_rejects_bad_top_k(world, top_k):
    with pytest.raises(ValueError, match="top_k"):
        PopularityRecommender().fit(world.interactions).recommend(0, top_k)


def test_legacy_fit_rejects_empty_or_incomplete_interactions():
    with pytest.raises(ValueError, match="empty"):
        PopularityRecommender().fit(pd.DataFrame({"user_idx": [], "item_idx": []}))
    with pytest.raises(ValueError, match="item_idx"):
        PopularityRecommender().fit(pd.DataFrame({"user_idx": [0]}))


def test_legacy_item_knn_cold_user_gets_popularity_and_warm_user_gets_cf(world):
    model = ItemKNNRecommender(neighbors=5).fit(world.interactions)
    assert model.recommend(0, 6) == POPULARITY_ORDER
    assert model.recommend(1, 5) == [1, 4, 5, 2, 3]  # u1 saw {0}: ordered by sim(0, i)
