"""Amazon raw lives in shared `resource/raw`. Processed defaults to `resource/local/processed`."""
from ..path import processed_dir, raw_dir

RAW_DIR = raw_dir()
PROCESSED_DIR = processed_dir()

REQUIRED_COLUMNS = ["user_id", "parent_asin", "rating", "timestamp"]
OPTIONAL_COLUMNS = ["title", "text", "helpful_vote", "verified_purchase"]
