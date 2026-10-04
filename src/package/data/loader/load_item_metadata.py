"""
Đọc metadata item (``meta_<Domain>.jsonl.gz``) theo dòng, chỉ giữ item cần dùng.
Dùng chung cho run_tools.py và candidate_recall.py.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

import pandas as pd

from .iter_jsonl_gz import iter_jsonl_gz

META_FIELDS = [
    "parent_asin",
    "title",
    "store",
    "price",
    "average_rating",
    "rating_number",
    "main_category",
    "categories",
]


def load_item_metadata(
    meta_files: Iterable[tuple[str, str]],
    keep: Callable[[str, str], bool] | None = None,
    fields: list[str] = META_FIELDS,
) -> pd.DataFrame:
    """
    meta_files: các cặp (domain, đường_dẫn_file_meta).
    keep(domain, parent_asin) -> True nếu giữ item đó; None = giữ tất cả.
    Trả về DataFrame có các cột ``fields`` + ``domain``.
    """
    frames = []
    for domain, path in meta_files:
        started = time.time()
        rows = []
        for record in iter_jsonl_gz(path):
            asin = record.get("parent_asin")
            if keep is None or keep(domain, asin):
                rows.append({k: record.get(k) for k in fields})
        df = pd.DataFrame(rows, columns=fields)
        df["domain"] = domain
        print(f"  {domain}: kept {len(df):,} items with metadata ({time.time() - started:.0f}s)")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
