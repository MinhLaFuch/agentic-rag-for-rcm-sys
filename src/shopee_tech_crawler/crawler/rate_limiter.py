"""
crawler/rate_limiter.py

RateLimiter: chèn delay ngẫu nhiên giữa các lần request/navigation để
không tạo tải bất thường lên Shopee. KHÔNG dùng để né tránh phát hiện
bot — chỉ đơn thuần giới hạn tốc độ crawl ở mức hợp lý.
"""

from __future__ import annotations

import random
import time

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Sleep ngẫu nhiên trong khoảng [min_delay, max_delay] giây.

    Ví dụ:
        limiter = RateLimiter()
        for url in urls:
            driver.get(url)
            limiter.wait()
    """

    def __init__(self, min_delay: float | None = None, max_delay: float | None = None) -> None:
        self.min_delay = settings.MIN_DELAY if min_delay is None else min_delay
        self.max_delay = settings.MAX_DELAY if max_delay is None else max_delay
        if self.min_delay < 0 or self.max_delay < self.min_delay:
            raise ValueError(
                f"Khoảng delay không hợp lệ: min={self.min_delay}, max={self.max_delay}"
            )

    def wait(self) -> float:
        """Sleep một khoảng ngẫu nhiên, trả về số giây đã sleep (để log/test)."""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug("RateLimiter: sleep %.2fs", delay)
        time.sleep(delay)
        return delay
