"""Extract per-item availability timestamps (avail_ts) from raw metadata.

Uses ``package.corpus.build_item_availability`` and project path helpers
(``get_data_paths`` / ``resolve_bundle_paths``) instead of hardcoded paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from package.config import get_domains, resolve_bundle_paths
from package.corpus.build_item_availability import build_item_availability


def _resolve_meta_path(raw_dir: Path, domain: str) -> Path:
    gz_path = raw_dir / f"meta_{domain}.jsonl.gz"
    if gz_path.exists():
        return gz_path
    plain_path = raw_dir / f"meta_{domain}.jsonl"
    if plain_path.exists():
        return plain_path
    return gz_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build item_availability.parquet from raw metadata.")
    ap.add_argument("--tag", default=None, help="Data bundle tag (defaults to data_paths.default_tag).")
    ap.add_argument("--domain", nargs="+", default=None, help="Domains to extract (default: configured domains).")
    ap.add_argument("--raw-dir", type=Path, default=None, help="Override raw metadata directory.")
    ap.add_argument("--out", type=Path, default=None, help="Output parquet path (default: corpus_dir/item_availability.parquet).")
    args = ap.parse_args(argv)

    paths = resolve_bundle_paths(tag=args.tag, domains=args.domain)
    domains = list(args.domain) if args.domain else list(get_domains())
    raw_dir = args.raw_dir if args.raw_dir is not None else paths.raw_dir
    out_path = args.out if args.out is not None else paths.availability_path

    meta_sources = [(domain, _resolve_meta_path(raw_dir, domain)) for domain in domains]
    summary = build_item_availability(meta_sources=meta_sources, output_path=out_path)
    print(
        f"Wrote {summary['items_with_avail_ts']:,} item availability rows "
        f"({summary['total_meta_rows']:,} raw meta rows) to {summary['output_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
