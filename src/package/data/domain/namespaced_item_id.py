"""Tạo item id có namespace 'Domain::asin' để asin trùng giữa các domain không đụng nhau."""

from __future__ import annotations

from .._schema import ITEM_ID_SEPARATOR


def namespaced_item_id(domain: str, parent_asin: str) -> str:
    return f"{domain}{ITEM_ID_SEPARATOR}{parent_asin}"
