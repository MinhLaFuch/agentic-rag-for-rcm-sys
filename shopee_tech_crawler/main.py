"""
main.py

Entry point của Shopee Tech Crawler.

⚠️ PHASE 1: đây mới là stub để xác nhận project skeleton import được
đúng cách (config load OK, thư mục data/ được tạo tự động, v.v.).
CLI đầy đủ (--keyword, --category, --max-pages, --resume, --export, ...)
sẽ được xây dựng ở PHASE 11 theo đúng workflow đã thống nhất.
"""

from __future__ import annotations

from config import settings
from config.categories import CATEGORIES, all_keywords


def main() -> None:
    print("Shopee Tech Crawler — Phase 1 skeleton check")
    print(f"PROJECT_ROOT       : {settings.PROJECT_ROOT}")
    print(f"BASE_URL            : {settings.BASE_URL}")
    print(f"HEADLESS            : {settings.HEADLESS}")
    print(f"MAX_PAGES_PER_KEYWORD: {settings.MAX_PAGES_PER_KEYWORD}")
    print(f"MIN_DELAY / MAX_DELAY: {settings.MIN_DELAY} / {settings.MAX_DELAY}")
    print(f"Số category đã cấu hình: {len(CATEGORIES)}")
    print(f"5 keyword đầu tiên: {all_keywords()[:5]}")
    print(f"PRODUCTS_JSONL_PATH : {settings.PRODUCTS_JSONL_PATH}")
    print(f"CHECKPOINT_DB_PATH  : {settings.CHECKPOINT_DB_PATH}")
    print("\n✅ Skeleton OK — sẵn sàng cho PHASE 2 trở đi.")


if __name__ == "__main__":
    main()
