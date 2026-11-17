"""Select an existing audit bundle without changing application defaults."""

from __future__ import annotations

import re

from .get_data_paths import get_data_paths
from .resolve_dataset_tag import resolve_dataset_tag
from ._dataclass import DataPaths


def resolve_bundle_paths(tag: str | None = None, domains: list[str] | None = None) -> DataPaths:
    """Resolve a safe explicit tag, retaining domain-derived selection when absent.

    Selecting a tag does not waive manifest, mapping or runtime compatibility checks.
    """
    if tag is not None and (
        not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", tag)
    ):
        raise ValueError("Bundle tag must contain only letters, digits, underscores or hyphens")
    if domains:
        resolve_dataset_tag(domains)  # Preserve unknown-domain/subset validation.
    return get_data_paths(tag=tag, domains=domains)
