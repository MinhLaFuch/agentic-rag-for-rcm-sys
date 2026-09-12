"""Entry point of the Shopee Tech Crawler.

Phase 1: skeleton check that config loads and data directories exist.
Full CLI (--keyword, --category, --max-pages, --resume, --export, ...)
belongs to Phase 11.
"""

from local_package.crawler import print_skeleton_status


def main() -> None:
    print_skeleton_status()


if __name__ == "__main__":
    main()
