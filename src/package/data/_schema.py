"""Schema/protocol constants for the data package (changing them changes the data contract, so they stay in Python)."""

REQUIRED_COLUMNS = ["user_id", "parent_asin", "rating", "timestamp"]
OPTIONAL_COLUMNS = ["title", "text", "helpful_vote", "verified_purchase"]
ITEM_ID_SEPARATOR = "::"

# Item corpus schema constants (shared between corpus and tools)
ITEM_COLUMNS = (
    "item_id",  # namespaced "{domain}::{parent_asin}"
    "domain",
    "original_item_id",
    "first_seen_ts",  # earliest cleaned interaction; proxy, not actual launch date
    "title",
    "store",  # closest field to "brand" in Amazon Reviews 2023
    "brand",  # extracted from details["Brand"]
    "release_date",  # extracted from details["Release date"] / "Date First Available"
    "price",  # REAL, NULL when missing (~55% in Video_Games)
    "average_rating",
    "rating_number",
    "main_category",
    "features",  # normalized bullet features text from metadata
)

SCHEMA_HINT = (
    "items(item_id TEXT, domain TEXT, original_item_id TEXT, first_seen_ts INTEGER, title TEXT, store TEXT, "
    "brand TEXT, release_date TEXT, price REAL NULL, average_rating REAL, rating_number REAL, main_category TEXT, "
    "features TEXT); "
    "item_categories(item_id TEXT, category TEXT)  -- multi-label, one row per (item, category); "
    "items_fts(title, store, brand, main_category, categories, features)  -- FTS5 table for full-text search"
)
