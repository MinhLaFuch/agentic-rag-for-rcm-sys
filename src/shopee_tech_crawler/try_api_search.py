"""Probe Shopee's public search JSON API without Selenium.

URL/query params in crawler/api_client.py follow Shopee's commonly
documented public API shape and are not yet confirmed against a live
request.

If this script errors or returns 0 products, capture the real request:

1. Open https://shopee.vn/search?keyword=laptop in Chrome by hand.
2. DevTools (F12) → Network → Fetch/XHR.
3. Reload, find a request named like "search_items".
4. Right-click → Copy → Copy as cURL (bash).
5. Send that cURL (cookie/token values can be stripped; URL, query
   param names, and header names are enough).

Usage:
    python -m shopee_tech_crawler.try_api_search laptop --pages 1
"""

from local_package.crawler import api_search_probe_cli

if __name__ == "__main__":
    raise SystemExit(api_search_probe_cli())
