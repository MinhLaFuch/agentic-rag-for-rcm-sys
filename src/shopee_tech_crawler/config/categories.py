"""
config/categories.py

Danh sách category/keyword cho ngành hàng "Thiết bị công nghệ".
Crawler KHÔNG được hard-code category trực tiếp — tất cả đọc từ đây.

Mỗi category là 1 dict:
    name    : slug nội bộ, dùng làm giá trị field `category` trong Product
    keyword : từ khóa dùng để search trên Shopee
    url     : (optional) URL category/landing page nếu có, có thể để None
"""

from __future__ import annotations

from typing import TypedDict


class CategoryConfig(TypedDict):
    name: str
    keyword: str
    url: str | None


CATEGORIES: list[CategoryConfig] = [
    {"name": "dien_thoai", "keyword": "điện thoại", "url": None},
    {"name": "may_tinh_bang", "keyword": "máy tính bảng", "url": None},
    {"name": "laptop", "keyword": "laptop", "url": None},
    {"name": "pc", "keyword": "pc gaming", "url": None},
    {"name": "man_hinh", "keyword": "màn hình máy tính", "url": None},
    {"name": "ban_phim", "keyword": "bàn phím cơ", "url": None},
    {"name": "chuot", "keyword": "chuột gaming", "url": None},
    {"name": "tai_nghe", "keyword": "tai nghe", "url": None},
    {"name": "loa", "keyword": "loa bluetooth", "url": None},
    {"name": "webcam", "keyword": "webcam", "url": None},
    {"name": "micro", "keyword": "micro thu âm", "url": None},
    {"name": "camera", "keyword": "camera an ninh", "url": None},
    {"name": "thiet_bi_mang", "keyword": "thiết bị mạng", "url": None},
    {"name": "router", "keyword": "router wifi", "url": None},
    {"name": "switch", "keyword": "switch mạng", "url": None},
    {"name": "usb", "keyword": "usb", "url": None},
    {"name": "ssd", "keyword": "ổ cứng SSD", "url": None},
    {"name": "hdd", "keyword": "ổ cứng HDD", "url": None},
    {"name": "ram", "keyword": "ram máy tính", "url": None},
    {"name": "card_man_hinh", "keyword": "card màn hình", "url": None},
    {"name": "cpu", "keyword": "cpu máy tính", "url": None},
    {"name": "mainboard", "keyword": "mainboard", "url": None},
    {"name": "nguon_may_tinh", "keyword": "nguồn máy tính", "url": None},
    {"name": "case_may_tinh", "keyword": "case máy tính", "url": None},
    {"name": "phu_kien_may_tinh", "keyword": "phụ kiện máy tính", "url": None},
    {"name": "phu_kien_dien_thoai", "keyword": "phụ kiện điện thoại", "url": None},
    {"name": "sac", "keyword": "sạc nhanh", "url": None},
    {"name": "cap", "keyword": "cáp sạc", "url": None},
    {"name": "hub", "keyword": "hub chuyển đổi", "url": None},
    {"name": "dock", "keyword": "dock chuyển đổi", "url": None},
    {"name": "smartwatch", "keyword": "smartwatch", "url": None},
    {"name": "iot", "keyword": "thiết bị iot", "url": None},
    {"name": "nha_thong_minh", "keyword": "thiết bị nhà thông minh", "url": None},
    {"name": "gaming_gear", "keyword": "gaming gear", "url": None},
]


def get_category_by_name(name: str) -> CategoryConfig | None:
    """Tra cứu category config theo `name`. Trả về None nếu không tìm thấy."""
    for cat in CATEGORIES:
        if cat["name"] == name:
            return cat
    return None


def all_keywords() -> list[str]:
    """Trả về danh sách toàn bộ keyword để dùng cho search crawler."""
    return [cat["keyword"] for cat in CATEGORIES]
