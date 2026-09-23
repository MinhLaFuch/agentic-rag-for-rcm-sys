from __future__ import annotations

import logging

import pandas as pd

from ...utils import raw_dir
from ..utils import REVIEW_SCHEMA, parse_list, read_cached_jsonl, resolve_category
from .join_description import join_description

log = logging.getLogger(__name__)


def load_reviews_and_metadata(
    category: str,
    max_description_sentences: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load + clean review and metadata tables for one category (jsonl.gz -> cached tsv -> cleaned).

    Cleaning: drop items with no title, join `description` into one string, take the
    first `categories` entry, rename `parent_asin` -> `item_id`, and keep only reviews
    whose item survived the meta cleaning.
    """
    name = resolve_category(category)
    raw = raw_dir(name)
    reviews_path = raw / f"{name}.jsonl.gz"
    meta_path = raw / f"meta_{name}.jsonl.gz"
    for path in (reviews_path, meta_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing file for category {name!r}: {path}")
    reviews = read_cached_jsonl(reviews_path, raw / "reviews.tsv")
    meta = read_cached_jsonl(meta_path, raw / "meta.tsv")

    meta = meta[meta["title"].notna()].copy()
    meta["description"] = meta.get("description", pd.Series(index=meta.index)).apply(
        lambda value: join_description(value, max_description_sentences)
    )
    categories = meta.get("categories", pd.Series(index=meta.index)).apply(parse_list)
    meta["category"] = categories.apply(lambda values: values[0] if values else "Unknown")

    reviews = reviews[list(REVIEW_SCHEMA.required)].rename(columns={"parent_asin": "item_id"})
    meta = meta[["parent_asin", "title", "category", "price", "description"]].rename(
        columns={"parent_asin": "item_id"}
    )
    meta = meta.drop_duplicates("item_id").reset_index(drop=True)
    reviews = reviews[reviews["item_id"].isin(meta["item_id"])].reset_index(drop=True)

    log.info("Loaded %s: reviews %s, meta %s", name, reviews.shape, meta.shape)
    return reviews, meta