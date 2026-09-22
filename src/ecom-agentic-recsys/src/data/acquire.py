from __future__ import annotations

from pathlib import Path
from typing import Any

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


def download_domain_reviews_direct(
    domain: str, output_path: str | Path, chunk_size: int = 1024 * 1024
) -> Path:
    """
    Cách đơn giản hơn nhiều so với datasets.load_dataset(): tải trực tiếp
    file .jsonl.gz gốc từ McAuley Lab (host tại UCSD, KHÔNG cần HuggingFace
    auth/token, không cần cài package `datasets`).

    URL pattern đã xác nhận qua README chính thức của dataset:
        https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/raw/review_categories/{domain}.jsonl.gz
        https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/raw/meta_categories/meta_{domain}.jsonl.gz

    LƯU Ý: hàm này cần chạy trên máy có internet đầy đủ — container hiện
    tại của Claude bị chặn network tới cả huggingface.co lẫn
    datarepo.eng.ucsd.edu (đã verify bằng curl, HTTP 403 host_not_allowed
    ở cả hai). Đây là lý do hàm được tách riêng để người dùng tự chạy.
    """
    import urllib.request

    url = (
        "https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/"
        f"raw/review_categories/{domain}.jsonl.gz"
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as response, open(output_path, "wb") as out_file:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)

    return output_path



    """Tải item metadata thật cho một domain."""
    from datasets import load_dataset

    ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        f"raw_meta_{domain}",
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    return ds["full"].to_pandas()
