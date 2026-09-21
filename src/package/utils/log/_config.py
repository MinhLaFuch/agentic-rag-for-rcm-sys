from collections.abc import Set

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONFIGURED_LOGGER: Set[str] = set()