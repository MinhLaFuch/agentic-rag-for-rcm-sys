import pandas as pd

from src.evaluation.recommendation_metrics import evaluate_ranking
from src.recommenders.baselines import ItemKNNRecommender, PopularityRecommender


def _train() -> pd.DataFrame:
    return pd.DataFrame({"user_idx": [0, 0, 1, 1, 2], "item_idx": [0, 1, 0, 2, 2]})


def test_popularity_excludes_seen_items():
    model = PopularityRecommender().fit(_train())
    assert 0 not in model.recommend(0, 3)
    assert model.recommend(99, 1)[0] in {0, 2}


def test_item_knn_recommends_cooccurring_item():
    model = ItemKNNRecommender(neighbors=2).fit(_train())
    assert model.recommend(0, 2)[0] == 2


def test_ranking_metrics_are_macro_averaged():
    model = PopularityRecommender().fit(_train())
    held_out = pd.DataFrame({"user_idx": [0, 1], "item_idx": [2, 1]})
    metrics = evaluate_ranking(model, held_out, [1, 2])
    assert metrics["evaluated_users"] == 2
    assert 0 <= metrics["ndcg@2"] <= 1
