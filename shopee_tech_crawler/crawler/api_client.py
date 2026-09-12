"""
crawler/api_client.py

ShopeeApiClient: gọi trực tiếp API JSON công khai mà chính trang Shopee
dùng để tải dữ liệu search (quan sát được qua Chrome DevTools > Network
> Fetch/XHR khi bạn tự duyệt trang bằng tay). Đây là hướng thay thế cho
SearchCrawler (Selenium) sau khi phát hiện Shopee chặn Chrome tự động
hoá bằng login-wall (xem crawler/browser.py: LoginWallDetectedError).

⚠️ CHƯA ĐƯỢC XÁC NHẬN BẰNG REQUEST THẬT (sandbox không truy cập được
shopee.vn để tự test). URL/query param dưới đây dựa trên cấu trúc API
phổ biến, công khai của Shopee — không phải bí mật/thuật toán ký request
nội bộ. Nếu scripts/try_api_search.py trả lỗi hoặc 0 kết quả, hãy lấy
request CHÍNH XÁC theo hướng dẫn trong docstring của script đó và gửi
lại — không tự đoán thêm.

Nguyên tắc giữ nguyên như SearchCrawler:
- Rate limit + retry giống hệt (dùng chung RateLimiter/retry_on_exception).
- Không giả mạo token bảo mật, không reverse-engineer thuật toán ký
  request riêng của Shopee — chỉ dùng header y hệt trình duyệt thường
  gửi (User-Agent, Referer, Accept-Language).
- Nếu API trả 403/lỗi liên tục → log rõ ràng và dừng, không cố "vượt".
"""

from __future__ import annotations

from typing import Any

import requests

from config import settings
from crawler.rate_limiter import RateLimiter
from crawler.retry import retry_on_exception
from utils.logger import get_logger

logger = get_logger(__name__)

SEARCH_API_PATH = "/api/v4/search/search_items"

# Header y hệt những gì trình duyệt thường gửi khi tự duyệt trang — không
# phải token bí mật, quan sát được qua DevTools bởi bất kỳ ai.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
    # Header Shopee frontend tự gắn khi gọi API này từ web desktop —
    # quan sát công khai qua Network tab, KHÔNG phải giá trị bí mật.
    "X-API-SOURCE": "pc",
}

_TRANSIENT_EXCEPTIONS = (requests.ConnectionError, requests.Timeout)


class ShopeeApiClient:
    """Client gọi API search JSON công khai của Shopee bằng requests.Session.

    Ví dụ:
        client = ShopeeApiClient()
        data = client.search("laptop", page=0)
        if data:
            for item in data.get("items", []):
                ...
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.timeout = timeout
        self._warmed_up = False

    def warm_up(self) -> None:
        """Ghé trang chủ 1 lần để nhận cookie session hợp lệ trước khi gọi
        API — nhiều API kiểu SPA yêu cầu cookie đã được set từ 1 lần load
        trang HTML thật trước đó, không nhận request "từ hư không".
        """
        try:
            resp = self.session.get(
                settings.BASE_URL,
                headers={"Referer": settings.BASE_URL},
                timeout=self.timeout,
            )
            logger.info(
                "warm_up: GET %s -> status=%d, cookies nhận được=%s",
                settings.BASE_URL,
                resp.status_code,
                list(self.session.cookies.keys()),
            )
        except requests.RequestException as exc:
            logger.warning("warm_up thất bại (thử gọi API trực tiếp): %s", exc)
        finally:
            self._warmed_up = True

    @retry_on_exception(_TRANSIENT_EXCEPTIONS)
    def search(self, keyword: str, page: int = 0, limit: int = 60) -> dict[str, Any] | None:
        """Gọi API search cho `keyword` tại `page` (0-indexed).

        Trả về JSON đã parse, hoặc None nếu lỗi/không phải JSON hợp lệ
        (log chi tiết status code + body để chẩn đoán, không raise để
        1 page lỗi không crash toàn bộ vòng lặp phía trên).
        """
        if not self._warmed_up:
            self.warm_up()

        params = {
            "keyword": keyword,
            "limit": limit,
            "newest": page * limit,
            "order": "desc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }
        headers = {"Referer": f"{settings.BASE_URL}/search?keyword={keyword}"}
        url = f"{settings.BASE_URL}{SEARCH_API_PATH}"

        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        logger.info(
            "search API: keyword=%r page=%d status=%d content-type=%s",
            keyword,
            page,
            resp.status_code,
            resp.headers.get("content-type"),
        )
        self.rate_limiter.wait()

        if resp.status_code != 200:
            logger.warning(
                "search API trả status=%d cho keyword=%r page=%d, body[:300]=%r",
                resp.status_code,
                keyword,
                page,
                resp.text[:300],
            )
            return None

        try:
            return resp.json()
        except ValueError:
            logger.warning(
                "search API không trả JSON hợp lệ cho keyword=%r page=%d, body[:300]=%r",
                keyword,
                page,
                resp.text[:300],
            )
            return None

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "ShopeeApiClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
