"""Retry decorator for transient crawler failures."""

import functools
import random
import time
from typing import Callable, Optional, Tuple, TypeVar

from local_package.config import shopee_crawl
from local_package.config.log import get_logger

logger = get_logger(__name__)
T = TypeVar("T")


def retry_on_exception(
	exceptions: Tuple[type, ...],
	max_retries: Optional[int] = None,
	base_delay: float = 1.0,
	max_delay: float = 10.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
	max_retries = shopee_crawl.MAX_RETRIES if max_retries is None else max_retries

	def decorator(func: Callable[..., T]) -> Callable[..., T]:
		@functools.wraps(func)
		def wrapper(*args, **kwargs) -> T:
			last_exc = None
			for attempt in range(1, max_retries + 1):
				try:
					return func(*args, **kwargs)
				except exceptions as exc:
					last_exc = exc
					if attempt >= max_retries:
						logger.error("%s failed after %d attempts: %s", func.__name__, attempt, exc)
						break
					delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
					delay += random.uniform(0, 0.5)
					logger.warning(
						"%s failed attempt %d/%d (%s), retrying in %.1fs",
						func.__name__, attempt, max_retries, exc, delay,
					)
					time.sleep(delay)
			if last_exc is None:
				raise RuntimeError("Retry wrapper completed without an exception")
			raise last_exc

		return wrapper

	return decorator
