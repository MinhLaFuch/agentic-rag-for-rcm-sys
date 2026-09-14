"""
utils/hashing.py

Helper cho việc chuẩn hóa URL và tạo product_id.

Nguyên tắc (theo yêu cầu #6):
- Ưu tiên product_id thực tế lấy từ URL/DOM.
- Nếu không lấy được, fallback = SHA256(normalized_product_url).
- KHÔNG dùng product_name làm primary key.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

# URL sản phẩm Shopee thường có dạng:
#   https://shopee.vn/<slug>-i.<shop_id>.<item_id>
# hoặc kèm query string phía sau.
_SHOPEE_ID_PATTERN = re.compile(r"-i\.(\d+)\.(\d+)")


def normalize_url(url: str) -> str:
    """Chuẩn hóa URL: bỏ query string + fragment, bỏ dấu `/` cuối,
    lowercase scheme/host — để cùng 1 sản phẩm luôn ra cùng 1 URL chuẩn
    hóa dù được crawl từ nhiều keyword khác nhau (phục vụ dedup).
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def sha256_hash(text: str) -> str:
    """SHA256 hex digest của `text` (dùng làm fallback product_id/data_hash)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_shopee_ids(url: str) -> tuple[str, str] | None:
    """Trích (shop_id, item_id) từ URL sản phẩm Shopee dạng chuẩn
    `...-i.<shop_id>.<item_id>`. Trả về None nếu không khớp pattern
    (không đoán mò — để tầng gọi tự fallback sang hash).
    """
    match = _SHOPEE_ID_PATTERN.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


def build_product_id(url: str) -> str:
    """Ưu tiên `shop_id_item_id` lấy từ URL thật; fallback SHA256 nếu
    không parse được (không bao giờ dùng product_name làm ID).
    """
    ids = extract_shopee_ids(url)
    if ids is not None:
        shop_id, item_id = ids
        return f"{shop_id}_{item_id}"
    return sha256_hash(normalize_url(url))
