from __future__ import annotations

from .baseline_item_knn_recommender import BaselineItemKNNRecommender


class ItemKNNRecommender(BaselineItemKNNRecommender):
    """Legacy DataFrame-based item-kNN recommender (plain name kept for existing callers).

    Identical to BaselineItemKNNRecommender; the sparse-matrix implementation is ItemKNNMatrixRecommender.
    """

    pass
