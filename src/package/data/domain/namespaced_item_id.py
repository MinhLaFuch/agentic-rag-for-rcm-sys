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

from .._schema import ITEM_ID_SEPARATOR


def namespaced_item_id(domain: str, parent_asin: str) -> str:
    return f"{domain}{ITEM_ID_SEPARATOR}{parent_asin}"
