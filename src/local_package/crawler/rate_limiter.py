"""Rate limiting for crawler requests and page navigation."""

import random
import time
from typing import Optional

from local_package.config import shopee_crawl
from local_package.config.log import get_logger

logger = get_logger(__name__)


class RateLimiter:
	"""Sleep for a random delay in the configured range."""

	def __init__(
		self,
		min_delay: Optional[float] = None,
		max_delay: Optional[float] = None,
	) -> None:
		self.min_delay = shopee_crawl.MIN_DELAY if min_delay is None else min_delay
		self.max_delay = shopee_crawl.MAX_DELAY if max_delay is None else max_delay
		if self.min_delay < 0 or self.max_delay < self.min_delay:
			raise ValueError(
				"Invalid delay range: min=%s, max=%s"
				% (self.min_delay, self.max_delay)
			)

	def wait(self) -> float:
		delay = random.uniform(self.min_delay, self.max_delay)
		logger.debug("RateLimiter: sleep %.2fs", delay)
		time.sleep(delay)
		return delay
