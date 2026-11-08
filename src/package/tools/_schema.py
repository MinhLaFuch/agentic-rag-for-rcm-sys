"""Tool contracts (schema): columns, filter keys, order columns. Fixed in Python on purpose.

Runtime-tunable limits (max candidates, row caps, SQL time budget...) live in configs/agent/tools.yaml → _limits.py.
"""

from package.data._schema import ITEM_COLUMNS, SCHEMA_HINT

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
