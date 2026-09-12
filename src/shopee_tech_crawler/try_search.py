"""Manual SearchCrawler probe (Phase 4).

This is not the official CLI (Phase 11). Use it to check whether
selectors.py matches the live DOM.

Usage:
    python -m shopee_tech_crawler.try_search laptop
    python -m shopee_tech_crawler.try_search "tai nghe bluetooth" --pages 2
"""

from local_package.crawler import search_probe_cli

if __name__ == "__main__":
    raise SystemExit(search_probe_cli())
