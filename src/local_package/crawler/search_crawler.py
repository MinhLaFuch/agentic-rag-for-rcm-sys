"""Search-result discovery crawler for Shopee technology products."""

import datetime as dt
from typing import Iterator, Optional
from urllib.parse import quote

from selenium.common.exceptions import (
	StaleElementReferenceException,
	TimeoutException,
	WebDriverException,
)
from selenium.webdriver.remote.webelement import WebElement

from local_package.config import shopee_crawl
from local_package.config.log import get_logger

from . import selectors
from .browser import BrowserManager, CaptchaDetectedError, LoginWallDetectedError
from .product_id import build_product_id
from .rate_limiter import RateLimiter
from .retry import retry_on_exception

logger = get_logger(__name__)
_TRANSIENT_EXCEPTIONS = (TimeoutException, StaleElementReferenceException, WebDriverException)


class SearchCrawler:
	def __init__(self, browser: BrowserManager, rate_limiter: Optional[RateLimiter] = None) -> None:
		self.browser = browser
		self.rate_limiter = rate_limiter or RateLimiter()

	def search(self, keyword: str, max_pages: Optional[int] = None) -> Iterator[dict]:
		max_pages = max_pages or shopee_crawl.MAX_PAGES_PER_KEYWORD
		discovered = 0
		for page in range(max_pages):
			url = self._build_search_url(keyword, page)
			try:
				loaded = self._navigate(url)
			except (CaptchaDetectedError, LoginWallDetectedError):
				logger.error("Stopping keyword=%r at page=%d due to blocked access", keyword, page)
				raise
			if not loaded:
				continue
			self.browser.scroll_to_bottom()
			self.browser.check_current_page_access(url)
			cards = self.browser.wait_for_products(
				by=selectors.SEARCH_PRODUCT_CARD_SELECTOR[0],
				value=selectors.SEARCH_PRODUCT_CARD_SELECTOR[1],
			)
			if not cards:
				break
			for card in cards:
				item = self._parse_card(card, keyword)
				if item is not None:
					discovered += 1
					yield item
			self.rate_limiter.wait()
		logger.info("Search complete keyword=%r: %d products", keyword, discovered)

	def _build_search_url(self, keyword: str, page: int) -> str:
		return "%s/search?keyword=%s&page=%d" % (
			shopee_crawl.BASE_URL.rstrip("/"), quote(keyword), page
		)

	@retry_on_exception(_TRANSIENT_EXCEPTIONS)
	def _navigate(self, url: str) -> bool:
		return self.browser.safe_get(url)

	def _parse_card(self, card: WebElement, keyword: str) -> Optional[dict]:
		try:
			link = card.find_element(*selectors.CARD_LINK_SELECTOR)
			product_url = link.get_attribute("href")
		except Exception:
			return None
		if not product_url:
			return None
		return {
			"product_id": build_product_id(product_url),
			"product_url": product_url,
			"product_name": self._extract_name(card, link),
			"image_url": self._safe_attr(card, selectors.CARD_PRODUCT_IMAGE, "src"),
			"price_raw": self._safe_text(card, selectors.CARD_PRODUCT_PRICE),
			"sold_count_raw": self._safe_text(card, selectors.CARD_PRODUCT_SOLD_COUNT),
			"rating_raw": self._safe_text(card, selectors.CARD_PRODUCT_RATING),
			"shop_location_raw": self._extract_location(card),
			"search_keyword": keyword,
			"crawl_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
		}

	@staticmethod
	def _extract_name(card: WebElement, link: WebElement) -> Optional[str]:
		for source, prefix in ((card, "product card: "), (link, "view product: ")):
			try:
				label = (
					source.find_element(*selectors.CARD_GROUP_SELECTOR).get_attribute("aria-label")
					if source is card
					else source.get_attribute("aria-label")
				) or ""
			except Exception:
				continue
			if label.lower().startswith(prefix):
				return label[len(prefix):].strip() or None
		return None

	@staticmethod
	def _extract_location(card: WebElement) -> Optional[str]:
		try:
			label = card.find_element(*selectors.CARD_SHOP_LOCATION).get_attribute("aria-label") or ""
		except Exception:
			return None
		return label[len("location-"):].strip() or None if label.lower().startswith("location-") else None

	@staticmethod
	def _safe_text(card: WebElement, selector) -> Optional[str]:
		try:
			return card.find_element(*selector).text.strip() or None
		except Exception:
			return None

	@staticmethod
	def _safe_attr(card: WebElement, selector, attr: str) -> Optional[str]:
		try:
			return card.find_element(*selector).get_attribute(attr) or None
		except Exception:
			return None
