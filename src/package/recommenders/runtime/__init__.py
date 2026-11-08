"""Runtime-capable recommender models used in agent tools.

These models are designed for online inference:
- Accept pandas DataFrame for flexible input
- Return direct item lists for use by tools
- Used by BaselineScorer, SimilarTool, RankTool

Models:
- PopularityRecommender: Popularity-based recommendations
- ItemKNNRecommender: Item-item collaborative filtering
- BaselinePopularityRecommender: DataFrame API for popularity
- BaselineItemKNNRecommender: DataFrame API for ItemKNN
"""

from .popularity_recommender import PopularityRecommender
from .item_knn_recommender import ItemKNNRecommender
from .baseline_popularity_recommender import BaselinePopularityRecommender
from .baseline_item_knn_recommender import BaselineItemKNNRecommender

__all__ = [
    "PopularityRecommender",
    "ItemKNNRecommender",
    "BaselinePopularityRecommender",
    "BaselineItemKNNRecommender",
]
