"""Resolve an Amazon category name (e.g. "beauty") to its raw/processed paths."""
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AmazonCategory:
    name: str            # exact folder name, e.g. "All_Beauty"
    raw_dir: Path        # <raw>/amazon/All_Beauty
    review_file: Path    # <raw_dir>/All_Beauty.jsonl.gz
    meta_file: Path      # <raw_dir>/meta_All_Beauty.jsonl.gz
    processed_dir: Path  # <processed>/amazon/All_Beauty (not created here)


