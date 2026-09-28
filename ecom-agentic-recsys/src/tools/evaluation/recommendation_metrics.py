"""Ranking metrics for implicit-feedback recommendation experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Protocol

import pandas as pd


class Recommender(Protocol):
    def recommend(self, user_idx: int, top_k: int) -> list[int]: ...


def evaluate_ranking(
    model: Recommender, interactions: pd.DataFrame, k_values: list[int]
) -> dict[str, float]:
    """Macro-average metrics over users with at least one held-out item."""
    if not k_values or min(k_values) <= 0:
        raise ValueError("k_values must contain positive integers")
    truth: dict[int, set[int]] = defaultdict(set)
    for user_idx, item_idx in interactions[["user_idx", "item_idx"]].itertuples(index=False):
        truth[int(user_idx)].add(int(item_idx))

    totals = {f"{metric}@{k}": 0.0 for k in k_values for metric in (
        "precision", "recall", "hit_rate", "ndcg", "mrr", "map"
    )}
    max_k = max(k_values)
    for user_idx, relevant in truth.items():
        recommendations = model.recommend(user_idx, max_k)
        for k in k_values:
            predicted = recommendations[:k]
            hits = [item in relevant for item in predicted]
            num_hits = sum(hits)
            totals[f"precision@{k}"] += num_hits / k
            totals[f"recall@{k}"] += num_hits / len(relevant)
            totals[f"hit_rate@{k}"] += float(num_hits > 0)
            dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
            ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(relevant), k)))
            totals[f"ndcg@{k}"] += dcg / ideal if ideal else 0.0
            first_hit = next((rank + 1 for rank, hit in enumerate(hits) if hit), None)
            totals[f"mrr@{k}"] += 1 / first_hit if first_hit else 0.0
            precisions = [sum(hits[: rank + 1]) / (rank + 1) for rank, hit in enumerate(hits) if hit]
            totals[f"map@{k}"] += sum(precisions) / min(len(relevant), k) if precisions else 0.0

    num_users = len(truth)
    return {"evaluated_users": num_users, **{key: value / num_users for key, value in totals.items()}}
