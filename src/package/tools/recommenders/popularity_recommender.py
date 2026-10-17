from __future__ import annotations

from .baseline_popularity_recommender import BaselinePopularityRecommender


class PopularityRecommender(BaselinePopularityRecommender):
    """Legacy DataFrame-based popularity recommender (plain name kept for existing callers).

    Identical to BaselinePopularityRecommender; the sparse-matrix implementation is PopularityMatrixRecommender.
    """

    pass
