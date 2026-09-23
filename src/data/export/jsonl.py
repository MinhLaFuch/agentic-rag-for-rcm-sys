from pathlib import Path
import json

def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            json.dump(record, stream, ensure_ascii=False)
            stream.write("\n")