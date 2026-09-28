import json
import gzip
from pathlib import Path
from typing import Iterator

def iter_jsonl_gz(path: str | Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)