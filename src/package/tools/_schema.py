"""Tool contracts (schema): columns, filter keys, order columns. Fixed in Python on purpose.

Runtime-tunable limits (max candidates, row caps, SQL time budget...) live in configs/agent/tools.yaml → _limits.py.
"""

ITEM_COLUMNS = (
    "item_id",  # namespaced "{domain}::{parent_asin}"
    "domain",
    "original_item_id",
    "title",
    "store",  # closest field to "brand" in Amazon Reviews 2023
    "price",  # REAL, NULL when missing (~55% in Video_Games)
    "average_rating",
    "rating_number",
    "main_category",
)

SCHEMA_HINT = (
    "items(item_id TEXT, domain TEXT, original_item_id TEXT, title TEXT, store TEXT, "
    "price REAL NULL, average_rating REAL, rating_number INTEGER, main_category TEXT); "
    "item_categories(item_id TEXT, category TEXT)  -- multi-label, one row per (item, category); "
    "items_fts(title, store, main_category, categories)  -- FTS5 table for full-text search"
)

FILTER_KEYS = {
    "domain",
    "price_min",
    "price_max",
    "include_missing_price",
    "min_rating",
    "min_rating_number",
    "categories_any",
    "categories_all",
    "store",
    "title_contains",
    "exclude_item_ids",
}
ORDER_COLUMNS = {"rating_number", "average_rating", "price"}
