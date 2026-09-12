"""
scripts/try_search.py

Script test thủ công cho Phase 4 — chạy SearchCrawler thật (mở Chrome
thật) với 1 keyword, in kết quả discovery ra console.

⚠️ Đây KHÔNG phải CLI chính thức (sẽ làm ở Phase 11). Dùng để bạn tự
kiểm tra selectors.py có khớp DOM thật hay không trước khi đi tiếp.

Sử dụng:
    python scripts/try_search.py laptop
    python scripts/try_search.py "tai nghe bluetooth" --pages 2
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Cho phép chạy trực tiếp bằng `python scripts/try_search.py` từ project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.browser import (
    BrowserManager,
    BrowserSessionClosedError,
    CaptchaDetectedError,
    LoginWallDetectedError,
)
from crawler.search_crawler import SearchCrawler
from config import settings
from utils.logger import get_logger

logger = get_logger("try_search")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test thử SearchCrawler với 1 keyword")
    parser.add_argument("keyword", help="Từ khóa search, vd: laptop")
    parser.add_argument(
        "--pages", type=int, default=1, help="Số trang search tối đa muốn crawl (default: 1)"
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
            "Mở Chrome để bạn tự đăng nhập/xác thực thủ công trước khi crawl. "
            "Không lưu hay tự điền mật khẩu/OTP; luôn chạy không headless."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Đang test SearchCrawler với keyword={args.keyword!r}, max_pages={args.pages}")
    print("(Khuyên dùng --no-headless ở lần chạy đầu để tự mắt xem Chrome có bị chặn/captcha không)\n")

    browser = BrowserManager(headless=False if args.manual_auth else args.headless)
    driver = browser.start()

    found = 0
    missing_fields_count = 0
    t0 = time.time()

    try:
        if args.manual_auth:
            # Không dùng safe_get: người dùng cần thao tác trước khi code kiểm
            # tra trạng thái đăng nhập/xác thực và quyết định dừng.
            driver.get(settings.BASE_URL)
            print("Chrome đã mở tại Shopee.")
            print("1. Tự đăng nhập/xác thực trực tiếp trong cửa sổ Chrome nếu được phép.")
            print("2. Mở thử trang tìm kiếm, bảo đảm danh sách sản phẩm hiển thị.")
            input("3. Quay lại đây và nhấn Enter để crawler kiểm tra phiên rồi tiếp tục... ")
            browser.check_current_page_access(settings.BASE_URL)

        crawler = SearchCrawler(browser)
        for i, item in enumerate(crawler.search(args.keyword, max_pages=args.pages), start=1):
            found += 1
            missing = [k for k in ("product_name", "price_raw", "rating_raw", "sold_count_raw") if not item.get(k)]
            if missing:
                missing_fields_count += 1

            print(f"--- Sản phẩm #{i} ---")
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

    except CaptchaDetectedError as exc:
        print(f"\n❌ CAPTCHA_DETECTED — dừng ngay, không thử bypass: {exc}")
        print("   Xem chi tiết trong data/logs/crawler.log")
        try:
            browser.save_debug_snapshot(f"captcha_{args.keyword}")
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)

    except LoginWallDetectedError as exc:
        print(f"\n❌ LOGIN_WALL_DETECTED — bị redirect sang trang đăng nhập: {exc}")
        print(
            "   Đây là dấu hiệu Selenium bị phát hiện là automation. Theo đúng nguyên tắc đã "
            "thống nhất, script KHÔNG tự động đăng nhập hay né tránh phát hiện."
        )
        try:
            png_path, html_path = browser.save_debug_snapshot(f"loginwall_{args.keyword}")
            print(f"   Debug snapshot: {png_path} | {html_path}")
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)

    except BrowserSessionClosedError as exc:
        print(f"\n❌ BROWSER_SESSION_CLOSED — {exc}")
        print(
            "   Cửa sổ Chrome do script mở đã bị đóng hoặc mất kết nối. "
            "Hãy chạy lại và không đóng cửa sổ đó trước khi nhấn Enter."
        )
        sys.exit(1)

    finally:
        if found == 0:
            try:
                png_path, html_path = browser.save_debug_snapshot(f"try_search_{args.keyword}")
                print(f"\n📸 Đã lưu debug snapshot để chẩn đoán:")
                print(f"   Screenshot: {png_path}")
                print(f"   HTML      : {html_path}")
            except Exception as exc:  # noqa: BLE001 — debug snapshot không được che lỗi gốc
                print(f"(Không lưu được debug snapshot: {exc})")
        browser.close()

    elapsed = time.time() - t0
    print("========== KẾT QUẢ ==========")
    print(f"Tổng sản phẩm tìm được : {found}")
    print(f"Sản phẩm thiếu field   : {missing_fields_count}")
    print(f"Thời gian chạy         : {elapsed:.1f}s")

    if found == 0:
        print(
            "\n⚠️  0 sản phẩm — mở file screenshot .png ở trên để tự xem Chrome đang hiển thị "
            "gì (login wall? loading vô hạn? bị chặn dạng khác?). Nếu cần mình xem cùng, gửi "
            "lại file .html (hoặc mở nó, tìm đoạn quanh khu vực danh sách sản phẩm rồi copy gửi mình)."
        )
    elif missing_fields_count > 0:
        print(
            f"\n⚠️  {missing_fields_count}/{found} sản phẩm thiếu field giá/rating/đã bán — "
            "gửi HTML phần đó (vd Copy outerHTML của khối giá) để mình chỉnh lại selector."
        )
    else:
        print("\n✅ Tất cả sản phẩm parse đầy đủ field — sẵn sàng sang Phase 5 (ProductCrawler).")


if __name__ == "__main__":
    main()
