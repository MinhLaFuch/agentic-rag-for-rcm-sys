"""Dựng recommender baseline từ config (``model.yaml → baselines``)."""

from __future__ import annotations

from .base import Recommender
from .bpr_mf import BPRMFRecommender
from .fallback import FallbackRecommender
from .item_knn import ItemKNNRecommender
from .popularity import PopularityRecommender
from .random_rec import RandomRecommender

ALL_MODELS = ["random", "popularity", "item_knn", "bpr_mf"]


def build_model(name: str, cfg: dict) -> Recommender:
    seed = cfg.get("seed", 42)
    if name == "random":
        return RandomRecommender(seed=seed)
    if name == "popularity":
        return PopularityRecommender()

    if name == "item_knn":
        model: Recommender = ItemKNNRecommender(**cfg.get("item_knn", {}))
    elif name == "bpr_mf":
        model = BPRMFRecommender(seed=seed, **cfg.get("bpr_mf", {}))
    else:
        raise ValueError(f"Unknown model '{name}'. Choose from {ALL_MODELS}")

    if cfg.get("popularity_fallback", True):
        return FallbackRecommender(model, PopularityRecommender())
    return model
