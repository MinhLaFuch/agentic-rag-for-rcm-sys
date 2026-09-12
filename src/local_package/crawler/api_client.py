"""HTTP client for Shopee's public search endpoint."""

from typing import Any, Dict, Optional

import requests

from local_package.config import shopee_crawl
from local_package.config.log import get_logger

from .rate_limiter import RateLimiter
from .retry import retry_on_exception

logger = get_logger(__name__)
SEARCH_API_PATH = "/api/v4/search/search_items"
DEFAULT_HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
	),
	"Accept": "application/json",
	"Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
	"X-Requested-With": "XMLHttpRequest",
	"X-API-SOURCE": "pc",
}
_TRANSIENT_EXCEPTIONS = (requests.ConnectionError, requests.Timeout)


class ShopeeApiClient:
	"""Call Shopee search JSON through a reusable requests session."""

	def __init__(
		self,
		rate_limiter: Optional[RateLimiter] = None,
		timeout: float = 15.0,
	) -> None:
		self.session = requests.Session()
		self.session.headers.update(DEFAULT_HEADERS)
		self.rate_limiter = rate_limiter or RateLimiter()
		self.timeout = timeout
		self._warmed_up = False

	def warm_up(self) -> None:
		try:
			response = self.session.get(
				shopee_crawl.BASE_URL,
				headers={"Referer": shopee_crawl.BASE_URL},
				timeout=self.timeout,
			)
			logger.info(
				"warm_up: GET %s -> status=%d, cookies=%s",
				shopee_crawl.BASE_URL,
				response.status_code,
				list(self.session.cookies.keys()),
			)
		except requests.RequestException as exc:
			logger.warning("warm_up failed (trying direct API): %s", exc)
		finally:
			self._warmed_up = True

	@retry_on_exception(_TRANSIENT_EXCEPTIONS)
	def search(self, keyword: str, page: int = 0, limit: int = 60) -> Optional[Dict[str, Any]]:
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
		headers = {"Referer": "%s/search?keyword=%s" % (shopee_crawl.BASE_URL, keyword)}
		response = self.session.get(
			"%s%s" % (shopee_crawl.BASE_URL, SEARCH_API_PATH),
			params=params,
			headers=headers,
			timeout=self.timeout,
		)
		logger.info(
			"search API: keyword=%r page=%d status=%d content-type=%s",
			keyword, page, response.status_code, response.headers.get("content-type"),
		)
		self.rate_limiter.wait()
		if response.status_code != 200:
			logger.warning(
				"search API status=%d keyword=%r page=%d body[:300]=%r",
				response.status_code, keyword, page, response.text[:300],
			)
			return None
		try:
			return response.json()
		except ValueError:
			logger.warning(
				"search API did not return JSON keyword=%r page=%d body[:300]=%r",
				keyword, page, response.text[:300],
			)
			return None

	def close(self) -> None:
		self.session.close()

	def __enter__(self) -> "ShopeeApiClient":
		return self

	def __exit__(self, *exc_info: object) -> None:
		self.close()
