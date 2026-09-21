import logging
import datetime
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Set, Union
from ._config import LOG_FORMAT, DATE_FORMAT, CONFIGURED_LOGGER

class LogHelper:
    """Configure application loggers and expose common structured log messages."""

    def __init__(
        self,
        name: Optional[str] = None,
        *,
        level: int = logging.INFO,
        to_file: bool = True,
        log_dir: Optional[Path] = None,
        log_file: Optional[Union[str, Path]] = None,
        rotating: bool = False,
    ) -> None:
        self.name = name
        self.level = level
        self.to_file = to_file
        self.log_dir = log_dir
        self.log_file = log_file
        self.rotating = rotating

    @property
    def logger(self) -> logging.Logger:
        return self.setup()

    def setup(self) -> logging.Logger:
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        if logger.handlers:
            return logger

        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.level)
        logger.addHandler(console_handler)

        if self.to_file:
            logger.addHandler(
                _build_file_handler(
                    log_dir=self.log_dir,
                    log_file=self.log_file,
                    rotating=self.rotating,
                    formatter=formatter,
                    level=self.level,
                )
            )

        logger.propagate = False
        return logger

    def child(
        self,
        name: str,
        *,
        parent: Optional[str] = None,
    ) -> logging.Logger:
        parent_name = parent or self.name
        if parent_name is None:
            return logging.getLogger(name)
        if parent_name not in CONFIGURED_LOGGER:
            self.setup()
            CONFIGURED_LOGGER.add(parent_name)
        return logging.getLogger(name)


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
