# config/data/__init__.py
from .._paths import PathConfig

_paths = PathConfig(__file__)

RAW_DATA_DIR = _paths.raw_dir
PROCESSED_DATA_DIR = _paths.processed_dir

AMAZON_RAW_DIR = _paths.raw("amazon")
STEAM_RAW_DIR = _paths.raw("steam")
MOVIELENS_RAW_DIR = _paths.raw("ml")

AMAZON_PROCESSED_DIR = _paths.processed("amazon")
STEAM_PROCESSED_DIR = _paths.processed("steam")
MOVIELENS_PROCESSED_DIR = _paths.processed("ml")