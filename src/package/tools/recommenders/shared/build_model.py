"""Dựng recommender baseline từ config (``baselines.yaml → baselines``)."""

from __future__ import annotations

from .recommender import Recommender
from .bpr_mf_recommender import BPRMFRecommender
from .fallback_recommender import FallbackRecommender
from .item_knn_matrix_recommender import ItemKNNMatrixRecommender
from .popularity_matrix_recommender import PopularityMatrixRecommender
from .random_recommender import RandomRecommender

# Model registry: the ONLY list of buildable models (keep in sync with the branches in build_model).
ALL_MODELS = ["random", "popularity", "item_knn", "bpr_mf"]


def build_model(name: str, cfg: dict) -> Recommender:
    seed = cfg.get("seed", 42)
    if name == "random":
        return RandomRecommender(seed=seed)
    if name == "popularity":
        return PopularityMatrixRecommender()

    if name == "item_knn":
        model: Recommender = ItemKNNMatrixRecommender(**cfg.get("item_knn", {}))
    elif name == "bpr_mf":
        # a per-model "seed" overrides the top-level one (both used to crash: "multiple values for keyword 'seed'")
        model = BPRMFRecommender(**{"seed": seed, **cfg.get("bpr_mf", {})})
    else:
        raise ValueError(f"Unknown model '{name}'. Choose from {ALL_MODELS}")

    if cfg.get("popularity_fallback", True):
        return FallbackRecommender(model, PopularityMatrixRecommender())
    return model
