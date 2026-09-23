from pathlib import Path
import pandas as pd
from .open_jsonl import open_jsonl

def read_cached_jsonl(path: Path, cache_path: Path, logger) -> pd.DataFrame:
    if cache_path.exists():
        logger.info("Loading cached data from %s", cache_path)
        return pd.read_csv(cache_path, sep="|", low_memory=False)
    logger.info("No cache found, parsing %s", path)
    frame = pd.DataFrame.from_records(open_jsonl(path))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, sep="|")
    return frame