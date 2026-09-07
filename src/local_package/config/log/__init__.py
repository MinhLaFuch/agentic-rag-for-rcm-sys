import logging
import sys
from pathlib import Path
from datetime import datetime

from .._find_root import find_repo_root

_REPO_ROOT = find_repo_root(__file__)
_LOG_ROOT = _REPO_ROOT / "src" / "log"

# Data log directory
DATA_LOG_DIR = _LOG_ROOT / "data"


PROCESS_LOG_DIR = DATA_LOG_DIR / "process"

AMAZON_PROCESS_LOG_DIR = PROCESS_LOG_DIR / "amazon"
STEAM_PROCESS_LOG_DIR = PROCESS_LOG_DIR / "steam"
MOVIELENS_PROCESS_LOG_DIR = PROCESS_LOG_DIR / "ml"