"""Console-oriented probe helpers used by shopee_tech_crawler scripts."""

from __future__ import annotations

import argparse
import json
import time
from typing import Callable, Optional, Sequence

from local_package.config import shopee_crawl

from .api_client import ShopeeApiClient
from .browser import (
    BrowserManager,
    BrowserSessionClosedError,
    CaptchaDetectedError,
    LoginWallDetectedError,
)
from .search_crawler import SearchCrawler

SEARCH_CARD_FIELDS = ("product_name", "price_raw", "rating_raw", "sold_count_raw")
_Pause = Callable[[str], str]


def print_skeleton_status() -> None:
    print("Shopee Tech Crawler — Phase 1 skeleton check")
    print(f"PROJECT_ROOT       : {shopee_crawl.PROJECT_ROOT}")
    print(f"BASE_URL            : {shopee_crawl.BASE_URL}")
    print(f"HEADLESS            : {shopee_crawl.HEADLESS}")
    print(f"MAX_PAGES_PER_KEYWORD: {shopee_crawl.MAX_PAGES_PER_KEYWORD}")
    print(f"MIN_DELAY / MAX_DELAY: {shopee_crawl.MIN_DELAY} / {shopee_crawl.MAX_DELAY}")
    print(f"Số category đã cấu hình: {len(shopee_crawl.CATEGORIES)}")
    print(f"5 keyword đầu tiên: {shopee_crawl.all_keywords()[:5]}")
    print(f"PRODUCTS_JSONL_PATH : {shopee_crawl.PRODUCTS_JSONL_PATH}")
    print(f"CHECKPOINT_DB_PATH  : {shopee_crawl.CHECKPOINT_DB_PATH}")
    print("\n✅ Skeleton OK — sẵn sàng cho PHASE 2 trở đi.")


def probe_browser(url: Optional[str] = None, headless: bool = True) -> int:
    target = url or shopee_crawl.BASE_URL
    browser = BrowserManager(headless=headless)
    driver = browser.start()
    try:
        ok = browser.safe_get(target)
        print("safe_get:", ok)
        print("title:", driver.title)
        return 0 if ok else 1
    finally:
        browser.close()


def run_search_probe(
    keyword: str,
    max_pages: int = 1,
    headless: Optional[bool] = None,
    manual_auth: bool = False,
    pause: _Pause = input,
) -> int:
    print(f"Đang test SearchCrawler với keyword={keyword!r}, max_pages={max_pages}")
    print(
        "(Khuyên dùng --no-headless ở lần chạy đầu để tự mắt xem Chrome "
        "có bị chặn/captcha không)\n"
    )

    browser = BrowserManager(headless=False if manual_auth else headless)
    driver = browser.start()
    found = 0
    missing_fields_count = 0
    started = time.time()
    exit_code = 0

    try:
        if manual_auth:
            driver.get(shopee_crawl.BASE_URL)
            print("Chrome đã mở tại Shopee.")
            print("1. Tự đăng nhập/xác thực trực tiếp trong cửa sổ Chrome nếu được phép.")
            print("2. Mở thử trang tìm kiếm, bảo đảm danh sách sản phẩm hiển thị.")
            pause("3. Quay lại đây và nhấn Enter để crawler kiểm tra phiên rồi tiếp tục... ")
            browser.check_current_page_access(shopee_crawl.BASE_URL)

        crawler = SearchCrawler(browser)
        for index, item in enumerate(crawler.search(keyword, max_pages=max_pages), start=1):
            found += 1
            missing = [key for key in SEARCH_CARD_FIELDS if not item.get(key)]
            if missing:
                missing_fields_count += 1
            _print_search_item(index, item, missing)
    except CaptchaDetectedError as exc:
        print(f"\n❌ CAPTCHA_DETECTED — dừng ngay, không thử bypass: {exc}")
        print("   Xem chi tiết trong data/logs/crawler.log")
        _try_snapshot(browser, f"captcha_{keyword}")
        exit_code = 1
    except LoginWallDetectedError as exc:
        print(f"\n❌ LOGIN_WALL_DETECTED — bị redirect sang trang đăng nhập: {exc}")
        print(
            "   Đây là dấu hiệu Selenium bị phát hiện là automation. Theo đúng nguyên tắc đã "
            "thống nhất, script KHÔNG tự động đăng nhập hay né tránh phát hiện."
        )
        paths = _try_snapshot(browser, f"loginwall_{keyword}")
        if paths:
            print(f"   Debug snapshot: {paths[0]} | {paths[1]}")
        exit_code = 1
    except BrowserSessionClosedError as exc:
        print(f"\n❌ BROWSER_SESSION_CLOSED — {exc}")
        print(
            "   Cửa sổ Chrome do script mở đã bị đóng hoặc mất kết nối. "
            "Hãy chạy lại và không đóng cửa sổ đó trước khi nhấn Enter."
        )
        exit_code = 1
    finally:
        if found == 0 and exit_code == 0:
            paths = _try_snapshot(browser, f"try_search_{keyword}")
            if paths:
                print("\n📸 Đã lưu debug snapshot để chẩn đoán:")
                print(f"   Screenshot: {paths[0]}")
                print(f"   HTML      : {paths[1]}")
            elif paths is False:
                pass
        browser.close()

    if exit_code != 0:
        return exit_code

    elapsed = time.time() - started
    print("========== KẾT QUẢ ==========")
    print(f"Tổng sản phẩm tìm được : {found}")
    print(f"Sản phẩm thiếu field   : {missing_fields_count}")
    print(f"Thời gian chạy         : {elapsed:.1f}s")
    _print_search_outcome(found, missing_fields_count)
    return 0


def run_api_search_probe(keyword: str, pages: int = 1) -> int:
    print(f"Đang test ShopeeApiClient với keyword={keyword!r}, pages={pages}\n")
    total_items = 0

    with ShopeeApiClient() as client:
        for page in range(pages):
            data = client.search(keyword, page=page)
            if data is None:
                print(
                    f"❌ Page {page}: API trả lỗi hoặc không phải JSON hợp lệ — "
                    "xem chi tiết status code/body trong data/logs/crawler.log"
                )
                break
            if data.get("error") not in (None, 0):
                print(
                    f"⚠️  Page {page}: API trả error={data.get('error')!r}, "
                    f"msg={data.get('error_msg')!r}"
                )
                print("   Đây có thể là dấu hiệu API cũng yêu cầu xác thực/chặn — gửi lại JSON này.")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
                break
            items = data.get("items") or []
            print(
                f"Page {page}: {len(items)} sản phẩm "
                f"(total_count báo cáo: {data.get('total_count')})"
            )
            if items:
                print("\n--- Cấu trúc raw JSON của item đầu tiên (để xem field thật) ---")
                print(json.dumps(items[0], ensure_ascii=False, indent=2)[:2500])
                print("--- hết đoạn preview (có thể bị cắt bớt) ---\n")
            total_items += len(items)

    print("\n========== KẾT QUẢ ==========")
    print(f"Tổng sản phẩm nhận được: {total_items}")
    if total_items == 0:
        print(
            "\n⚠️ 0 sản phẩm — rất có thể URL/query param trong crawler/api_client.py "
            "chưa khớp API thật. Làm theo hướng dẫn 'Copy as cURL' ở đầu script "
            "rồi gửi lại để chỉnh."
        )
    else:
        print(
            "\n✅ Nhận được dữ liệu thật từ API! Gửi lại đoạn JSON preview ở trên "
            "để map field (tên, giá, ảnh, rating...) sang product_id/product_name/..."
        )
    return 0 if total_items else 1


def search_probe_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test thử SearchCrawler với 1 keyword")
    parser.add_argument("keyword", help="Từ khóa search, vd: laptop")
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Số trang search tối đa muốn crawl (default: 1)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Chạy Chrome headless (mặc định lấy theo .env/HEADLESS)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Mở Chrome có giao diện (khuyên dùng khi debug selector lần đầu)",
    )
    parser.add_argument(
        "--manual-auth",
        action="store_true",
        help=(
            "Mở Chrome để tự đăng nhập/xác thực thủ công trước khi crawl. "
            "Không lưu hay tự điền mật khẩu/OTP; luôn chạy không headless."
        ),
    )
    args = parser.parse_args(argv)
    return run_search_probe(
        keyword=args.keyword,
        max_pages=args.pages,
        headless=args.headless,
        manual_auth=args.manual_auth,
    )


def api_search_probe_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test thử ShopeeApiClient.search() với 1 keyword")
    parser.add_argument("keyword", help="Từ khóa search, vd: laptop")
    parser.add_argument("--pages", type=int, default=1, help="Số trang muốn thử (default: 1)")
    args = parser.parse_args(argv)
    return run_api_search_probe(args.keyword, pages=args.pages)


def _print_search_item(index: int, item: dict, missing: list) -> None:
    print(f"--- Sản phẩm #{index} ---")
    print(f"  product_id   : {item['product_id']}")
    print(f"  product_name : {item['product_name']}")
    print(f"  product_url  : {item['product_url']}")
    print(f"  price_raw    : {item['price_raw']}")
    print(f"  sold_count   : {item['sold_count_raw']}")
    print(f"  rating_raw   : {item['rating_raw']}")
    print(f"  shop_location: {item['shop_location_raw']}")
    print(f"  image_url    : {item['image_url']}")
    if missing:
        print(f"  ⚠️  Field rỗng: {missing}")
    print()


def _print_search_outcome(found: int, missing_fields_count: int) -> None:
    if found == 0:
        print(
            "\n⚠️  0 sản phẩm — mở file screenshot .png ở trên để tự xem Chrome đang hiển thị "
            "gì (login wall? loading vô hạn? bị chặn dạng khác?). Nếu cần xem cùng, gửi "
            "lại file .html (hoặc mở nó, tìm đoạn quanh khu vực danh sách sản phẩm rồi copy)."
        )
    elif missing_fields_count > 0:
        print(
            f"\n⚠️  {missing_fields_count}/{found} sản phẩm thiếu field giá/rating/đã bán — "
            "gửi HTML phần đó (vd Copy outerHTML của khối giá) để chỉnh lại selector."
        )
    else:
        print("\n✅ Tất cả sản phẩm parse đầy đủ field — sẵn sàng sang Phase 5 (ProductCrawler).")


def _try_snapshot(browser: BrowserManager, label: str):
    try:
        return browser.save_debug_snapshot(label)
    except Exception as exc:  # noqa: BLE001
        print(f"(Không lưu được debug snapshot: {exc})")
        return False
