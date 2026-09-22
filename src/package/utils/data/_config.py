"""Amazon raw lives in shared `resource/raw`. Processed defaults to `resource/local/processed`."""
from ..path import processed_dir, raw_dir

RAW_DIR = raw_dir()
PROCESSED_DIR = processed_dir()
