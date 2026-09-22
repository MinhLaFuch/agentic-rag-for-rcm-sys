
from __future__ import annotations

import gzip
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


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


def _iter_jsonl_gz(path: str | Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def compute_metadata_stats(path: str | Path, limit: int | None = None) -> MetadataStats:
    """
    Tính thống kê completeness + phân phối category/store cho item
    metadata thật (jsonl.gz theo schema McAuley-Lab/Amazon-Reviews-2023).
    """
    stats = MetadataStats()
    for i, record in enumerate(_iter_jsonl_gz(path)):
        if limit is not None and i >= limit:
            break
        stats.num_items += 1

        if record.get("price") in (None, "", "null"):
            stats.num_missing_price += 1

        if not record.get("description"):
            stats.num_missing_description += 1

        if not record.get("features"):
            stats.num_missing_features += 1

        store = record.get("store")
        if not store:
            stats.num_missing_store += 1
        else:
            stats.store_counter[store] += 1

        for cat in record.get("categories", []) or []:
            stats.category_counter[cat] += 1

        rating_number = record.get("rating_number")
        if isinstance(rating_number, (int, float)):
            stats.rating_number_sum += rating_number

        avg_rating = record.get("average_rating")
        if isinstance(avg_rating, (int, float)):
            stats.average_rating_sum += avg_rating
            stats.num_with_average_rating += 1
        else:
            stats.num_missing_average_rating += 1

    return stats
