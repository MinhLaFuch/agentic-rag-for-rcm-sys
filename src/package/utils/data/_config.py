"""Where Amazon raw/processed data lives on disk: resource/data/{raw,processed}/<category>."""
from ..path import processed_dir, raw_dir

RAW_DIR = raw_dir(__file__)
PROCESSED_DIR = processed_dir(__file__)