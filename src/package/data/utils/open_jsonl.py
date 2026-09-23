from pathlib import Path
import gzip
import json
from typing import Iterator

def open_jsonl(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)