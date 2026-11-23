import sys
import sqlite3
from pathlib import Path

src_dir = Path(__file__).resolve().parents[2]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import json
from package.config import get_data_paths
from package.corpus import get_corpus_schema_fingerprint, CORPUS_LOGIC_VERSION

paths = get_data_paths()
print("Corpus path:", paths.corpus_path)
meta_path = paths.corpus_path.with_suffix(".meta.json")
meta = json.loads(meta_path.read_text(encoding="utf-8"))
print("Current schema fingerprint:", get_corpus_schema_fingerprint())
print("Saved schema fingerprint:  ", meta.get("schema_fingerprint"))
print("Fingerprints match?        ", get_corpus_schema_fingerprint() == meta.get("schema_fingerprint"))

conn = sqlite3.connect(paths.corpus_path)
cur = conn.cursor()
cur.execute("PRAGMA table_info(items)")
cols = [row[1] for row in cur.fetchall()]
print("Columns in items table:", cols)
cur.execute("SELECT COUNT(*) FROM items")
print("Total rows in items table:", cur.fetchone()[0])
conn.close()
