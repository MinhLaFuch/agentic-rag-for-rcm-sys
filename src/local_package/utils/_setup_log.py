import logging
from pathlib import Path
import sys
import datetime

def setup_logging(name: str = None, 
                  level: int = logging.INFO, 
                  to_file: bool = True, 
                  log_dir: Path = Path()) -> logging.Logger:
    """
    Set up a logger with consistent formatting across notebooks/scripts.

    Usage:
        from config.log import setup_logging
        logger = setup_logging(__name__)                       # logs to PROCESS_LOG_DIR
        logger = setup_logging(__name__, log_dir=AMAZON_PROCESS_LOG_DIR)  # logs to a specific subdir
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if to_file:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger