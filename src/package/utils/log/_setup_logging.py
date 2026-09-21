import logging
import datetime
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Set, Union

def setup_logging(
    name: Optional[str] = None,
    level: int = logging.INFO,
    to_file: bool = True,
    log_dir: Optional[Path] = None,
    log_file: Optional[Union[str, Path]] = None,
    rotating: bool = False,
) -> logging.Logger:
    """
    Set up a logger with consistent formatting across notebooks/scripts.

    Usage:
        from local_package.config.log import setup_logging
        logger = setup_logging(__name__, log_dir=AMAZON_PROCESS_LOG_DIR)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    if to_file:
        file_handler = _build_file_handler(
            log_dir=log_dir,
            log_file=log_file,
            rotating=rotating,
            formatter=formatter,
            level=level,
        )
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger





def _build_file_handler(
    *,
    log_dir: Optional[Path],
    log_file: Optional[Union[str, Path]],
    rotating: bool,
    formatter: logging.Formatter,
    level: int,
) -> logging.Handler:
    if log_file is not None:
        path = Path(log_file)
    elif log_dir is not None:
        path = Path(log_dir) / f"{datetime.datetime.now():%Y%m%d}.log"
    else:
        raise ValueError("log_dir or log_file is required when to_file=True")

    path.parent.mkdir(parents=True, exist_ok=True)
    if rotating:
        handler: logging.Handler = RotatingFileHandler(
            path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    else:
        handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler
