"""
crawler/selectors.py

⚠️ TẤT CẢ selector CSS/XPath của Shopee tập trung ở file này.
Nếu Shopee đổi DOM, chỉ cần sửa ở đây — không sửa logic crawler.

TRẠNG THÁI CALIBRATION (cập nhật theo DOM thật do người dùng cung cấp):
- Trang SEARCH RESULTS (/search?keyword=...): ĐÃ xác nhận bằng DOM thật.
  Neo vào: class BEM ổn định (shopee-search-item-result__item), attribute
  aria-label (không bị hash như class Tailwind/CSS-modules), và
  data-testid. Các field phụ (giá, đã bán, rating) vẫn dùng selector dựa
  trên class utility — CÓ THỂ lệch nếu Shopee đổi bố cục, nhưng có
  fallback graceful (trả None, không crash) trong search_crawler.py.
- Trang PRODUCT DETAIL (Phase 6): CHƯA cần vì Phase 6 sẽ ưu tiên parse
  JSON-LD (<script type="application/ld+json"> Product schema) thay vì
  CSS selector — xem ghi chú trong crawler/parser.py khi tới Phase 6.
  Các selector PRODUCT_* dưới đây vẫn là placeholder/fallback.
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

# --------------------------------------------------------------------------
# Trang search (danh sách sản phẩm) — ĐÃ xác nhận bằng DOM thật
# --------------------------------------------------------------------------
# Container bọc toàn bộ danh sách kết quả search.
SEARCH_RESULTS_CONTAINER = (By.CSS_SELECTOR, "ul.shopee-search-item-result__items")

# 1 "ô" sản phẩm trong danh sách search — LƯU Ý: bao gồm cả ô skeleton
# (đang loading, chưa có link/nội dung thật). search_crawler.py phải tự
# lọc bỏ ô không có link hợp lệ, không phải lỗi của selector.
SEARCH_PRODUCT_CARD_SELECTOR = (By.CSS_SELECTOR, "li.shopee-search-item-result__item")

# Link sản phẩm bên trong 1 card. Ưu tiên aria-label="View product: ..."
# (accessibility attribute, ổn định hơn class), fallback href chứa "-i.".
CARD_LINK_SELECTOR = (By.CSS_SELECTOR, "a[aria-label^='View product'], a[href*='-i.']")

# Nhóm bọc ngoài card có aria-label="Product card: <tên đầy đủ>" — lấy
# TÊN SẢN PHẨM từ đây ổn định hơn nhiều so với đào vào div Tailwind lồng
# nhau (search_crawler.py sẽ strip prefix "Product card: ").
CARD_GROUP_SELECTOR = (By.CSS_SELECTOR, "div[role='group']")

# Field phụ — dựa vào class utility/thiết kế riêng của Shopee (không phải
# hash ngẫu nhiên nhưng vẫn có thể đổi khi Shopee redesign UI).
CARD_PRODUCT_PRICE = (By.CSS_SELECTOR, "div.text-shopee-primary span.truncate")
CARD_PRODUCT_IMAGE = (By.CSS_SELECTOR, "img")
CARD_PRODUCT_SOLD_COUNT = (By.CSS_SELECTOR, "div.truncate.text-shopee-black87.text-xs")
CARD_PRODUCT_RATING = (By.CSS_SELECTOR, "div.flex.items-center span.truncate")

# aria-label="location-<Tên tỉnh/thành>" — attribute rõ ràng, không phải class.
CARD_SHOP_LOCATION = (By.CSS_SELECTOR, "span[data-testid='a11y-label'][aria-label^='location-']")

# --------------------------------------------------------------------------
# Pagination — DỰA TRÊN quan sát DOM thật (chưa test click thật, sẽ xác
# nhận thêm khi chạy discovery thật lần đầu)
# --------------------------------------------------------------------------
PAGINATION_CONTAINER = (By.CSS_SELECTOR, "nav.shopee-page-controller")
PAGINATION_TOTAL_PAGES = (By.CSS_SELECTOR, "span.shopee-mini-page-controller__total")

# --------------------------------------------------------------------------
# Trang product detail (Phase 6) — placeholder, ưu tiên JSON-LD thay vì CSS
# --------------------------------------------------------------------------
PRODUCT_TITLE_SELECTOR = (By.CSS_SELECTOR, "h1")  # fallback nếu JSON-LD thiếu
PRODUCT_PRICE_SELECTOR = (By.CSS_SELECTOR, "[class*='product-price' i]")  # fallback
PRODUCT_RATING_SELECTOR = (By.CSS_SELECTOR, "[class*='product-rating' i]")  # fallback
PRODUCT_IMAGES_SELECTOR = (By.CSS_SELECTOR, "div[class*='thumbnail' i] img")  # fallback
PRODUCT_DESCRIPTION_SELECTOR = (By.CSS_SELECTOR, "[class*='product-description' i]")  # fallback
PRODUCT_VARIANT_SELECTOR = (By.CSS_SELECTOR, "[class*='variant' i]")  # TODO xác nhận DOM thật
PRODUCT_SHOP_NAME_SELECTOR = (By.CSS_SELECTOR, "[class*='shop-name' i]")  # fallback

