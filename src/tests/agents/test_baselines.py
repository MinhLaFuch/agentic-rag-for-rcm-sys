import pandas as pd

from package.tools.evaluation import evaluate_ranking
from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender


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


def test_item_knn_recommend_returns_exactly_top_k_when_neighbours_already_fill_the_list():
    # user 0 has seen {0, 1}; the only neighbour-scored item is 2, while items 3 and 4 are unseen and popular enough to
    # be appended: the old fill loop never stopped once the list was already full and returned [2, 3, 4].
    frame = pd.DataFrame({"user_idx": [0, 0, 1, 1, 2, 2], "item_idx": [0, 1, 0, 2, 3, 4]})
    assert ItemKNNRecommender(neighbors=2).fit(frame).recommend(0, 1) == [2]
    assert len(PopularityRecommender().fit(frame).recommend(0, 1)) == 1
