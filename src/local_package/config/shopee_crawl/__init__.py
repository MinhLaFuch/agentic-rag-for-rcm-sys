# config/shopee_crawl/__init__.py
import os
from typing import List, Optional, Tuple, TypedDict

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs) -> bool:
        return False

from .._paths import PathConfig
from ..data import PROCESSED_DATA_DIR, RAW_DATA_DIR
from ..log import CRAWLER_LOG_DIR, CRAWLER_LOG_FILE, CRAWLER_LOG_LEVEL

_paths = PathConfig(__file__)
PROJECT_ROOT = _paths.repository_root
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


RAW_DIR = RAW_DATA_DIR
PROCESSED_DIR = PROCESSED_DATA_DIR
CHECKPOINT_DIR = _paths.checkpoint_dir
LOGS_DIR = CRAWLER_LOG_DIR
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.getenv("BASE_URL", "https://shopee.vn")
HEADLESS = _get_bool("HEADLESS", True)
WINDOW_WIDTH = _get_int("WINDOW_WIDTH", 1920)
WINDOW_HEIGHT = _get_int("WINDOW_HEIGHT", 1080)
PAGE_LOAD_TIMEOUT = _get_int("PAGE_LOAD_TIMEOUT", 30)
PRODUCT_TIMEOUT = _get_int("PRODUCT_TIMEOUT", 20)
IMPLICIT_WAIT = 0.0

MAX_PAGES_PER_KEYWORD = _get_int("MAX_PAGES_PER_KEYWORD", 20)
MAX_PRODUCTS = _get_int("MAX_PRODUCTS", 1000)
MAX_RETRIES = _get_int("MAX_RETRIES", 3)
MAX_SCROLLS_PER_PAGE = _get_int("MAX_SCROLLS_PER_PAGE", 15)
STOP_AFTER_NO_NEW_PRODUCTS = _get_int("STOP_AFTER_NO_NEW_PRODUCTS", 3)
MIN_DELAY = _get_float("MIN_DELAY", 1.5)
MAX_DELAY = _get_float("MAX_DELAY", 4.0)

SAVE_RAW_HTML = _get_bool("SAVE_RAW_HTML", False)
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "src/resource/data/processed")
PRODUCTS_JSONL_PATH = PROCESSED_DIR / "products.jsonl"
PRODUCTS_CSV_PATH = PROCESSED_DIR / "products.csv"
CRAWL_REPORT_PATH = PROCESSED_DIR / "crawl_report.json"
CHECKPOINT_DB_PATH = CHECKPOINT_DIR / "crawl_state.db"

LOG_FILE_PATH = CRAWLER_LOG_FILE
LOG_LEVEL = CRAWLER_LOG_LEVEL
CURRENCY = "VND"

CAPTCHA_MARKERS: Tuple[str, ...] = (
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
LOGIN_WALL_URL_MARKERS: Tuple[str, ...] = ("/buyer/login", "/verify/traveler")


class CategoryConfig(TypedDict):
    name: str
    keyword: str
    url: Optional[str]


CATEGORIES: List[CategoryConfig] = [
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


def get_category_by_name(name: str) -> Optional[CategoryConfig]:
    return next((category for category in CATEGORIES if category["name"] == name), None)


def all_keywords() -> List[str]:
    return [category["keyword"] for category in CATEGORIES]
