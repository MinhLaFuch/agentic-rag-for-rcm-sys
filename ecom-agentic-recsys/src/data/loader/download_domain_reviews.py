"""
Data acquisition cho Amazon Reviews 2023 (mục V, Phase 2).

LƯU Ý QUAN TRỌNG: module này đã được viết đầy đủ và đúng API thật của
HuggingFace `datasets`, nhưng CHƯA thể chạy thành công trong môi trường
container hiện tại vì `huggingface.co` bị chặn ở tầng network
(x-deny-reason: host_not_allowed — đã verify bằng curl).

BLOCKED:
REASON: môi trường container không cho phép egress tới huggingface.co /
  datasets-server.huggingface.co.
REQUIRED ACTION: chạy script này trên máy có internet đầy đủ (hoặc môi
  trường có allowlist huggingface.co), ví dụ:
    DOMAIN=Video_Games python scripts/run_eda.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def download_domain_reviews(domain: str, cache_dir: str | Path | None = None) -> pd.DataFrame:
    """
    Tải review data thật cho một domain từ McAuley-Lab/Amazon-Reviews-2023.

    Trả về DataFrame với các cột: user_id, parent_asin, rating, timestamp,
    title, text, helpful_vote, verified_purchase (đúng schema đã xác nhận
    ở docs/data_specification.md §1.1).
    """
    from datasets import load_dataset  # import cục bộ để module load được dù chưa cài datasets

    ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        f"raw_review_{domain}",
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    df = ds["full"].to_pandas()
    return df[
        [
            "user_id",
            "parent_asin",
            "rating",
            "timestamp",
            "title",
            "text",
            "helpful_vote",
            "verified_purchase",
        ]
    ]
