"""Dataclass kết quả của các hàm EDA (interaction, streaming, metadata)."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter

@dataclass
class InteractionStats:
    num_users: int
    num_items: int
    num_interactions: int
    sparsity: float  # 1 - num_interactions / (num_users * num_items)
    avg_interactions_per_user: float
    median_interactions_per_user: float
    p90_interactions_per_user: float
    timestamp_min: int
    timestamp_max: int

@dataclass
class StreamingInteractionStats:
    """
    Giống InteractionStats nhưng tính bằng streaming (không load toàn bộ
    file vào RAM cùng lúc) — dùng cho file review lớn (Video_Games có
    ~4.6M dòng) chạy trên máy người dùng, không cần pandas load hết.
    """

    num_interactions: int = 0
    num_users: int = 0
    num_items: int = 0
    timestamp_min: int | None = None
    timestamp_max: int | None = None
    rating_sum: float = 0.0
    interactions_per_user: dict = field(default_factory=dict)

@dataclass
class MetadataStats:
    num_items: int = 0
    num_missing_price: int = 0
    num_missing_description: int = 0
    num_missing_features: int = 0
    num_missing_store: int = 0
    num_missing_average_rating: int = 0
    category_counter: Counter = field(default_factory=Counter)
    store_counter: Counter = field(default_factory=Counter)
    rating_number_sum: float = 0
    average_rating_sum: float = 0.0
    num_with_average_rating: int = 0

    @property
    def pct_missing_price(self) -> float:
        return self.num_missing_price / self.num_items if self.num_items else 0.0

    @property
    def pct_missing_description(self) -> float:
        return self.num_missing_description / self.num_items if self.num_items else 0.0

    @property
    def pct_missing_features(self) -> float:
        return self.num_missing_features / self.num_items if self.num_items else 0.0

    @property
    def pct_missing_store(self) -> float:
        return self.num_missing_store / self.num_items if self.num_items else 0.0

    @property
    def avg_rating_number(self) -> float:
        return self.rating_number_sum / self.num_items if self.num_items else 0.0

    @property
    def avg_average_rating(self) -> float:
        return (
            self.average_rating_sum / self.num_with_average_rating
            if self.num_with_average_rating
            else 0.0
        )