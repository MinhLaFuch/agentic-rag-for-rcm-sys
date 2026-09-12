"""Selenium browser lifecycle and access checks for the crawler."""

import datetime as dt
import time
from types import TracebackType
from typing import List, Optional, Tuple, Type

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from local_package.config import shopee_crawl
from local_package.config.log import get_logger

logger = get_logger(__name__)


class CaptchaDetectedError(Exception):
    """The current page shows a CAPTCHA or access-denied state."""


class LoginWallDetectedError(Exception):
    """The requested page redirected to a login wall."""


class BrowserSessionClosedError(Exception):
    """The browser window or WebDriver session was closed."""


class BrowserManager:
    def __init__(
        self,
        headless: Optional[bool] = None,
        window_width: Optional[int] = None,
        window_height: Optional[int] = None,
        page_load_timeout: Optional[int] = None,
    ) -> None:
        self.headless = shopee_crawl.HEADLESS if headless is None else headless
        self.window_width = window_width or shopee_crawl.WINDOW_WIDTH
        self.window_height = window_height or shopee_crawl.WINDOW_HEIGHT
        self.page_load_timeout = page_load_timeout or shopee_crawl.PAGE_LOAD_TIMEOUT
        self.driver: Optional[WebDriver] = None

    def start(self) -> WebDriver:
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=%d,%d" % (self.window_width, self.window_height))
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=vi-VN")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = self._create_driver(options)
        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(shopee_crawl.IMPLICIT_WAIT)
        self.driver = driver
        logger.info("Browser started (headless=%s)", self.headless)
        return driver

    def _create_driver(self, options: Options) -> WebDriver:
        try:
            return webdriver.Chrome(options=options)
        except (SessionNotCreatedException, WebDriverException) as exc:
            logger.warning("Selenium Manager failed (%s); using webdriver-manager", exc)
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )

    def close(self) -> None:
        if self.driver is None:
            return
        try:
            self.driver.quit()
        except WebDriverException as exc:
            logger.warning("Error closing browser: %s", exc)
        finally:
            self.driver = None

    def __enter__(self) -> WebDriver:
        return self.start()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def safe_get(self, url: str) -> bool:
        assert self.driver is not None, "Call start() before navigation"
        try:
            self.driver.get(url)
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError("WebDriver session was closed") from exc
        except TimeoutException:
            logger.warning("Timeout loading page: %s", url)
            return False
        except WebDriverException as exc:
            logger.error("WebDriver error loading %s: %s", url, exc)
            return False
        self._check_captcha(url)
        self._check_login_wall(url)
        return True

    def check_current_page_access(self, requested_url: str) -> None:
        assert self.driver is not None, "Call start() before checking access"
        self._check_captcha(requested_url)
        self._check_login_wall(requested_url)

    def _check_login_wall(self, requested_url: str) -> None:
        assert self.driver is not None
        try:
            current_url = self.driver.current_url
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError("WebDriver session was closed") from exc
        except WebDriverException:
            return
        for marker in shopee_crawl.LOGIN_WALL_URL_MARKERS:
            if marker in current_url and marker not in requested_url:
                raise LoginWallDetectedError(
                    "Redirected to login wall: requested=%s current=%s"
                    % (requested_url, current_url)
                )

    def _check_captcha(self, url: str) -> None:
        assert self.driver is not None
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            title = (self.driver.title or "").lower()
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError("WebDriver session was closed") from exc
        except WebDriverException:
            return
        for marker in shopee_crawl.CAPTCHA_MARKERS:
            if marker.lower() in body_text or marker.lower() in title:
                raise CaptchaDetectedError("CAPTCHA detected at %s" % url)
        try:
            widgets = self.driver.find_elements(
                By.CSS_SELECTOR,
                "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[title*='captcha' i]",
            )
        except WebDriverException:
            widgets = []
        if widgets:
            raise CaptchaDetectedError("CAPTCHA widget detected at %s" % url)

    def wait_for_element(
        self, by: str, value: str, timeout: Optional[int] = None
    ) -> Optional[WebElement]:
        assert self.driver is not None
        try:
            return WebDriverWait(self.driver, timeout or shopee_crawl.PRODUCT_TIMEOUT).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            return None

    def wait_for_elements(
        self, by: str, value: str, timeout: Optional[int] = None
    ) -> List[WebElement]:
        assert self.driver is not None
        try:
            WebDriverWait(self.driver, timeout or shopee_crawl.PRODUCT_TIMEOUT).until(
                EC.presence_of_element_located((by, value))
            )
            return self.driver.find_elements(by, value)
        except TimeoutException:
            return []

    def wait_for_products(
        self, by: str = By.CSS_SELECTOR, value: str = "", timeout: Optional[int] = None
    ) -> List[WebElement]:
        return self.wait_for_elements(by, value, timeout)

    def scroll_to_bottom(
        self,
        max_scrolls: Optional[int] = None,
        pause_seconds: float = 1.0,
        stop_after_no_new_height: Optional[int] = None,
    ) -> int:
        assert self.driver is not None
        max_scrolls = max_scrolls or shopee_crawl.MAX_SCROLLS_PER_PAGE
        stop_after_no_new_height = stop_after_no_new_height or shopee_crawl.STOP_AFTER_NO_NEW_PRODUCTS
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        unchanged = 0
        completed = 0
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_seconds)
            completed += 1
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            unchanged = unchanged + 1 if new_height == last_height else 0
            if unchanged >= stop_after_no_new_height:
                break
            last_height = new_height
        return completed

    def scroll_incrementally(
        self,
        step_px: int = 800,
        pause_seconds: float = 0.5,
        max_scrolls: Optional[int] = None,
    ) -> int:
        """Scroll by fixed steps until the page bottom or the limit."""
        assert self.driver is not None
        max_scrolls = max_scrolls or shopee_crawl.MAX_SCROLLS_PER_PAGE
        completed = 0
        for _ in range(max_scrolls):
            at_bottom = self.driver.execute_script(
                "return (window.innerHeight + window.scrollY) >= "
                "document.body.scrollHeight - 5;"
            )
            if at_bottom:
                break
            self.driver.execute_script("window.scrollBy(0, %d);" % step_px)
            time.sleep(pause_seconds)
            completed += 1
        return completed

    def save_debug_snapshot(self, label: str) -> Tuple[str, str]:
        assert self.driver is not None
        debug_dir = shopee_crawl.LOGS_DIR / "debug_snapshots"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(char if char.isalnum() else "_" for char in label)[:50]
        png_path = debug_dir / (timestamp + "_" + safe_label + ".png")
        html_path = debug_dir / (timestamp + "_" + safe_label + ".html")
        try:
            self.driver.save_screenshot(str(png_path))
        except WebDriverException:
            png_path = None
        try:
            html_path.write_text(self.driver.page_source, encoding="utf-8")
        except (WebDriverException, OSError):
            html_path = None
        return (str(png_path) if png_path else "", str(html_path) if html_path else "")
