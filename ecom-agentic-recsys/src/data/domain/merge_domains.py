"""
Domain registry cho multi-domain recommendation (bổ sung theo yêu cầu
người dùng — xem docs/decisions.md D-010).

Nguyên tắc thiết kế quan trọng:
  - `user_id` trong Amazon Reviews 2023 là ID GLOBAL, chia sẻ giữa mọi
    category (cùng 1 user thật có thể xuất hiện ở cả Video_Games và
    Toys_and_Games với CÙNG user_id). => KHÔNG namespace user_id — đây
    chính là cơ chế giúp cross-domain giảm cold-start (mục V/D-010).
  - `parent_asin` thì KHÔNG global — 2 domain khác nhau có thể (hiếm
    nhưng không phải không thể) trùng giá trị asin nếu xử lý dữ liệu
    sai. => PHẢI namespace item_id theo domain: "{domain}::{parent_asin}"
    để đảm bảo an toàn, tránh việc code vô tình gộp nhầm 2 item khác
    nhau thành 1.
"""

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
