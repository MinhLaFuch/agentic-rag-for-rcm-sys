# DataFrame-based recommenders (used in agent tools: BaselineScorer, ItemCFTool, RecoModelTool)
# These accept pandas DataFrame and return direct item lists
from .baseline_popularity import PopularityRecommender
from .baseline_item_knn import ItemKNNRecommender

# Matrix-based recommenders (used in evaluation pipeline and experiments)
# These accept sparse CSR matrix and return scores, with recommend() for top-k extraction
from .base import Recommender
from .popularity import PopularityRecommender as PopularityMatrixRecommender
from .item_knn import ItemKNNRecommender as ItemKNNMatrixRecommender
from .bpr_mf import BPRMFRecommender
from .random_rec import RandomRecommender
from .fallback import FallbackRecommender

# Utilities
from .build_interaction_matrix import build_interaction_matrix
from .factory import ALL_MODELS, build_model

# Legacy aliases for backward compatibility (will be deprecated in future).
# NOTE: despite the "ABC" suffix these are the CONCRETE sparse-matrix classes, not abstract base classes.
# The DataFrame-API and matrix-API ItemKNN agree only when no top-k truncation happens (see
# tests/tools/recommenders/test_contract_recommenders.py): they score in opposite orientations.
ItemKNNRecommenderABC = ItemKNNMatrixRecommender
PopularityRecommenderABC = PopularityMatrixRecommender

__all__ = [
    "ALL_MODELS",
    "build_model",
    "build_interaction_matrix",
    "Recommender",
    "BPRMFRecommender",
    "FallbackRecommender",
    "RandomRecommender",
    # DataFrame-based (for agent tools)
    "ItemKNNRecommender",
    "PopularityRecommender",
    # Matrix-based (for evaluation/experiments)
    "ItemKNNMatrixRecommender",
    "PopularityMatrixRecommender",
    # Legacy aliases (deprecated)
    "ItemKNNRecommenderABC",
    "PopularityRecommenderABC",
]
