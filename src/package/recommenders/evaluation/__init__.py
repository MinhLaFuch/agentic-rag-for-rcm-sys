"""Evaluation-only recommender models used in offline experiments.

These models are designed for offline evaluation and benchmarking:
- Accept sparse CSR matrix for efficient batch operations
- Return scores for top-k extraction
- Used in training pipelines, candidate recall experiments, ranking evaluation

Models:
- PopularityMatrixRecommender: Matrix-based popularity for evaluation
- ItemKNNMatrixRecommender: Matrix-based ItemKNN for evaluation
- BPRMFRecommender: Bayesian Personalized Ranking Matrix Factorization
- RandomRecommender: Random baseline for evaluation
- FallbackRecommender: Fallback strategy for evaluation
"""

from .popularity_matrix_recommender import PopularityMatrixRecommender
from .item_knn_matrix_recommender import ItemKNNMatrixRecommender
from .bpr_mf_recommender import BPRMFRecommender
from .random_recommender import RandomRecommender
from .fallback_recommender import FallbackRecommender

__all__ = [
    "PopularityMatrixRecommender",
    "ItemKNNMatrixRecommender",
    "BPRMFRecommender",
    "RandomRecommender",
    "FallbackRecommender",
]
