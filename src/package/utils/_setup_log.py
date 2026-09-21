import logging
import datetime
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Set, Union

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured_loggers: Set[str] = set()


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

        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
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
        if parent_name not in _configured_loggers:
            self.setup()
            _configured_loggers.add(parent_name)
        return logging.getLogger(name)

    def crawl_summary(
        self,
        *,
        keywords: list,
        pages: int,
        discovered: int,
        crawled: int,
        success: int,
        failed: int,
        duplicate: int,
        elapsed_seconds: float,
    ) -> None:
        logger = self.logger
        logger.info("========== CRAWL SUMMARY ==========")
        logger.info("Keywords: %s", ", ".join(keywords))
        logger.info("Pages: %s", pages)
        logger.info("Products discovered: %s", discovered)
        logger.info("Products crawled: %s", crawled)
        logger.info("Success: %s", success)
        logger.info("Failed: %s", failed)
        logger.info("Duplicate: %s", duplicate)
        logger.info("Elapsed time: %.1fs", elapsed_seconds)
        logger.info("====================================")


def setup_logging(
    name: Optional[str] = None,
    level: int = logging.INFO,
    to_file: bool = True,
    log_dir: Optional[Path] = None,
    log_file: Optional[Union[str, Path]] = None,
    rotating: bool = False,
) -> logging.Logger:
    """Backward-compatible wrapper around :class:`LogHelper`."""
    return LogHelper(
        name,
        level=level,
        to_file=to_file,
        log_dir=log_dir,
        log_file=log_file,
        rotating=rotating,
    ).logger


def get_logger(
    name: str,
    *,
    parent: str = "local_package.crawler",
    log_dir: Optional[Path] = None,
    log_file: Optional[Union[str, Path]] = None,
    level: int = logging.INFO,
    rotating: bool = True,
) -> logging.Logger:
    """Return a child logger under a once-configured parent."""
    return LogHelper(
        parent,
        level=level,
        to_file=log_file is not None or log_dir is not None,
        log_dir=log_dir,
        log_file=log_file,
        rotating=rotating,
    ).child(name, parent=parent)


def log_crawl_summary(
    logger: logging.Logger,
    *,
    keywords: list,
    pages: int,
    discovered: int,
    crawled: int,
    success: int,
    failed: int,
    duplicate: int,
    elapsed_seconds: float,
) -> None:
    """Backward-compatible wrapper around :meth:`LogHelper.crawl_summary`."""
    helper = LogHelper(logger.name, to_file=False)
    helper.crawl_summary(
        keywords=keywords,
        pages=pages,
        discovered=discovered,
        crawled=crawled,
        success=success,
        failed=failed,
        duplicate=duplicate,
        elapsed_seconds=elapsed_seconds,
    )


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
