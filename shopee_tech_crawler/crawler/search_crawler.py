"""
crawler/search_crawler.py

SearchCrawler: crawl trang search theo keyword, thu thập dữ liệu RÚT GỌN
của từng sản phẩm (chỉ để DISCOVERY). Dữ liệu chi tiết đầy đủ được lấy
sau bởi ProductCrawler (Phase 5) khi mở product_url.

Luồng xử lý mỗi trang search:
    navigate (safe_get) → scroll để trigger lazy-load → wait_for_products
    → parse từng card → yield dict → rate_limiter.wait() → next page
"""

from __future__ import annotations

import datetime as dt
from typing import Iterator
from urllib.parse import quote

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.remote.webelement import WebElement

from config import settings
from crawler import selectors
from crawler.browser import BrowserManager, CaptchaDetectedError, LoginWallDetectedError
from crawler.rate_limiter import RateLimiter
from crawler.retry import retry_on_exception
from utils.hashing import build_product_id
from utils.logger import get_logger

logger = get_logger(__name__)

_TRANSIENT_EXCEPTIONS = (TimeoutException, StaleElementReferenceException, WebDriverException)


class SearchCrawler:
    """Discovery sản phẩm từ trang search Shopee theo keyword.

    Ví dụ:
        browser = BrowserManager()
        browser.start()
        crawler = SearchCrawler(browser)
        for item in crawler.search("laptop", max_pages=5):
            print(item["product_url"])
        browser.close()
    """

    def __init__(
        self,
        browser: BrowserManager,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.browser = browser
        self.rate_limiter = rate_limiter or RateLimiter()

    # ------------------------------------------------------------------
    def search(self, keyword: str, max_pages: int | None = None) -> Iterator[dict]:
        """Generator yield từng sản phẩm rút gọn tìm được cho `keyword`.

        Dừng khi: đạt `max_pages`, HOẶC 1 trang không có sản phẩm nào
        (đã hết kết quả). CaptchaDetectedError được log rồi raise lại
        để tầng gọi (script/CLI) quyết định dừng toàn bộ session —
        KHÔNG cố bypass, KHÔNG âm thầm nuốt lỗi.
        """
        max_pages = max_pages or settings.MAX_PAGES_PER_KEYWORD
        discovered_on_keyword = 0

        for page in range(max_pages):
            url = self._build_search_url(keyword, page)
            logger.info("SearchCrawler: keyword=%r page=%d url=%s", keyword, page, url)

            try:
                ok = self._navigate(url)
            except CaptchaDetectedError:
                logger.error(
                    "Dừng crawl keyword=%r tại page=%d do CAPTCHA_DETECTED", keyword, page
                )
                raise
            except LoginWallDetectedError:
                logger.error(
                    "Dừng crawl keyword=%r tại page=%d do LOGIN_WALL_DETECTED "
                    "(automation-detection) — KHÔNG tự động đăng nhập/bypass",
                    keyword,
                    page,
                )
                raise

            if not ok:
                logger.warning("Không load được page=%d cho keyword=%r, bỏ qua", page, keyword)
                continue

            self.browser.scroll_to_bottom()
            # Shopee có thể redirect sau driver.get, khi trang hydrate/scroll.
            self.browser.check_current_page_access(url)

            cards = self.browser.wait_for_products(
                by=selectors.SEARCH_PRODUCT_CARD_SELECTOR[0],
                value=selectors.SEARCH_PRODUCT_CARD_SELECTOR[1],
            )
            self.browser.check_current_page_access(url)

            if not cards:
                logger.info(
                    "Không còn sản phẩm ở page=%d cho keyword=%r — dừng phân trang",
                    page,
                    keyword,
                )
                break

            page_count = 0
            for card in cards:
                item = self._parse_card(card, keyword)
                if item is not None:
                    page_count += 1
                    discovered_on_keyword += 1
                    yield item

            logger.info(
                "keyword=%r page=%d: %d sản phẩm parse thành công", keyword, page, page_count
            )

            self.rate_limiter.wait()

        logger.info(
            "SearchCrawler hoàn tất keyword=%r: tổng %d sản phẩm discovered",
            keyword,
            discovered_on_keyword,
        )

    # ------------------------------------------------------------------
    def _build_search_url(self, keyword: str, page: int) -> str:
        base = settings.BASE_URL.rstrip("/")
        return f"{base}/search?keyword={quote(keyword)}&page={page}"

    @retry_on_exception(_TRANSIENT_EXCEPTIONS)
    def _navigate(self, url: str) -> bool:
        """safe_get bọc retry cho lỗi tạm thời (mạng chậm...).
        CaptchaDetectedError KHÔNG nằm trong _TRANSIENT_EXCEPTIONS nên
        không bị retry — nó phải được xử lý riêng ở tầng gọi.
        """
        return self.browser.safe_get(url)

    def _parse_card(self, card: WebElement, keyword: str) -> dict | None:
        """Parse 1 product card (`card` = thẻ `<li>` từ SEARCH_PRODUCT_CARD_SELECTOR).

        Nhiều `<li>` là skeleton đang loading (chưa có link/nội dung thật)
        — trả None để bỏ qua, không phải lỗi.

        Field lỗi/thiếu → None thay vì đoán mò (theo yêu cầu #22).
        Sản phẩm lỗi KHÔNG được làm crash toàn bộ crawler (#18).
        """
        try:
            link_el = card.find_element(*selectors.CARD_LINK_SELECTOR)
        except StaleElementReferenceException:
            logger.warning("Card bị stale, bỏ qua sản phẩm này")
            return None
        except Exception:  # noqa: BLE001 — skeleton card không có link, không phải lỗi
            return None

        try:
            product_url = link_el.get_attribute("href")
        except StaleElementReferenceException:
            logger.warning("Card bị stale khi lấy href, bỏ qua sản phẩm này")
            return None

        if not product_url:
            logger.warning("Card không có href hợp lệ, bỏ qua")
            return None

        product_id = build_product_id(product_url)

        item: dict = {
            "product_id": product_id,
            "product_url": product_url,
            "product_name": self._extract_name(card, link_el),
            "image_url": self._safe_attr(card, selectors.CARD_PRODUCT_IMAGE, "src"),
            "price_raw": self._safe_text(card, selectors.CARD_PRODUCT_PRICE),
            "sold_count_raw": self._safe_text(card, selectors.CARD_PRODUCT_SOLD_COUNT),
            "rating_raw": self._safe_text(card, selectors.CARD_PRODUCT_RATING),
            "shop_location_raw": self._extract_location(card),
            "search_keyword": keyword,
            "crawl_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        return item

    @staticmethod
    def _extract_name(card: WebElement, link_el: WebElement) -> str | None:
        """Ưu tiên aria-label="Product card: <tên>" của div[role=group] bọc
        ngoài (ổn định hơn đào div Tailwind lồng nhau); fallback sang
        aria-label="View product: <tên>" của chính link nếu group không có.
        """
        for source, prefix in (
            (card, "product card: "),
            (link_el, "view product: "),
        ):
            try:
                if source is card:
                    el = card.find_element(*selectors.CARD_GROUP_SELECTOR)
                    label = el.get_attribute("aria-label") or ""
                else:
                    label = source.get_attribute("aria-label") or ""
            except Exception:  # noqa: BLE001
                continue
            label_lower = label.lower()
            if label_lower.startswith(prefix):
                name = label[len(prefix):].strip()
                if name:
                    return name
        return None

    @staticmethod
    def _extract_location(card: WebElement) -> str | None:
        """aria-label="location-<Tên tỉnh/thành>" -> trả về phần sau dấu '-'."""
        try:
            el = card.find_element(*selectors.CARD_SHOP_LOCATION)
            label = el.get_attribute("aria-label") or ""
        except Exception:  # noqa: BLE001
            return None
        prefix = "location-"
        if label.lower().startswith(prefix):
            value = label[len(prefix):].strip()
            return value or None
        return None

    @staticmethod
    def _safe_text(card: WebElement, selector: tuple[str, str]) -> str | None:
        try:
            el = card.find_element(*selector)
            text = el.text.strip()
            return text or None
        except Exception:  # noqa: BLE001 — 1 field lỗi không được crash crawler
            return None

    @staticmethod
    def _safe_attr(card: WebElement, selector: tuple[str, str], attr: str) -> str | None:
        try:
            el = card.find_element(*selector)
            value = el.get_attribute(attr)
            return value or None
        except Exception:  # noqa: BLE001
            return None
