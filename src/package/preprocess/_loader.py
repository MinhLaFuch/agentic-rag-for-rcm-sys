"""Load and clean the Amazon Reviews 2023 JSONL data."""
from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

import pandas as pd


def iter_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _read_cached_jsonl(path: Path, cache_path: Path, logger) -> pd.DataFrame:
    if cache_path.exists():
        logger.info("Loading cached data from %s", cache_path)
        return pd.read_csv(cache_path, sep="|", low_memory=False)
    logger.info("No cache found, parsing %s", path)
    frame = pd.DataFrame.from_records(iter_jsonl_gz(path))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, sep="|")
    return frame


def _parse_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def join_description(value, max_sentences: int = 2) -> str:
    values = _parse_list(value)
    return " ".join(str(item) for item in values[:max_sentences]) or "No description"


def load_reviews_and_meta(category, logger) -> tuple[pd.DataFrame, pd.DataFrame]:
    reviews = _read_cached_jsonl(category.review_file, category.raw_dir / "reviews.tsv", logger)
    meta = _read_cached_jsonl(category.meta_file, category.raw_dir / "meta.tsv", logger)
    logger.info("Shape of reviews: %s", reviews.shape)
    logger.info("Shape of meta: %s", meta.shape)
    return reviews, meta


def load_reviews_and_metadata(
    category, logger, max_description_sentences: int = 2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reviews, meta = load_reviews_and_meta(category, logger)
    meta = meta[meta["title"].notna()].copy()
    meta["description"] = meta.get("description", pd.Series(index=meta.index)).apply(
        lambda value: join_description(value, max_description_sentences)
    )
    categories = meta.get("categories", pd.Series(index=meta.index)).apply(_parse_list)
    meta["category"] = categories.apply(lambda values: values[0] if values else "Unknown")
    reviews = reviews[["user_id", "parent_asin", "rating", "timestamp"]].rename(
        columns={"parent_asin": "item_id"}
    )
    meta = meta[["parent_asin", "title", "category", "price", "description"]].rename(
        columns={"parent_asin": "item_id"}
    )
    return (
        reviews[reviews["item_id"].isin(meta["item_id"])].reset_index(drop=True),
        meta.drop_duplicates("item_id").reset_index(drop=True),
    )