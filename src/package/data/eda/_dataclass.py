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


@dataclass
class SplitDiagnosis:
    """Kết quả chẩn đoán splits cho stage 3."""
    train_rows: int
    val_rows: int
    test_rows: int
    train_users: int
    val_users: int
    test_users: int
    train_items: int
    val_items: int
    test_items: int
    train_timestamp_min: int
    train_timestamp_max: int
    val_timestamp_min: int
    val_timestamp_max: int
    test_timestamp_min: int
    test_timestamp_max: int
    # Domain distribution
    train_domain_ratios: dict[str, float]
    val_domain_ratios: dict[str, float]
    test_domain_ratios: dict[str, float]
    # Target item coverage
    val_items_in_train_pct: float  # % val items seen in train (by unique item)
    test_items_in_train_pct: float  # % test items seen in train (by unique item)
    val_rows_with_train_item_pct: float  # % val rows whose item is in train
    test_rows_with_train_item_pct: float  # % test rows whose item is in train
    # User history coverage
    val_users_with_train_history_pct: float  # % val users seen in train
    test_users_with_train_history_pct: float  # % test users seen in train
    val_history_len_stats: dict[str, float]  # {min, median, p90} of train history length for val users
    test_history_len_stats: dict[str, float]  # {min, median, p90} of train history length for test users
    # Repeated user-item pairs; repeat events are not inherently leakage
    val_repeat_pairs_pct: float  # % val (user, item) pairs already in train
    test_repeat_pairs_pct: float  # % test (user, item) pairs already in train+val
    # Micro unique-pair catalog eligibility, NOT a macro Recall@K ceiling
    val_reachable_pct: float  # % unique val pairs: item in train and pair absent from train
    test_reachable_pct: float  # % unique test pairs: item in train+validation and pair absent from fit
    # Multi-domain users
    train_multi_domain_users_pct: float
    val_multi_domain_users_pct: float
    test_multi_domain_users_pct: float
    protocol: dict = field(default_factory=dict)
    fit_diagnostics: dict = field(default_factory=dict)
    domain_diagnostics: dict = field(default_factory=dict)
