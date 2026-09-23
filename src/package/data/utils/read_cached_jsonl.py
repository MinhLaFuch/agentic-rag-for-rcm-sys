import logging
from pathlib import Path

import pandas as pd

from .open_jsonl import open_jsonl

log = logging.getLogger(__name__)


def read_cached_jsonl(path: Path, cache_path: Path) -> pd.DataFrame:
    if cache_path.exists():
        log.info("Loading cached data from %s", cache_path)
        return pd.read_csv(cache_path, sep="|", low_memory=False)
    log.info("No cache found, parsing %s", path)
    frame = pd.DataFrame.from_records(open_jsonl(path))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, sep="|")
    return frame