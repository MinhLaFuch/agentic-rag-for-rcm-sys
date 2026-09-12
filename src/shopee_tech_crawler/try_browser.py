"""Smoke-test BrowserManager against Shopee."""

from local_package.crawler import probe_browser

if __name__ == "__main__":
    raise SystemExit(probe_browser())
