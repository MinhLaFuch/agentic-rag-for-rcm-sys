"""
config/settings.py

Tất cả cấu hình quan trọng của crawler nằm ở đây.
Không hard-code các thông số này trực tiếp trong crawler/pipeline.

Giá trị mặc định có thể bị override bởi biến môi trường (.env).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Nạp file .env nếu tồn tại (không bắt buộc, không raise nếu thiếu)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    try:
        return float(val) if val is not None else default
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


# --------------------------------------------------------------------------
# Đường dẫn dự án
# --------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
CHECKPOINT_DIR: Path = DATA_DIR / "checkpoint"
LOGS_DIR: Path = DATA_DIR / "logs"

for _d in (RAW_DIR, PROCESSED_DIR, CHECKPOINT_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Base URL
# --------------------------------------------------------------------------
BASE_URL: str = os.getenv("BASE_URL", "https://shopee.vn")

# --------------------------------------------------------------------------
# Browser
# --------------------------------------------------------------------------
HEADLESS: bool = _get_bool("HEADLESS", True)
WINDOW_WIDTH: int = _get_int("WINDOW_WIDTH", 1920)
WINDOW_HEIGHT: int = _get_int("WINDOW_HEIGHT", 1080)
PAGE_LOAD_TIMEOUT: int = _get_int("PAGE_LOAD_TIMEOUT", 30)
PRODUCT_TIMEOUT: int = _get_int("PRODUCT_TIMEOUT", 20)
IMPLICIT_WAIT: float = 0.0  # ưu tiên explicit wait (WebDriverWait)

# --------------------------------------------------------------------------
# Crawl limits
# --------------------------------------------------------------------------
MAX_PAGES_PER_KEYWORD: int = _get_int("MAX_PAGES_PER_KEYWORD", 20)
MAX_PRODUCTS: int = _get_int("MAX_PRODUCTS", 1000)
MAX_RETRIES: int = _get_int("MAX_RETRIES", 3)

# Scroll control (lazy-loading)
MAX_SCROLLS_PER_PAGE: int = _get_int("MAX_SCROLLS_PER_PAGE", 15)
STOP_AFTER_NO_NEW_PRODUCTS: int = _get_int("STOP_AFTER_NO_NEW_PRODUCTS", 3)

# --------------------------------------------------------------------------
# Rate limiting (human-like delay, giây)
# --------------------------------------------------------------------------
MIN_DELAY: float = _get_float("MIN_DELAY", 1.5)
MAX_DELAY: float = _get_float("MAX_DELAY", 4.0)

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
SAVE_RAW_HTML: bool = _get_bool("SAVE_RAW_HTML", False)
OUTPUT_DIR: Path = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "data/processed")

PRODUCTS_JSONL_PATH: Path = PROCESSED_DIR / "products.jsonl"
PRODUCTS_CSV_PATH: Path = PROCESSED_DIR / "products.csv"
CRAWL_REPORT_PATH: Path = PROCESSED_DIR / "crawl_report.json"
CHECKPOINT_DB_PATH: Path = CHECKPOINT_DIR / "crawl_state.db"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_FILE_PATH: Path = LOGS_DIR / "crawler.log"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --------------------------------------------------------------------------
# Currency
# --------------------------------------------------------------------------
CURRENCY: str = "VND"

# --------------------------------------------------------------------------
# Anti-bot policy (chỉ để log & dừng graceful, KHÔNG bypass)
# --------------------------------------------------------------------------
# QUAN TRỌNG: dùng cụm nhiều từ, KHÔNG dùng từ đơn (vd "verify") — trang
# Shopee bình thường (trang chủ, form đăng ký/OTP, footer...) hoàn toàn có
# thể chứa các từ đơn lẻ đó mà không hề liên quan tới CAPTCHA thật.
# Nếu gặp false-positive/false-negative mới, hãy cung cấp title + đoạn HTML
# thực tế của trang chặn để tinh chỉnh danh sách này (không tự đoán).
CAPTCHA_MARKERS: tuple[str, ...] = (
    "verify you are human",
    "verify that you are human",
    "unusual traffic from your computer",
    "unusual traffic from your network",
    "checking your browser before accessing",
    "xác minh bạn không phải là người máy",
    "xác minh bạn không phải là robot",
    "hãy xác minh bạn là người",
    "please complete the security check",
    "access to this page has been denied",
    "captcha-container",
    "captcha",
)

# Route URL công khai của Shopee dùng để redirect người dùng chưa đăng
# nhập — công khai, ổn định (khác với text "Đăng Nhập" xuất hiện bình
# thường ở mọi trang nên KHÔNG dùng được làm marker).
LOGIN_WALL_URL_MARKERS: tuple[str, ...] = (
    "/buyer/login",
    "/verify/traveler",
)

