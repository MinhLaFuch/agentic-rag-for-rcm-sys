"""
EDA cho item metadata (Phase 2, phần metadata — KHÔNG phải interaction
data, xem module riêng src/data/eda.py cho interaction).

Streaming, không load toàn bộ file vào RAM một lúc (mục XXVI — code
phải scale được, tránh việc "chạy được trên máy Claude" nhưng vỡ trên
máy thật với RAM hạn chế hơn).
"""

from __future__ import annotations

from pathlib import Path

from ._dataclass import MetadataStats
from ..loader import iter_jsonl_gz

def compute_metadata_stats(path: str | Path, limit: int | None = None) -> MetadataStats:
    """
    Tính thống kê completeness + phân phối category/store cho item
    metadata thật (jsonl.gz theo schema McAuley-Lab/Amazon-Reviews-2023).
    """
    stats = MetadataStats()
    for i, record in enumerate(iter_jsonl_gz(path)):
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
