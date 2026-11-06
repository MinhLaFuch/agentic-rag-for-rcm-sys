"""Shared recommender components used by both runtime and evaluation.

This module contains:
- Recommender base protocol
- Model factory (build_model)
- Interaction matrix builder
- Provenance tracking (fit metadata)
- Model metadata utilities (file hashes, split names)
- ItemKNN persistence utilities

All components are pure functions or protocols with no tool dependencies.
"""

from .recommender import Recommender
from .build_model import ALL_MODELS, build_model
from .build_interaction_matrix import build_interaction_matrix
from .fit_provenance import fit_provenance
from ._model_metadata import file_hash, mapping_hash, fit_split_names, item_knn_data_hash
from ._helper import _append_popular_unseen, _keep_top_neighbors, _user_item_matrix

__all__ = [
    "ALL_MODELS",
    "build_model",
    "build_interaction_matrix",
    "Recommender",
    "fit_provenance",
    "file_hash",
    "mapping_hash",
    "fit_split_names",
    "item_knn_data_hash",
    "_append_popular_unseen",
    "_keep_top_neighbors",
    "_user_item_matrix",
]
