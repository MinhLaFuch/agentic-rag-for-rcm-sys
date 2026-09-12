from .._paths import PathConfig
from ...utils import setup_logging

_paths = PathConfig(__file__)

LOG_ROOT = _paths.log_dir

AMAZON_PROCESS_LOG_DIR = _paths.log("amazon")
STEAM_PROCESS_LOG_DIR = _paths.log("steam")
MOVIELENS_PROCESS_LOG_DIR = _paths.log("ml")

__all__ = [
	"setup_logging",
	"LOG_ROOT",
	"AMAZON_PROCESS_LOG_DIR",
	"STEAM_PROCESS_LOG_DIR",
	"MOVIELENS_PROCESS_LOG_DIR",
]