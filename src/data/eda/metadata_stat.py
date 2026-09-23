from dataclasses import dataclass, field
from collections import Counter

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
    rating_number_sum: int = 0
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