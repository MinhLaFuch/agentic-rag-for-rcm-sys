"""
utils/logger.py

Logger dùng chung cho toàn bộ crawler.
Ghi ra file `data/logs/crawler.log` VÀ console, format nhất quán.

Sử dụng:
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("...")
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    """Cấu hình root logger một lần duy nhất (idempotent)."""
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger("shopee_tech_crawler")
    root.setLevel(level)
    root.propagate = False

    # Tránh add handler trùng lặp nếu module bị import lại (reload).
    if root.handlers:
        _configured = True
        return

    # File handler — xoay vòng khi quá 10MB, giữ tối đa 5 file cũ.
    file_handler = RotatingFileHandler(
        settings.LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console handler.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Trả về logger con của `shopee_tech_crawler`, đã cấu hình sẵn handler."""
    _configure_root()
    return logging.getLogger(f"shopee_tech_crawler.{name}")


def log_crawl_summary(
    logger: logging.Logger,
    *,
    keywords: list[str],
    pages: int,
    discovered: int,
    crawled: int,
    success: int,
    failed: int,
    duplicate: int,
    elapsed_seconds: float,
) -> None:
    """In summary block chuẩn hóa cuối mỗi phiên crawl."""
    logger.info("========== CRAWL SUMMARY ==========")
    logger.info("Keywords: %s", ", ".join(keywords))
    logger.info("Pages: %s", pages)
    logger.info("Products discovered: %s", discovered)
    logger.info("Products crawled: %s", crawled)
    logger.info("Success: %s", success)
    logger.info("Failed: %s", failed)
    logger.info("Duplicate: %s", duplicate)
    logger.info("Elapsed time: %.1fs", elapsed_seconds)
    logger.info("====================================")
