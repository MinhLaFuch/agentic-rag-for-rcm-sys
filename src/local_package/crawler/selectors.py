"""CSS selectors used by the Shopee search crawler."""

from selenium.webdriver.common.by import By

SEARCH_RESULTS_CONTAINER = (By.CSS_SELECTOR, "ul.shopee-search-item-result__items")
SEARCH_PRODUCT_CARD_SELECTOR = (By.CSS_SELECTOR, "li.shopee-search-item-result__item")
CARD_LINK_SELECTOR = (By.CSS_SELECTOR, "a[aria-label^='View product'], a[href*='-i.']")
CARD_GROUP_SELECTOR = (By.CSS_SELECTOR, "div[role='group']")
CARD_PRODUCT_PRICE = (By.CSS_SELECTOR, "div.text-shopee-primary span.truncate")
CARD_PRODUCT_IMAGE = (By.CSS_SELECTOR, "img")
CARD_PRODUCT_SOLD_COUNT = (By.CSS_SELECTOR, "div.truncate.text-shopee-black87.text-xs")
CARD_PRODUCT_RATING = (By.CSS_SELECTOR, "div.flex.items-center span.truncate")
CARD_SHOP_LOCATION = (
	By.CSS_SELECTOR,
	"span[data-testid='a11y-label'][aria-label^='location-']",
)
PAGINATION_CONTAINER = (By.CSS_SELECTOR, "nav.shopee-page-controller")
PAGINATION_TOTAL_PAGES = (By.CSS_SELECTOR, "span.shopee-mini-page-controller__total")
PRODUCT_TITLE_SELECTOR = (By.CSS_SELECTOR, "h1")
PRODUCT_PRICE_SELECTOR = (By.CSS_SELECTOR, "[class*='product-price' i]")
PRODUCT_RATING_SELECTOR = (By.CSS_SELECTOR, "[class*='product-rating' i]")
PRODUCT_IMAGES_SELECTOR = (By.CSS_SELECTOR, "div[class*='thumbnail' i] img")
PRODUCT_DESCRIPTION_SELECTOR = (By.CSS_SELECTOR, "[class*='product-description' i]")
PRODUCT_VARIANT_SELECTOR = (By.CSS_SELECTOR, "[class*='variant' i]")
PRODUCT_SHOP_NAME_SELECTOR = (By.CSS_SELECTOR, "[class*='shop-name' i]")
