from .._paths import PathConfig

_paths = PathConfig(__file__)

LOG_ROOT = _paths.log_dir

AMAZON_PROCESS_LOG_DIR = _paths.log("amazon")
STEAM_PROCESS_LOG_DIR = _paths.log("steam")
MOVIELENS_PROCESS_LOG_DIR = _paths.log("ml")