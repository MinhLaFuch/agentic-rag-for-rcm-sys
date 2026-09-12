"""
crawler/retry.py

Decorator retry dùng chung cho các thao tác dễ fail tạm thời (network
chậm, element chưa kịp render...). KHÔNG retry vô hạn — luôn giới hạn
bởi settings.MAX_RETRIES.
"""

from __future__ import annotations

import functools
import random
import time
from typing import Callable, TypeVar

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_on_exception(
    exceptions: tuple[type[BaseException], ...],
    max_retries: int | None = None,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry hàm khi gặp một trong `exceptions`, exponential backoff + jitter.

    Sau khi hết `max_retries` lần thử, exception cuối cùng được raise lại
    (không nuốt lỗi âm thầm) để tầng gọi (vd ProductCrawler) tự quyết định
    đánh dấu sản phẩm là failed.

    Ví dụ:
        @retry_on_exception((TimeoutException, StaleElementReferenceException))
        def load_product(url): ...
    """
    max_retries = settings.MAX_RETRIES if max_retries is None else max_retries

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        logger.error(
                            "%s thất bại sau %d lần thử: %s",
                            func.__name__,
                            attempt,
                            exc,
                        )
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay += random.uniform(0, 0.5)
                    logger.warning(
                        "%s lỗi lần %d/%d (%s), retry sau %.1fs",
                        func.__name__,
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
