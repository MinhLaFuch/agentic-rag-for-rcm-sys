"""Stable Shopee product identifiers derived from product URLs."""

import hashlib
import re
from typing import Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

_SHOPEE_ID_PATTERN = re.compile(r"-i\.(\d+)\.(\d+)")


def build_product_id(url: str) -> str:
    ids = _extract_shopee_ids(url)
    if ids is not None:
        return "%s_%s" % ids
    return hashlib.sha256(_normalize_url(url).encode("utf-8")).hexdigest()


def _extract_shopee_ids(url: str) -> Optional[Tuple[str, str]]:
    match = _SHOPEE_ID_PATTERN.search(url)
    return match.groups() if match else None


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))
