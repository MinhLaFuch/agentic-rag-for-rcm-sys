from package.data.utils import resolve_category
import pandas as pd
from ..utils import read_cached_jsonl, parse_list
from . import join_description
from ...utils import raw_dir

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
    # Use provided logger or create a simple print-based fallback
    if logger is None:
        class SimpleLogger:
            def info(self, msg, *args):
                print(msg % args if args else msg)
        logger = SimpleLogger()

    name = resolve_category(category)
    raw = raw_dir(name)
    reviews_path = raw / f"{name}.jsonl.gz"
    meta_path = raw / f"meta_{name}.jsonl.gz"
    for path in (reviews_path, meta_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing file for category {name!r}: {path}")
    reviews = read_cached_jsonl(reviews_path, raw / "reviews.tsv", logger)
    meta = read_cached_jsonl(meta_path, raw / "meta.tsv", logger)

    meta = meta[meta["title"].notna()].copy()
    meta["description"] = meta.get("description", pd.Series(index=meta.index)).apply(
        lambda value: join_description(value, max_description_sentences)
    )
    categories = meta.get("categories", pd.Series(index=meta.index)).apply(parse_list)
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