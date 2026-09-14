"""
crawler/browser.py

BrowserManager: quản lý vòng đời Selenium WebDriver (Chrome) dùng chung
cho SearchCrawler và ProductCrawler.

Nguyên tắc:
- Ưu tiên explicit wait (WebDriverWait) thay vì time.sleep() cố định.
- implicit_wait = 0 (đặt trong config/settings.py).
- Không triển khai bất kỳ kỹ thuật bypass CAPTCHA / anti-bot nào.
  Nếu phát hiện CAPTCHA/access-denied: log CAPTCHA_DETECTED và trả
  quyền quyết định (dừng / pause) cho tầng gọi phía trên.
"""

from __future__ import annotations

from types import TracebackType
from typing import Iterable

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

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaDetectedError(Exception):
    """Raised khi phát hiện CAPTCHA / access-denied trên trang hiện tại.

    Đây KHÔNG phải lỗi để retry — tầng gọi phải xử lý graceful
    (dừng crawler hoặc pause session), không được cố bypass.
    """


class LoginWallDetectedError(Exception):
    """Raised khi trang bị redirect sang màn hình yêu cầu đăng nhập
    thay vì hiển thị nội dung công khai (vd search results).

    Đây là tín hiệu automation-detection (Selenium bị phát hiện), KHÔNG
    phải hành vi bình thường khi duyệt web thủ công. Tầng gọi phải dừng
    graceful — TUYỆT ĐỐI không tự động hoá việc đăng nhập, không giả
    mạo fingerprint/navigator.webdriver, không dùng driver đã patch để
    né phát hiện. Đây là ranh giới đạo đức đã thống nhất với người dùng.
    """


class BrowserSessionClosedError(Exception):
    """Raised khi cửa sổ Chrome hoặc phiên WebDriver đã bị đóng."""


class BrowserManager:
    """Quản lý một phiên Chrome WebDriver duy nhất.

    Ví dụ:
        browser = BrowserManager()
        driver = browser.start()
        driver.get(url)
        ...
        browser.close()

    Hoặc dùng context manager:
        with BrowserManager() as driver:
            driver.get(url)
    """

    def __init__(
        self,
        headless: bool | None = None,
        window_width: int | None = None,
        window_height: int | None = None,
        page_load_timeout: int | None = None,
    ) -> None:
        self.headless = settings.HEADLESS if headless is None else headless
        self.window_width = window_width or settings.WINDOW_WIDTH
        self.window_height = window_height or settings.WINDOW_HEIGHT
        self.page_load_timeout = page_load_timeout or settings.PAGE_LOAD_TIMEOUT
        self.driver: WebDriver | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> WebDriver:
        """Khởi tạo và trả về Chrome WebDriver đã cấu hình."""
        options = Options()

        if self.headless:
            # "new" headless mode ổn định hơn với các site render nặng JS.
            options.add_argument("--headless=new")

        options.add_argument(f"--window-size={self.window_width},{self.window_height}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=vi-VN")
        # Giảm log rác của Chrome trong console.
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        driver = self._create_driver(options)

        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(settings.IMPLICIT_WAIT)

        self.driver = driver
        logger.info(
            "Browser started (headless=%s, window=%sx%s)",
            self.headless,
            self.window_width,
            self.window_height,
        )
        return driver

    def _create_driver(self, options: Options) -> WebDriver:
        """Tạo Chrome WebDriver, ưu tiên Selenium Manager (built-in từ Selenium
        4.6+) vì nó tự dò đúng version Chrome đã cài và tải chromedriver khớp
        version — tránh lỗi SessionNotCreatedException do version lệch nhau
        (vấn đề hay gặp với webdriver-manager khi cache driver cũ hoặc Chrome
        vừa tự động update).

        Nếu Selenium Manager thất bại vì lý do khác (ví dụ máy không có mạng
        để Selenium Manager tự tải), fallback sang webdriver-manager.
        """
        try:
            # Không truyền `service` -> Selenium 4.6+ tự dùng Selenium Manager,
            # tự dò chromedriver khớp đúng version Chrome đang cài.
            return webdriver.Chrome(options=options)
        except SessionNotCreatedException as exc:
            logger.warning(
                "Selenium Manager tạo driver lỗi version-mismatch (%s). "
                "Thử fallback sang webdriver-manager...",
                exc,
            )
        except WebDriverException as exc:
            logger.warning(
                "Selenium Manager không tạo được driver (%s). "
                "Thử fallback sang webdriver-manager...",
                exc,
            )

        # Fallback: webdriver-manager (xoá cache cũ trước để tránh lệch version)
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def close(self) -> None:
        """Đóng browser an toàn (không raise nếu đã đóng / lỗi)."""
        if self.driver is None:
            return
        try:
            self.driver.quit()
            logger.info("Browser closed")
        except WebDriverException as exc:
            logger.warning("Lỗi khi đóng browser (bỏ qua): %s", exc)
        finally:
            self.driver = None

    def __enter__(self) -> WebDriver:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def safe_get(self, url: str) -> bool:
        """Điều hướng tới `url`, trả về True/False thay vì raise.

        Sau khi load xong sẽ kiểm tra CAPTCHA/access-denied và raise
        CaptchaDetectedError nếu phát hiện (tầng gọi bắt exception này
        riêng biệt với lỗi mạng thông thường).
        """
        assert self.driver is not None, "Phải gọi start() trước"
        try:
            self.driver.get(url)
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError(
                "Chrome/WebDriver session was closed before navigation completed."
            ) from exc
        except TimeoutException:
            logger.warning("Timeout khi load trang: %s", url)
            return False
        except WebDriverException as exc:
            logger.error("Lỗi WebDriver khi load %s: %s", url, exc)
            return False

        self._check_captcha(url)
        self._check_login_wall(url)
        return True

    def check_current_page_access(self, requested_url: str) -> None:
        """Kiểm tra lại CAPTCHA/login wall sau các thao tác tải động.

        Hàm chỉ phát hiện trạng thái chặn và raise để caller dừng; không tự
        đăng nhập, giải CAPTCHA hay thay đổi fingerprint trình duyệt.
        """
        assert self.driver is not None, "Phải gọi start() trước"
        self._check_captcha(requested_url)
        self._check_login_wall(requested_url)

    def _check_login_wall(self, requested_url: str) -> None:
        """Phát hiện bị redirect sang trang đăng nhập thay vì nội dung
        công khai được yêu cầu (dấu hiệu automation-detection).

        Dùng URL route công khai của Shopee (`/buyer/login`) làm tín hiệu
        chính — đây là routing convention công khai, ổn định hơn nhiều so
        với text/class nội bộ (vd link "Đăng Nhập" luôn xuất hiện ở góc
        mọi trang Shopee kể cả khi KHÔNG bị chặn, nên không thể dùng text
        đó làm marker — sẽ false-positive 100% các trang).

        Nếu marker này vẫn miss/false-positive ở lần chạy tới, hãy gửi
        `current_url` thực tế lúc bị chặn (in trong log/debug snapshot)
        để tinh chỉnh — không tự đoán thêm.
        """
        assert self.driver is not None
        try:
            current_url = self.driver.current_url
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError(
                "Chrome/WebDriver session was closed while checking access."
            ) from exc
        except WebDriverException:
            return

        requested_path = requested_url.split("?", 1)[0].rstrip("/")
        current_path = current_url.split("?", 1)[0].rstrip("/")

        for marker in settings.LOGIN_WALL_URL_MARKERS:
            if marker in current_url and marker not in requested_url:
                logger.error(
                    "LOGIN_WALL_DETECTED: yêu cầu %s nhưng bị redirect sang %s "
                    "(marker=%r) — dấu hiệu automation-detection, KHÔNG cố đăng nhập/bypass.",
                    requested_path,
                    current_path,
                    marker,
                )
                raise LoginWallDetectedError(
                    f"Redirected to login wall: requested={requested_path} current={current_path}"
                )

    def _check_captcha(self, url: str) -> None:
        """Kiểm tra dấu hiệu CAPTCHA/access-denied trên trang hiện tại.

        Không cố bypass — chỉ log CAPTCHA_DETECTED và raise để tầng
        gọi (search_crawler/product_crawler) quyết định dừng/pause.

        QUAN TRỌNG: chỉ quét TEXT HIỂN THỊ THỰC TẾ (`<body>.text`), KHÔNG
        quét `driver.page_source` (HTML thô). Lý do: Shopee nhúng sẵn các
        JSON config nội bộ trong <script> (vd key "pcmall-captcha" trỏ tới
        service endpoint) ở MỌI trang, kể cả khi không hề có CAPTCHA nào
        hiển thị — quét page_source sẽ luôn false-positive với marker
        "captcha". Text hiển thị + widget iframe thật là tín hiệu đáng tin
        cậy hơn nhiều.
        """
        assert self.driver is not None
        try:
            visible_text_lower = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            title_lower = (self.driver.title or "").lower()
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError(
                "Chrome/WebDriver session was closed while checking CAPTCHA."
            ) from exc
        except WebDriverException:
            return

        # Tín hiệu 1: cụm từ cảnh báo xuất hiện trong TEXT HIỂN THỊ (không phải JS/JSON ẩn).
        for marker in settings.CAPTCHA_MARKERS:
            marker_lower = marker.lower()
            if marker_lower in visible_text_lower or marker_lower in title_lower:
                idx = visible_text_lower.find(marker_lower)
                context = (
                    visible_text_lower[max(0, idx - 60): idx + 60] if idx != -1 else "(trong title)"
                )
                logger.error(
                    "CAPTCHA_DETECTED tại %s (marker=%r, title=%r, context=...%r...)",
                    url,
                    marker,
                    self.driver.title,
                    context,
                )
                raise CaptchaDetectedError(f"CAPTCHA detected at {url} (marker={marker!r})")

        # Tín hiệu 2: widget CAPTCHA thật sự được render trên DOM (recaptcha/hcaptcha iframe).
        try:
            widgets = self.driver.find_elements(
                By.CSS_SELECTOR,
                "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[title*='captcha' i]",
            )
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise BrowserSessionClosedError(
                "Chrome/WebDriver session was closed while checking CAPTCHA."
            ) from exc
        except WebDriverException:
            widgets = []
        if widgets:
            logger.error(
                "CAPTCHA_DETECTED tại %s (widget iframe recaptcha/hcaptcha render trên DOM)",
                url,
            )
            raise CaptchaDetectedError(f"CAPTCHA widget detected at {url}")

    # ------------------------------------------------------------------
    # Explicit wait helpers
    # ------------------------------------------------------------------
    def wait_for_element(
        self, by: str, value: str, timeout: int | None = None
    ) -> WebElement | None:
        """Chờ 1 element xuất hiện (presence). Trả về None nếu timeout."""
        assert self.driver is not None
        timeout = timeout or settings.PRODUCT_TIMEOUT
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            logger.warning("Timeout chờ element: (%s, %s)", by, value)
            return None

    def wait_for_elements(
        self, by: str, value: str, timeout: int | None = None
    ) -> list[WebElement]:
        """Chờ ít nhất 1 element trong danh sách xuất hiện. Trả về [] nếu timeout."""
        assert self.driver is not None
        timeout = timeout or settings.PRODUCT_TIMEOUT
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return self.driver.find_elements(by, value)
        except TimeoutException:
            logger.warning("Timeout chờ danh sách element: (%s, %s)", by, value)
            return []

    def wait_for_products(
        self, by: str = By.CSS_SELECTOR, value: str = "", timeout: int | None = None
    ) -> list[WebElement]:
        """Alias có ngữ nghĩa rõ ràng của wait_for_elements, dùng ở search page.

        `value` selector thực tế sẽ được truyền từ crawler/selectors.py (Phase 6),
        browser.py không hard-code selector cụ thể.
        """
        return self.wait_for_elements(by, value, timeout)

    # ------------------------------------------------------------------
    # Scrolling (lazy-loading) — luôn có điều kiện dừng, không while True vô hạn
    # ------------------------------------------------------------------
    def scroll_to_bottom(
        self,
        max_scrolls: int | None = None,
        pause_seconds: float = 1.0,
        stop_after_no_new_height: int | None = None,
    ) -> int:
        """Scroll xuống cuối trang nhiều lần để trigger lazy-loading.

        Dừng khi: đạt `max_scrolls`, HOẶC chiều cao trang không đổi
        `stop_after_no_new_height` lần liên tiếp (đã load hết).

        Trả về số lần đã scroll thực tế.
        """
        import time

        assert self.driver is not None
        max_scrolls = max_scrolls or settings.MAX_SCROLLS_PER_PAGE
        stop_after_no_new_height = (
            stop_after_no_new_height or settings.STOP_AFTER_NO_NEW_PRODUCTS
        )

        last_height = self.driver.execute_script("return document.body.scrollHeight")
        unchanged_count = 0
        scrolls_done = 0

        for _ in range(max_scrolls):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(pause_seconds)
            scrolls_done += 1

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                unchanged_count += 1
                if unchanged_count >= stop_after_no_new_height:
                    logger.info(
                        "scroll_to_bottom: dừng sau %d lần (chiều cao không đổi)",
                        scrolls_done,
                    )
                    break
            else:
                unchanged_count = 0
            last_height = new_height

        return scrolls_done

    def scroll_incrementally(
        self,
        step_px: int = 800,
        pause_seconds: float = 0.5,
        max_scrolls: int | None = None,
    ) -> int:
        """Scroll từng đoạn nhỏ (mô phỏng hành vi người dùng thật hơn scroll thẳng
        xuống cuối). Dừng khi đạt max_scrolls hoặc đã chạm đáy trang.

        Trả về số bước scroll thực tế.
        """
        import time

        assert self.driver is not None
        max_scrolls = max_scrolls or settings.MAX_SCROLLS_PER_PAGE

        scrolls_done = 0
        for _ in range(max_scrolls):
            at_bottom = self.driver.execute_script(
                "return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 5;"
            )
            if at_bottom:
                logger.info("scroll_incrementally: đã chạm đáy trang sau %d bước", scrolls_done)
                break
            self.driver.execute_script(f"window.scrollBy(0, {step_px});")
            time.sleep(pause_seconds)
            scrolls_done += 1

        return scrolls_done

    # ------------------------------------------------------------------
    # Debug / diagnostics
    # ------------------------------------------------------------------
    def save_debug_snapshot(self, label: str) -> tuple[str, str]:
        """Lưu screenshot (.png) + page source (.html) hiện tại vào
        data/logs/debug_snapshots/ — dùng khi crawler ra kết quả bất thường
        (0 sản phẩm, selector không khớp...) để chẩn đoán CHÍNH XÁC trạng
        thái trang thay vì đoán mò. Trả về (screenshot_path, html_path).
        """
        import datetime as _dt

        assert self.driver is not None
        debug_dir = settings.LOGS_DIR / "debug_snapshots"
        debug_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:50]
        png_path = debug_dir / f"{timestamp}_{safe_label}.png"
        html_path = debug_dir / f"{timestamp}_{safe_label}.html"

        try:
            self.driver.save_screenshot(str(png_path))
        except WebDriverException as exc:
            logger.warning("Không chụp được screenshot debug: %s", exc)
            png_path = None  # type: ignore[assignment]

        try:
            html_path.write_text(self.driver.page_source, encoding="utf-8")
        except (WebDriverException, OSError) as exc:
            logger.warning("Không lưu được HTML debug: %s", exc)
            html_path = None  # type: ignore[assignment]

        logger.info(
            "Debug snapshot đã lưu: screenshot=%s html=%s current_url=%s title=%r",
            png_path,
            html_path,
            self.driver.current_url,
            self.driver.title,
        )
        return (str(png_path) if png_path else "", str(html_path) if html_path else "")
