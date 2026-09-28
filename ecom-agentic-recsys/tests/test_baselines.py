import numpy as np
import pandas as pd

from src.data.interactions import build_interaction_matrix
from src.evaluation.evaluator import evaluate_recommender
from src.evaluation.tuning import merge_model_params, parameter_grid
from src.recommenders.item_knn import ItemKNNRecommender
from src.recommenders.popularity import PopularityRecommender


def _train_matrix():
    frame = pd.DataFrame({"user_idx": [0, 0, 1, 1, 2], "item_idx": [0, 1, 0, 2, 2]})
    return build_interaction_matrix(frame, num_users=3, num_items=3)


def test_popularity_excludes_seen_items():
    train = _train_matrix()
    model = PopularityRecommender().fit(train)

    recommendations = model.recommend(np.array([0]), k=1, exclude=train)
    assert recommendations.tolist() == [[2]]


def test_item_knn_recommends_cooccurring_item():
    train = _train_matrix()
    model = ItemKNNRecommender(k=2, block_elements=100).fit(train)

    recommendations = model.recommend(np.array([0]), k=1, exclude=train)
    assert recommendations.tolist() == [[2]]


def test_evaluator_reports_segments_and_metrics():
    train = _train_matrix()
    target = build_interaction_matrix(
        pd.DataFrame({"user_idx": [0, 1], "item_idx": [2, 1]}), num_users=3, num_items=3
    )
    result = evaluate_recommender(PopularityRecommender().fit(train), train, target, [1], sparse_max=4)

    assert result.num_users["all"] == 2
    assert 0 <= result.overall["ndcg@1"] <= 1
    assert result.num_users["sparse"] == 2


def test_tuning_grid_and_parameter_override_do_not_mutate_base_config():
    base = {"item_knn": {"k": 20, "block_elements": 100}}
    assert parameter_grid({"k": [10, 20]}) == [{"k": 10}, {"k": 20}]

    updated = merge_model_params(base, "item_knn", {"k": 50})
    assert updated["item_knn"] == {"k": 50, "block_elements": 100}
    assert base["item_knn"]["k"] == 20
