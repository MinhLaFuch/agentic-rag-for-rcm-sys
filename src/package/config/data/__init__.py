# config/data/__init__.py
from .._paths import PathConfig
from ._amazon import AmazonCategory, list_categories, resolve_category

_paths = PathConfig(__file__)

AMAZON_RAW_DIR = _paths.raw("amazon")
AMAZON_PROCESSED_DIR = _paths.processed("amazon")


def list_amazon_categories() -> list[str]:
    """All category folders available under the Amazon raw directory."""
    return list_categories(AMAZON_RAW_DIR)


def get_amazon_category(category: str) -> AmazonCategory:
    """Look up a category by name, e.g. get_amazon_category("beauty") -> All_Beauty."""
    return resolve_category(category, AMAZON_RAW_DIR, AMAZON_PROCESSED_DIR)


__all__ = [
    "AMAZON_RAW_DIR",
    "AMAZON_PROCESSED_DIR",
    "AmazonCategory",
    "get_amazon_category",
    "list_amazon_categories",
]
