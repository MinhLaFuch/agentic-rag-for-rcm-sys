"""
scripts/try_api_search.py

Test thử gọi trực tiếp API search JSON công khai của Shopee bằng HTTP
request thường (KHÔNG dùng Chrome/Selenium) — hướng thay thế sau khi
Selenium bị chặn bởi automation-detection (login-wall).

⚠️ URL/query param trong crawler/api_client.py hiện dựa trên cấu trúc
API phổ biến, công khai của Shopee — CHƯA được xác nhận bằng request
thật (mình không tự test được vì sandbox không truy cập được shopee.vn).

Nếu script này báo lỗi hoặc 0 sản phẩm, lấy request CHÍNH XÁC theo các
bước sau rồi gửi lại cho mình:

1. Mở https://shopee.vn/search?keyword=laptop trên Chrome — duyệt BÌNH
   THƯỜNG bằng tay, KHÔNG qua Selenium.
2. Mở DevTools (F12) → tab Network → lọc "Fetch/XHR".
3. Nhấn F5 để load lại trang, tìm request có tên gần giống
   "search_items" trong danh sách.
4. Chuột phải vào request đó → Copy → Copy as cURL (bash).
5. Dán NGUYÊN VĂN lệnh cURL đó cho mình (có thể chứa cookie — nếu bạn
   ngại lộ thông tin tài khoản, bạn có thể tự xoá giá trị cookie/token
   nhạy cảm trước khi gửi, mình chỉ cần đọc URL + tên các query param
   + tên các header, không cần giá trị cookie thật).

Sử dụng:
    python scripts/try_api_search.py laptop --pages 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.api_client import ShopeeApiClient
from utils.logger import get_logger

logger = get_logger("try_api_search")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test thử ShopeeApiClient.search() với 1 keyword")
    parser.add_argument("keyword", help="Từ khóa search, vd: laptop")
    parser.add_argument("--pages", type=int, default=1, help="Số trang muốn thử (default: 1)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Đang test ShopeeApiClient với keyword={args.keyword!r}, pages={args.pages}\n")

    total_items = 0
    with ShopeeApiClient() as client:
        for page in range(args.pages):
            data = client.search(args.keyword, page=page)

            if data is None:
                print(
                    f"❌ Page {page}: API trả lỗi hoặc không phải JSON hợp lệ — "
                    "xem chi tiết status code/body trong data/logs/crawler.log"
                )
                break

            # error field khác None -> Shopee trả lỗi có cấu trúc (vd yêu cầu login,
            # rate limit...) thay vì HTTP error thông thường.
            if data.get("error") not in (None, 0):
                print(f"⚠️  Page {page}: API trả error={data.get('error')!r}, msg={data.get('error_msg')!r}")
                print("   Đây có thể là dấu hiệu API cũng yêu cầu xác thực/chặn — gửi lại JSON này cho mình.")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
                break

            items = data.get("items") or []
            total_count = data.get("total_count")
            print(f"Page {page}: {len(items)} sản phẩm (total_count báo cáo: {total_count})")

            if items:
                print("\n--- Cấu trúc raw JSON của item đầu tiên (để mình xem field thật) ---")
                print(json.dumps(items[0], ensure_ascii=False, indent=2)[:2500])
                print("--- hết đoạn preview (có thể bị cắt bớt) ---\n")

            total_items += len(items)

    print(f"\n========== KẾT QUẢ ==========")
    print(f"Tổng sản phẩm nhận được: {total_items}")

    if total_items == 0:
        print(
            "\n⚠️ 0 sản phẩm — rất có thể URL/query param trong crawler/api_client.py "
            "chưa khớp API thật. Làm theo hướng dẫn 'Copy as cURL' ở đầu file này "
            "rồi gửi lại cho mình để chỉnh."
        )
    else:
        print(
            "\n✅ Nhận được dữ liệu thật từ API! Gửi lại đoạn JSON preview ở trên cho mình "
            "để mình map chính xác các field (tên, giá, ảnh, rating...) sang product_id/"
            "product_name/... như SearchCrawler cũ, rồi viết lại pipeline discovery dùng "
            "ShopeeApiClient thay cho Selenium."
        )


if __name__ == "__main__":
    main()
