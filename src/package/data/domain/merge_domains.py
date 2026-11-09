"""Gộp các DataFrame đã gắn domain thành một bảng interaction đa-domain."""

from __future__ import annotations

import pandas as pd
from pandas.api.types import union_categoricals


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

    # Keep category-encoded item/domain columns encoded across domains. Pandas
    # otherwise may coerce categories with different vocabularies to object,
    # recreating one Python object per event during concat.
    categorical_columns = [
        column
        for column in ("parent_asin", "original_item_id", "domain")
        if all(
            column in frame.columns and isinstance(frame[column].dtype, pd.CategoricalDtype)
            for frame in tagged_dfs
        )
    ]
    aligned = tagged_dfs
    if categorical_columns:
        category_sets = {
            column: union_categoricals([frame[column].array for frame in tagged_dfs]).categories
            for column in categorical_columns
        }
        aligned = []
        for frame in tagged_dfs:
            view = frame.copy(deep=False)
            for column, categories in category_sets.items():
                view[column] = frame[column].cat.set_categories(categories)
            aligned.append(view)

    return pd.concat(aligned, ignore_index=True)
