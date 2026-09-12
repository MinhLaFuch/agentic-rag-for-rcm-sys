import logging
import os

from .._paths import PathConfig
from ...utils import get_logger as _get_logger
from ...utils import setup_logging

_paths = PathConfig(__file__)

LOG_ROOT = _paths.log_dir
CRAWLER_LOG_DIR = _paths.crawler_log_dir
CRAWLER_LOG_FILE = CRAWLER_LOG_DIR / "crawler.log"
CRAWLER_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

AMAZON_PROCESS_LOG_DIR = _paths.log("amazon")
STEAM_PROCESS_LOG_DIR = _paths.log("steam")
MOVIELENS_PROCESS_LOG_DIR = _paths.log("ml")


def get_logger(name: str) -> logging.Logger:
    level = getattr(logging, CRAWLER_LOG_LEVEL.upper(), logging.INFO)
    return _get_logger(
        name,
        parent="local_package.crawler",
        log_file=CRAWLER_LOG_FILE,
        level=level,
        rotating=True,
    )


__all__ = [
    "setup_logging",
    "get_logger",
    "LOG_ROOT",
    "CRAWLER_LOG_DIR",
    "CRAWLER_LOG_FILE",
    "CRAWLER_LOG_LEVEL",
    "AMAZON_PROCESS_LOG_DIR",
    "STEAM_PROCESS_LOG_DIR",
    "MOVIELENS_PROCESS_LOG_DIR",
]
