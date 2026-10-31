"""Dựng ItemCorpus từ meta_<Domain>.jsonl.gz, chỉ giữ item có trong mapping, và kiểm tra độ phủ."""

from __future__ import annotations

import sqlite3
import time

import pandas as pd

from package.data import namespaced_item_id
from package.data.loader import load_item_metadata

from .item_corpus import ItemCorpus
from .._schema import ITEM_COLUMNS
from ._helper import normalize_categories
from ._sql import (
    CATEGORIES_INDEXES,
    CATEGORIES_TABLE_SCHEMA,
    FTS_POPULATE_SQL,
    FTS_TABLE_SCHEMA,
    ITEMS_TABLE_SCHEMA,
    ITEMS_INDEXES,
)


def build_corpus(
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
    timing: bool = False,
    first_seen_ts: dict[str, int] | None = None,
    min_coverage_by_domain: dict[str, float] | None = None,
) -> tuple[ItemCorpus, pd.DataFrame, float] | tuple[ItemCorpus, pd.DataFrame, float, dict[str, float]]:
    """
    meta_files: [(domain, đường dẫn meta)].
    item2id: mapping từ namespaced item_id ('Domain::asin') sang integer id.
    min_coverage: tỉ lệ tối thiểu item mapping phải có metadata, dưới mức này ném ValueError
    min_coverage_by_domain: các ngưỡng override theo domain; domain chưa khai báo dùng min_coverage.
    (thường do sai file meta hoặc sai định dạng id).
    timing: nếu True, trả về thêm dict thời gian từng bước.
    coverage tương thích float, đồng thời có thuộc tính by_domain chứa số lượng và độ phủ chính xác từng domain.
    """

    def in_mapping(domain: str, asin: str) -> bool:
        return namespaced_item_id(domain, asin) in item2id

    build_times = {} if timing else None

    # Step (a): load metadata
    t0 = time.perf_counter() if timing else None
    meta = load_item_metadata(meta_files, keep=in_mapping)
    duplicates_dropped: dict[str, int] = {domain: 0 for domain, _ in meta_files}
    if not meta.empty:
        before_counts = meta.groupby("domain").size().to_dict()
        fields = [field for field in meta.columns if field not in {"parent_asin", "domain"}]

        def completeness(row: pd.Series) -> int:
            score = 0
            for field in fields:
                value = row[field]
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                try:
                    if pd.isna(value):
                        continue
                except (TypeError, ValueError):
                    pass
                if isinstance(value, (list, tuple, dict, set)) and not value:
                    continue
                score += 1
            return score

        meta["_completeness"] = meta.apply(completeness, axis=1)
        meta = meta.sort_values("_completeness", ascending=False, kind="stable")
        meta = meta.drop_duplicates(["domain", "parent_asin"], keep="first")
        meta = meta.drop(columns="_completeness").reset_index(drop=True)
        after_counts = meta.groupby("domain").size().to_dict()
        duplicates_dropped.update({domain: int(count - after_counts.get(domain, 0))
                                   for domain, count in before_counts.items()})
    meta.attrs["duplicates_dropped_by_domain"] = duplicates_dropped
    if any(duplicates_dropped.values()):
        print("  Metadata duplicate rows dropped by domain: " + ", ".join(
            f"{domain}={count}" for domain, count in sorted(duplicates_dropped.items())
        ))
    if timing:
        build_times["load_meta"] = time.perf_counter() - t0
        print(f"  Corpus load_meta: {build_times['load_meta']:.2f}s")

    # Step (b): to_sql items table
    if timing:
        t0 = time.perf_counter()

    # Prepare dataframe (copied from ItemCorpus.from_dataframe)
    df = meta.copy()
    if "domain" not in df.columns:
        df["domain"] = meta_files[0][0]  # Use first domain if not present
    if "original_item_id" not in df.columns:
        df["original_item_id"] = df["parent_asin"]
    df["item_id"] = [namespaced_item_id(d, a) for d, a in zip(df["domain"], df["parent_asin"])]
    if first_seen_ts is not None:
        df["first_seen_ts"] = df["item_id"].map(first_seen_ts)

    for col in ITEM_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["price"] = pd.to_numeric(
        df["price"].astype("string").str.replace(r"[$,]", "", regex=True), errors="coerce"
    )
    from ._helper import numeric_column
    df["average_rating"] = numeric_column(df["average_rating"], "average_rating")
    df["rating_number"] = numeric_column(df["rating_number"], "rating_number")

    conn = sqlite3.connect(":memory:")
    conn.execute(ITEMS_TABLE_SCHEMA)
    df[list(ITEM_COLUMNS)].to_sql("items", conn, if_exists="append", index=False)
    if timing:
        build_times["to_sql"] = time.perf_counter() - t0
        print(f"  Corpus to_sql: {build_times['to_sql']:.2f}s")

    # Step (c): build item_categories
    if timing:
        t0 = time.perf_counter()
    cats = df["categories"] if "categories" in df.columns else pd.Series([None] * len(df))
    rows = []
    for item_id, cs in zip(df["item_id"], cats):
        for cat in normalize_categories(cs, item_id):
            rows.append((item_id, cat))
    conn.execute(CATEGORIES_TABLE_SCHEMA)
    conn.executemany("INSERT INTO item_categories VALUES (?, ?)", rows)
    if timing:
        build_times["categories"] = time.perf_counter() - t0
        print(f"  Corpus categories: {build_times['categories']:.2f}s")

    # Step (d): create indexes
    if timing:
        t0 = time.perf_counter()
    for idx_sql in ITEMS_INDEXES:
        conn.execute(idx_sql)
    for idx_sql in CATEGORIES_INDEXES:
        conn.execute(idx_sql)
    if timing:
        build_times["indexes"] = time.perf_counter() - t0
        print(f"  Corpus indexes: {build_times['indexes']:.2f}s")

    # Step (e): populate FTS
    if timing:
        t0 = time.perf_counter()
    conn.execute(FTS_TABLE_SCHEMA)
    conn.execute(FTS_POPULATE_SQL)
    conn.commit()
    if timing:
        build_times["fts"] = time.perf_counter() - t0
        print(f"  Corpus fts: {build_times['fts']:.2f}s")

    # Create corpus
    corpus = ItemCorpus(conn)

    # Calculate exact coverage for every mapping domain.
    mapped_by_domain: dict[str, int] = {}
    for item_id in item2id:
        if "::" not in item_id:
            raise ValueError(f"Invalid namespaced item id in mapping: {item_id!r}")
        domain = item_id.split("::", 1)[0]
        mapped_by_domain[domain] = mapped_by_domain.get(domain, 0) + 1
    metadata_by_domain = dict(corpus._conn.execute("SELECT domain, COUNT(*) FROM items GROUP BY domain"))
    by_domain: dict[str, dict[str, float | int]] = {}
    failures = []
    for domain, mapped_count in sorted(mapped_by_domain.items()):
        metadata_count = int(metadata_by_domain.get(domain, 0))
        domain_coverage = metadata_count / mapped_count if mapped_count else 1.0
        threshold = float((min_coverage_by_domain or {}).get(domain, min_coverage))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Metadata coverage threshold for {domain} must be between 0 and 1, got {threshold}")
        by_domain[domain] = {"mapping_items": mapped_count, "metadata_items": metadata_count,
                             "coverage": domain_coverage, "min_coverage": threshold,
                             "duplicate_metadata_rows_dropped": int(duplicates_dropped.get(domain, 0))}
        if domain_coverage < threshold:
            failures.append(f"{domain}: {domain_coverage:.1%} ({metadata_count}/{mapped_count}; required {threshold:.1%})")
    total_mapped = sum(mapped_by_domain.values())
    total_metadata = sum(int(value["metadata_items"]) for value in by_domain.values())
    coverage = _Coverage(total_metadata / total_mapped if total_mapped else 1.0, by_domain)
    for domain, values in by_domain.items():
        print(
            f"  Metadata coverage {domain}: {values['metadata_items']:,}/{values['mapping_items']:,} "
            f"({values['coverage']:.1%}; minimum {values['min_coverage']:.1%})"
        )
    if failures:
        corpus._conn.close()
        raise ValueError("Metadata coverage below threshold by domain: " + "; ".join(failures))

    if timing:
        return corpus, meta, coverage, build_times
    return corpus, meta, coverage


class _Coverage(float):
    """Float-compatible overall metadata coverage carrying per-domain details."""

    def __new__(cls, value: float, by_domain: dict[str, dict[str, float | int]]):
        result = super().__new__(cls, value)
        result.by_domain = by_domain
        return result
