"""SQL queries for the corpus module.

This module defines:
- CREATE TABLE statements for the in-memory SQLite database
- Index definitions for query performance
- FTS5 full-text search configuration and population
"""
import hashlib

# ---- table schemas ------------------------------------------------------- #

# Main items table - stores item metadata
ITEMS_TABLE_SCHEMA = """
CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    original_item_id TEXT,
    first_seen_ts INTEGER,
    title TEXT,
    store TEXT,
    price REAL,
    average_rating REAL,
    rating_number REAL,
    main_category TEXT
)
"""

# Item categories table - multi-label categories (one row per item-category pair)
CATEGORIES_TABLE_SCHEMA = """
CREATE TABLE item_categories (
    item_id TEXT,
    category TEXT
)
"""

# FTS5 full-text search table for title, store, main_category, and categories
FTS_TABLE_SCHEMA = """
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, store, main_category, categories, tokenize='porter unicode61'
)
"""

# ---- indexes ------------------------------------------------------------- #

# Indexes for the items table
ITEMS_INDEXES = [
    "CREATE UNIQUE INDEX idx_items_id ON items(item_id)",
    "CREATE INDEX idx_items_domain ON items(domain)",
    "CREATE INDEX idx_items_price ON items(price)",
]

# Indexes for the item_categories table
CATEGORIES_INDEXES = [
    "CREATE INDEX idx_cat_item ON item_categories(item_id)",
    "CREATE INDEX idx_cat_cat ON item_categories(category)",
    "CREATE INDEX idx_cat_item_cat ON item_categories(item_id, category)",
]

# ---- FTS5 population ---------------------------------------------------- #

# SQL to populate FTS5 table from items and item_categories
# External-content FTS cannot include categories directly, so we copy rowids
FTS_POPULATE_SQL = """
INSERT INTO items_fts(rowid, title, store, main_category, categories)
SELECT i.rowid, i.title, i.store, i.main_category,
       COALESCE((SELECT group_concat(c.category, ' ') FROM item_categories c
                 WHERE c.item_id = i.item_id), '')
FROM items i
"""

# ---- schema fingerprint ------------------------------------------------- #

# Version of the from_dataframe logic - increment when changing construction logic
CORPUS_LOGIC_VERSION = 2

# Fingerprint of the schema (CREATE TABLE, CREATE INDEX, FTS) - used to detect outdated corpus files
# This hash is computed from the SQL strings above; if _sql.py changes, regenerate this hash.
_CORPUS_SCHEMA_FINGERPRINT = hashlib.sha256(
    (
        ITEMS_TABLE_SCHEMA +
        CATEGORIES_TABLE_SCHEMA +
        FTS_TABLE_SCHEMA +
        "".join(ITEMS_INDEXES) +
        "".join(CATEGORIES_INDEXES) +
        FTS_POPULATE_SQL
    ).encode("utf-8")
).hexdigest()

def get_corpus_schema_fingerprint() -> str:
    """Return the schema fingerprint for corpus file validation."""
    return _CORPUS_SCHEMA_FINGERPRINT
