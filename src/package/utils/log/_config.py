"""Where Amazon process logs get written, and how they're formatted."""
from ..path import dataset_log_dir, log_root

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_ROOT = log_root(__file__)
PROCESS_LOG_DIR = dataset_log_dir("amazon", __file__)