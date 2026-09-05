from pathlib import Path

# This file lives at: src/config/data/__init__.py
# parents[0] = src/config/data
# parents[1] = src/config
# parents[2] = src
# parents[3] = repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_ROOT = REPO_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"

AMAZON_RAW_DIR = RAW_DATA_DIR / "amazon"
STEAM_RAW_DIR = RAW_DATA_DIR / "steam"
MOVIELENS_RAW_DIR = RAW_DATA_DIR / "ml"

AMAZON_PROCESSED_DIR = PROCESSED_DATA_DIR / "amazon"
STEAM_PROCESSED_DIR = PROCESSED_DATA_DIR / "steam"
MOVIELENS_PROCESSED_DIR = PROCESSED_DATA_DIR / "ml"