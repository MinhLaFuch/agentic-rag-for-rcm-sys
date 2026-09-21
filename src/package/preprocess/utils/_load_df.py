"""Load reviews and metadata for one Amazon category, each on its own."""
from __future__ import annotations

import pandas as pd

from package.utils.data import AmazonCategory, get_amazon_category


def _resolve(category: AmazonCategory | str) -> AmazonCategory:
    """Accept an AmazonCategory or a plain name like "beauty"."""
    return get_amazon_category(category) if isinstance(category, str) else category


def load_review_df(category: AmazonCategory | str) -> pd.DataFrame:
    """Read the category's review file (jsonl.gz), keeping only REVIEW_COLUMNS."""
    category = _resolve(category)
    return pd.read_json(category.review_file, lines=True)


def load_meta_df(category: AmazonCategory | str) -> pd.DataFrame:
    """Read the category's meta file (jsonl.gz), keeping only META_COLUMNS, one row per item."""
    category = _resolve(category)
    meta = pd.read_json(category.meta_file, lines=True)
    return meta.drop_duplicates(subset=["parent_asin"])


def merge_df(reviews: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Inner-merge reviews with metadata on parent_asin -> canonical table."""
    return reviews.merge(meta, on="parent_asin", how="inner")