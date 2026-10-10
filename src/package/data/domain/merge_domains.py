"""Gộp các DataFrame đã gắn domain thành một bảng interaction đa-domain."""

from __future__ import annotations

import pandas as pd


def merge_domains(tagged_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Gộp nhiều DataFrame đã tag_domain() thành 1 DataFrame thống nhất.
    Không dedupe theo (user_id, parent_asin, timestamp) ở đây — việc đó
    thuộc `src/data/clean.py::clean_interactions`, nên chạy merge_domains
    TRƯỚC bước clean cuối cùng nếu cần dedupe toàn cục, hoặc chạy
    clean_interactions lại sau merge để an toàn double-check.
    """
    if not tagged_dfs:
        raise ValueError("tagged_dfs must not be empty")

    missing_domain_col = [i for i, df in enumerate(tagged_dfs) if "domain" not in df.columns]
    if missing_domain_col:
        raise ValueError(
            f"DataFrame(s) at index {missing_domain_col} chưa được tag_domain() "
            "trước khi merge."
        )

    return pd.concat(tagged_dfs, ignore_index=True)
