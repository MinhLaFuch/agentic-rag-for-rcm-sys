"""Load and clean the Amazon Reviews 2023 JSONL data."""
from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

import pandas as pd

from utils.path import raw_dir
from package.utils.log import setup_logging
from utils.log import experiment_log_path

from .paths import category_name
from .config import REQUIRED_COLUMNS, OPTIONAL_COLUMNS

_LOGGER = None


def _logger(logger, workspace: str | None = None):
    global _LOGGER
    if logger is not None:
        return logger
    if _LOGGER is None:
        log_path = experiment_log_path("process", "amazon_preprocess", workspace=workspace)
        _LOGGER = setup_logging("process", log_file=log_path)
    return _LOGGER


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


def load_reviews_and_metadata(
    category: str,
    logger=None,
    max_description_sentences: int = 2,
    workspace: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load + clean review and metadata tables for one category (jsonl.gz -> cached tsv -> cleaned).

    Cleaning: drop items with no title, join `description` into one string, take the
    first `categories` entry, rename `parent_asin` -> `item_id`, and keep only reviews
    whose item survived the meta cleaning.
    """
    logger = _logger(logger, workspace)
    name = category_name(category)
    raw = raw_dir(name)
    reviews_path = raw / f"{name}.jsonl.gz"
    meta_path = raw / f"meta_{name}.jsonl.gz"
    for path in (reviews_path, meta_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing file for category {name!r}: {path}")
    reviews = _read_cached_jsonl(reviews_path, raw / "reviews.tsv", logger)
    meta = _read_cached_jsonl(meta_path, raw / "meta.tsv", logger)

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
    meta = meta.drop_duplicates("item_id").reset_index(drop=True)
    reviews = reviews[reviews["item_id"].isin(meta["item_id"])].reset_index(drop=True)

    logger.info("Shape of reviews: %s", reviews.shape)
    logger.info("Shape of meta: %s", meta.shape)
    return reviews, meta