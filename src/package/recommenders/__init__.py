"""Recommender models for runtime and offline evaluation.

This module is organized into three subdirectories:
- runtime/: Runtime-capable models used in agent tools (DataFrame API)
- evaluation/: Evaluation-only models used in offline experiments (Matrix API)
- shared/: Shared components (protocols, factories, utilities)

Re-export for backward compatibility:
"""

# Runtime models (DataFrame API, used in agent tools)
from .runtime import (
    PopularityRecommender,
    ItemKNNRecommender,
    BaselinePopularityRecommender,
    BaselineItemKNNRecommender,
)

# Evaluation models (Matrix API, used in offline experiments)
from .evaluation import (
    PopularityMatrixRecommender,
    ItemKNNMatrixRecommender,
    BPRMFRecommender,
    RandomRecommender,
    FallbackRecommender,
)

# Shared components
from .shared import (
    Recommender,
    ALL_MODELS,
    build_model,
    build_interaction_matrix,
    fit_provenance,
    file_hash,
    mapping_hash,
    fit_split_names,
    item_knn_data_hash,
)

# ItemKNN persistence (imported directly to avoid circular dependencies)
from .shared.load_item_knn import load_item_knn
from .shared.save_item_knn import save_item_knn

# Legacy aliases for backward compatibility (will be deprecated in future).
# NOTE: despite the "ABC" suffix these are the CONCRETE sparse-matrix classes, not abstract base classes.
# The DataFrame-API and matrix-API ItemKNN agree only when no top-k truncation happens (see
# tests/tools/recommenders/test_contract_recommenders.py): they score in opposite orientations.
ItemKNNRecommenderABC = ItemKNNMatrixRecommender
PopularityRecommenderABC = PopularityMatrixRecommender

__all__ = [
    # Runtime models
    "PopularityRecommender",
    "ItemKNNRecommender",
    "BaselinePopularityRecommender",
    "BaselineItemKNNRecommender",
    # Evaluation models
    "PopularityMatrixRecommender",
    "ItemKNNMatrixRecommender",
    "BPRMFRecommender",
    "RandomRecommender",
    "FallbackRecommender",
    # Shared components
    "Recommender",
    "ALL_MODELS",
    "build_model",
    "build_interaction_matrix",
    "fit_provenance",
    "file_hash",
    "mapping_hash",
    "fit_split_names",
    "item_knn_data_hash",
    "load_item_knn",
    "save_item_knn",
    # Legacy aliases (deprecated)
    "ItemKNNRecommenderABC",
    "PopularityRecommenderABC",
]
