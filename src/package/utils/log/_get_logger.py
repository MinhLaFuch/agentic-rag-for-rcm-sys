import logging
from pathlib import Path
from typing import Optional, Union
from ._setup_logging import setup_logging
from ._config import _LOG_FORMAT, _DATE_FORMAT, _configured_loggers

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
    if parent not in _configured_loggers:
        setup_logging(
            parent,
            level=level,
            to_file=log_file is not None or log_dir is not None,
            log_dir=log_dir,
            log_file=log_file,
            rotating=rotating,
        )
        _configured_loggers.add(parent)
    return logging.getLogger(name)