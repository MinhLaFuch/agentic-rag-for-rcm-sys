from pathlib import Path
from .._parent_path import find_repo_root

_REPO_ROOT = find_repo_root(__file__)
_DATA_ROOT = _REPO_ROOT / "data"

RAW_DATA_DIR = _DATA_ROOT / "raw"
PROCESSED_DATA_DIR = _DATA_ROOT / "processed"

AMAZON_RAW_DIR = RAW_DATA_DIR / "amazon"
STEAM_RAW_DIR = RAW_DATA_DIR / "steam"
MOVIELENS_RAW_DIR = RAW_DATA_DIR / "ml"

AMAZON_PROCESSED_DIR = PROCESSED_DATA_DIR / "amazon"
STEAM_PROCESSED_DIR = PROCESSED_DATA_DIR / "steam"
MOVIELENS_PROCESSED_DIR = PROCESSED_DATA_DIR / "ml"

