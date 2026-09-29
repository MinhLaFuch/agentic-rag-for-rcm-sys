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

from .namespaced_item_id import namespaced_item_id


def tag_domain(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """
    Gắn domain vào một DataFrame interaction đã clean (có cột
    user_id, parent_asin, rating, timestamp):
      - thêm cột `domain`
      - thêm cột `original_item_id` (giữ giá trị parent_asin gốc, để
        truy vết ngược lại metadata gốc của domain đó)
      - overwrite `parent_asin` thành item id đã namespace

    `user_id` GIỮ NGUYÊN, không đổi (xem docstring module).
    """
    if "parent_asin" not in df.columns:
        raise ValueError("DataFrame must have a 'parent_asin' column")

    out = df.copy()
    out["domain"] = domain
    out["original_item_id"] = out["parent_asin"]
    out["parent_asin"] = out["parent_asin"].apply(lambda x: namespaced_item_id(domain, x))
    return out
