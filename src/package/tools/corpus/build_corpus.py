"""Dựng ItemCorpus từ meta_<Domain>.jsonl.gz, chỉ giữ item có trong mapping, và kiểm tra độ phủ."""

from __future__ import annotations

import sqlite3
import time
from itertools import islice

import pandas as pd

from package.data import namespaced_item_id
from package.data.loader import load_item_metadata

from .item_corpus import ItemCorpus
from .._schema import ITEM_COLUMNS
from ._helper import normalize_categories
from ._schema import COVERAGE_SAMPLE
from ._sql import (
    CATEGORIES_INDEXES,
    CATEGORIES_TABLE_SCHEMA,
    FTS_POPULATE_SQL,
    FTS_TABLE_SCHEMA,
    ITEMS_INDEXES,
)


def build_corpus(
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
) -> tuple[ItemCorpus, pd.DataFrame, float]:
    """
    meta_files: [(domain, đường dẫn meta)].
    item2id: mapping từ namespaced item_id ('Domain::asin') sang integer id.
    min_coverage: tỉ lệ tối thiểu item mapping phải có metadata, dưới mức này ném ValueError
    (thường do sai file meta hoặc sai định dạng id).
    Trả về (corpus, bảng metadata đã lọc, độ phủ ước lượng) — bảng này còn dùng để dựng text cho query mô phỏng.
    """

    def in_mapping(domain: str, asin: str) -> bool:
        return namespaced_item_id(domain, asin) in item2id

    meta = load_item_metadata(meta_files, keep=in_mapping)
    corpus = ItemCorpus.from_dataframe(meta)
    sample = list(islice(item2id, COVERAGE_SAMPLE))
    coverage = len(corpus.item_domains(sample)) / max(1, len(sample))
    if coverage < min_coverage:
        raise ValueError(
            f"Chỉ {coverage:.1%} item mapping có metadata (cần ≥ {min_coverage:.0%}): "
            "kiểm tra resource/raw/meta_<Domain>.jsonl.gz và định dạng id."
        )
    return corpus, meta, coverage


def _build_corpus_with_timing(
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
) -> tuple[ItemCorpus, pd.DataFrame, float, dict[str, float]]:
    """
    Same as build_corpus, but also returns timing information for each build step.

    Returns:
        (corpus, meta, coverage, build_times) where build_times is a dict with keys:
        - load_meta: time to load and parse metadata files
        - to_sql: time to create items table
        - categories: time to create item_categories table
        - indexes: time to create indexes
        - fts: time to populate FTS5 table
    """

    def in_mapping(domain: str, asin: str) -> bool:
        return namespaced_item_id(domain, asin) in item2id

    build_times = {}

    # Step (a): load metadata
    t0 = time.perf_counter()
    meta = load_item_metadata(meta_files, keep=in_mapping)
    build_times["load_meta"] = time.perf_counter() - t0
    print(f"  Corpus load_meta: {build_times['load_meta']:.2f}s")

    # Step (b): to_sql items table
    t0 = time.perf_counter()

    # Prepare dataframe (copied from ItemCorpus.from_dataframe)
    df = meta.copy()
    if "domain" not in df.columns:
        df["domain"] = meta_files[0][0]  # Use first domain if not present
    if "original_item_id" not in df.columns:
        df["original_item_id"] = df["parent_asin"]
    df["item_id"] = [namespaced_item_id(d, a) for d, a in zip(df["domain"], df["parent_asin"])]

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
    df[list(ITEM_COLUMNS)].to_sql("items", conn, index=False)
    build_times["to_sql"] = time.perf_counter() - t0
    print(f"  Corpus to_sql: {build_times['to_sql']:.2f}s")

    # Step (c): build item_categories
    t0 = time.perf_counter()
    cats = df["categories"] if "categories" in df.columns else pd.Series([None] * len(df))
    rows = []
    for item_id, cs in zip(df["item_id"], cats):
        for cat in normalize_categories(cs, item_id):
            rows.append((item_id, cat))
    conn.execute(CATEGORIES_TABLE_SCHEMA)
    conn.executemany("INSERT INTO item_categories VALUES (?, ?)", rows)
    build_times["categories"] = time.perf_counter() - t0
    print(f"  Corpus categories: {build_times['categories']:.2f}s")

    # Step (d): create indexes
    t0 = time.perf_counter()
    for idx_sql in ITEMS_INDEXES:
        conn.execute(idx_sql)
    for idx_sql in CATEGORIES_INDEXES:
        conn.execute(idx_sql)
    build_times["indexes"] = time.perf_counter() - t0
    print(f"  Corpus indexes: {build_times['indexes']:.2f}s")

    # Step (e): populate FTS
    t0 = time.perf_counter()
    conn.execute(FTS_TABLE_SCHEMA)
    conn.execute(FTS_POPULATE_SQL)
    conn.commit()
    build_times["fts"] = time.perf_counter() - t0
    print(f"  Corpus fts: {build_times['fts']:.2f}s")

    # Create corpus
    corpus = ItemCorpus(conn)

    # Calculate coverage
    sample = list(islice(item2id, COVERAGE_SAMPLE))
    coverage = len(corpus.item_domains(sample)) / max(1, len(sample))
    if coverage < min_coverage:
        raise ValueError(
            f"Chỉ {coverage:.1%} item mapping có metadata (cần ≥ {min_coverage:.0%}): "
            "kiểm tra resource/raw/meta_<Domain>.jsonl.gz và định dạng id."
        )

    return corpus, meta, coverage, build_times
