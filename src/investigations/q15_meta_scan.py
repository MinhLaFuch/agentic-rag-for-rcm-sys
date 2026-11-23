"""Q15 raw-side: scan meta_*.jsonl.gz for category/main_category/rating_number
presence per parent_asin, to compare against processed corpus coverage
(source-data gap vs preprocessing drop).

Output: investigations/q15_meta_flags.parquet (domain, parent_asin,
has_categories, has_main_category, rating_number_raw)
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "resource/raw"
DOMAINS = ["Video_Games", "Toys_and_Games", "Electronics"]
OUT = Path(__file__).parent / "q15_meta_flags.parquet"


def nonempty(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and v.strip() not in ("None", "[]")
    try:
        return len(v) > 0
    except TypeError:
        return bool(v)


def main() -> None:
    rows = []
    for dom in DOMAINS:
        path = RAW / f"meta_{dom}.jsonl.gz"
        t0 = time.time()
        n = 0
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                asin = d.get("parent_asin")
                if not asin:
                    continue
                rows.append((dom, str(asin),
                             int(nonempty(d.get("categories"))),
                             int(nonempty(d.get("main_category"))),
                             str(d.get("rating_number") or "")))
                n += 1
        print(f"{dom}: {n:,} rows in {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows, columns=["domain", "parent_asin", "has_categories",
                                     "has_main_category", "rating_number_raw"])
    df.to_parquet(OUT, index=False)
    print(df.groupby("domain")[["has_categories", "has_main_category"]].mean())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
