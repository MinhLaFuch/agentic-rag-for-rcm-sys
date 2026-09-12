from crawler.browser import BrowserManager

bm = BrowserManager(headless=True)
driver = bm.start()
ok = bm.safe_get("https://shopee.vn")
print("safe_get:", ok)
print("title:", driver.title)
bm.close()