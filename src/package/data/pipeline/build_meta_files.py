"""Helper to build meta_files list for corpus construction."""

from __future__ import annotations

from package.config import DataPaths, get_domains


def build_meta_files(data_paths: DataPaths, domains: list[str] | None = None) -> list[tuple[str, str]]:
    """Build list of (domain, meta_path) tuples for corpus construction.

    Args:
        data_paths: DataPaths configuration.
        domains: List of domain names. If None, uses all domains from config.

    Returns:
        List of (domain, path) tuples for metadata files.
    """
    domain_list = domains or get_domains()
    return [(d, str(data_paths.meta_path(d))) for d in domain_list]
