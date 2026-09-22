from __future__ import annotations

import datetime
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ._config import DATE_FORMAT, LOG_FORMAT


def setup_logging(
    name: str = "process",
    *,
    level: int = logging.INFO,
    to_file: bool = True,
    log_dir: str | Path | None = None,
    log_file: str | Path | None = None,
    rotating: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level)
    logger.addHandler(console)

    if to_file:
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
        logger.addHandler(handler)

    logger.propagate = False
    return logger
