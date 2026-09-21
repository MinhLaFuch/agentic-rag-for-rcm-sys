"""Load review + metadata cục bộ rồi merge thành bảng canonical."""
import os

import pandas as pd

from package.preprocess.config import DEFAULT_LOCAL_DATA_DIR


def _find_file(filename: str, category: str, data_dir: str) -> str | None:
    for base in (data_dir, os.path.join(data_dir, category), os.path.join(data_dir, "amazon", category)):
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return path
    return None


def load_canonical_table(category: str, data_dir: str = DEFAULT_LOCAL_DATA_DIR) -> pd.DataFrame:
    review_path = _find_file(f"{category}.jsonl.gz", category, data_dir)
    meta_path = _find_file(f"meta_{category}.jsonl.gz", category, data_dir)
    if not (review_path and meta_path):
        raise FileNotFoundError(
            f"Không tìm thấy data local cho category={category!r} trong {data_dir} "
            f"(review={review_path}, meta={meta_path})"
        )

    reviews = pd.read_json(review_path, lines=True)[["user_id", "parent_asin", "rating", "timestamp"]]
    meta = pd.read_json(meta_path, lines=True)[["parent_asin", "title", "average_rating", "rating_number", "categories"]]
    meta = meta.drop_duplicates(subset=["parent_asin"])
    return reviews.merge(meta, on="parent_asin", how="inner")