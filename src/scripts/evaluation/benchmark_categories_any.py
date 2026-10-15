#!/usr/bin/env python3
"""
Benchmark script for SemanticSearchTool with categories_any + FTS.

Measures query performance and EXPLAIN QUERY PLAN before and after adding
the composite index idx_cat_item_cat on item_categories(item_id, category).

Usage:
    python scripts/evaluation/benchmark_categories_any.py --tag <tag> [--queries-file queries.jsonl]
"""

import argparse
import json
import time
from typing import Any

import pandas as pd

from package.config import get_data_paths, get_domains
from package.data.loader import load_item_metadata
from package.tools import ItemCorpus, SemanticSearchTool
from package.tools._limits import SQL_TIME_BUDGET_SECONDS
from package.tools.base import ToolResult


def _check_result(result: ToolResult) -> bool:
    """Return False for an expected SQL timeout; raise for other search failures."""
    if result.ok:
        return True
    if result.error == "query exceeded the time budget":
        return False
    raise RuntimeError(f"SemanticSearchTool failed: {result.error}")


def create_corpus_without_composite_index(meta: pd.DataFrame) -> ItemCorpus:
    """
    Create a corpus WITHOUT the composite index idx_cat_item_cat.
    This is done by temporarily modifying the CATEGORIES_INDEXES list.
    """
    from package.tools.corpus._sql import CATEGORIES_INDEXES

    # Save original indexes
    original_indexes = CATEGORIES_INDEXES.copy()

    # Remove composite index if present
    CATEGORIES_INDEXES[:] = [
        idx for idx in CATEGORIES_INDEXES
        if "idx_cat_item_cat" not in idx
    ]

    try:
        corpus = ItemCorpus.from_dataframe(meta)
    finally:
        # Restore original indexes
        CATEGORIES_INDEXES[:] = original_indexes

    return corpus


def benchmark_query(
    tool: SemanticSearchTool,
    query: str,
    category: str,
    iterations: int = 5,
    limit: int = 100,
) -> dict[str, Any]:
    """Run SemanticSearchTool query multiple times and collect timing information."""
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    # Warm-up run
    result = tool(query=query, filters={"categories_any": [category]}, limit=limit)
    if not _check_result(result):
        return {
            "times": [],
            "median_time": None,
            "median_rows": None,
            "total_matches": None,
            "timed_out": True,
        }

    # Timed runs
    times = []
    row_counts = []
    for _ in range(iterations):
        start = time.monotonic()
        result = tool(query=query, filters={"categories_any": [category]}, limit=limit)
        elapsed = time.monotonic() - start
        if not _check_result(result):
            return {
                "times": times,
                "median_time": None,
                "median_rows": None,
                "total_matches": None,
                "timed_out": True,
            }
        times.append(elapsed)
        row_counts.append(len(result.data["candidates"]))

    times.sort()
    median_time = times[len(times) // 2]
    median_rows = row_counts[len(row_counts) // 2]

    return {
        "times": times,
        "median_time": median_time,
        "median_rows": median_rows,
        "total_matches": result.data["total_matches"],
        "timed_out": False,
    }


def get_query_plan(corpus: ItemCorpus, query: str, category: str) -> list[tuple]:
    """Get EXPLAIN QUERY PLAN for the FTS + categories_any query."""
    match = f'"{query}"'
    where = """EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id
AND c.category IN (?))"""
    sql = (
        f"SELECT items.item_id FROM items_fts "
        f"JOIN items ON items.rowid = items_fts.rowid "
        f"WHERE items_fts MATCH ? AND {where}"
    )
    plan = corpus._conn.execute(f"EXPLAIN QUERY PLAN {sql}", [match, category]).fetchall()
    return plan


def list_indexes(corpus: ItemCorpus) -> list[str]:
    """List all indexes on item_categories."""
    indexes = corpus._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='item_categories'"
    ).fetchall()
    return [idx[0] for idx in indexes]


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark SemanticSearchTool categories_any + FTS queries"
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Data tag (e.g., exp_002, exp_003)"
    )
    parser.add_argument(
        "--queries-file",
        help="Path to JSONL file with queries (one per line: {\"query\": \"...\", \"category\": \"...\"})"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations for timing (default: 5)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Result limit for queries (default: 100)"
    )
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")

    print("="*80)
    print("Benchmark: SemanticSearchTool categories_any + FTS")
    print("="*80)
    print(f"Tag: {args.tag}")

    # Load data paths
    paths = get_data_paths(args.tag)
    meta_files = []
    for domain in get_domains():
        meta_path = paths.meta_path(domain)
        if meta_path.exists():
            meta_files.append((domain, str(meta_path)))
        else:
            print(f"  note: {meta_path} not found; skipping metadata for {domain}")
    if not meta_files:
        raise SystemExit(f"No metadata files found for tag {args.tag!r}")

    # Load metadata
    print("\nLoading metadata from:")
    for domain, meta_path in meta_files:
        print(f"  {domain}: {meta_path}")
    meta = load_item_metadata(meta_files)
    print(f"Loaded {len(meta)} items")

    # Define queries
    if args.queries_file:
        print(f"\nLoading queries from {args.queries_file}...")
        queries = []
        with open(args.queries_file, 'r') as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))
    else:
        # Default queries
        queries = [
            {"query": "keyboard", "category": "Keyboards"},
            {"query": "mouse", "category": "Mice"},
            {"query": "game", "category": "Video_Games"},
        ]
        print(f"\nUsing default queries: {len(queries)}")

    for i, q in enumerate(queries, 1):
        query_text = q["query"]
        category = q["category"]
        print(f"\n{'='*80}")
        print(f"Query {i}/{len(queries)}: query='{query_text}', category='{category}'")
        print(f"{'='*80}")

        # Benchmark WITHOUT composite index
        print("\n--- WITHOUT composite index idx_cat_item_cat ---")
        corpus_without = create_corpus_without_composite_index(meta)
        indexes_without = list_indexes(corpus_without)
        print(f"Indexes on item_categories: {indexes_without}")

        tool_without = SemanticSearchTool(corpus_without)
        plan_without = get_query_plan(corpus_without, query_text, category)
        print("Query plan:")
        for row in plan_without:
            print(f"  {row}")

        print(f"\nRunning {args.iterations} iterations...")
        bench_without = benchmark_query(
            tool_without, query_text, category, args.iterations, args.limit
        )
        if bench_without["timed_out"]:
            print(f"Query exceeded the SQL time budget ({SQL_TIME_BUDGET_SECONDS:.1f}s); stopping this benchmark side.")
        else:
            print(f"Median time: {bench_without['median_time']:.3f}s")
            print(f"Median rows returned: {bench_without['median_rows']}")
            print(f"Total matches: {bench_without['total_matches']}")

        # Benchmark WITH composite index
        print("\n--- WITH composite index idx_cat_item_cat ---")
        corpus_with = ItemCorpus.from_dataframe(meta)
        indexes_with = list_indexes(corpus_with)
        print(f"Indexes on item_categories: {indexes_with}")

        tool_with = SemanticSearchTool(corpus_with)
        plan_with = get_query_plan(corpus_with, query_text, category)
        print("Query plan:")
        for row in plan_with:
            print(f"  {row}")

        print(f"\nRunning {args.iterations} iterations...")
        bench_with = benchmark_query(
            tool_with, query_text, category, args.iterations, args.limit
        )
        if bench_with["timed_out"]:
            print(f"Query exceeded the SQL time budget ({SQL_TIME_BUDGET_SECONDS:.1f}s); stopping this benchmark side.")
        else:
            print(f"Median time: {bench_with['median_time']:.3f}s")
            print(f"Median rows returned: {bench_with['median_rows']}")
            print(f"Total matches: {bench_with['total_matches']}")

        # Summary
        print("\n--- SUMMARY ---")
        if bench_without["median_time"] is None:
            print(f"Without composite index: >{SQL_TIME_BUDGET_SECONDS:.1f}s (timed out)")
        else:
            print(f"Without composite index: {bench_without['median_time']:.3f}s")
        if bench_with["median_time"] is None:
            print(f"With composite index: >{SQL_TIME_BUDGET_SECONDS:.1f}s (timed out)")
        else:
            print(f"With composite index: {bench_with['median_time']:.3f}s")
        if bench_without["median_time"] is not None and bench_with["median_time"] is not None:
            speedup = bench_without["median_time"] / bench_with["median_time"] if bench_with["median_time"] > 0 else 0
            print(f"Speedup: {speedup:.2f}x")
        else:
            print("Speedup: unavailable (one or both benchmark sides timed out)")
        if bench_without["median_rows"] is not None and bench_with["median_rows"] is not None:
            row_consistent = bench_without["median_rows"] == bench_with["median_rows"]
            matches_consistent = bench_without["total_matches"] == bench_with["total_matches"]
            print(f"Row count consistency: {'PASS' if row_consistent else 'FAIL'}")
            print(f"Total matches consistency: {'PASS' if matches_consistent else 'FAIL'}")
        else:
            print("Row count consistency: unavailable (one or both benchmark sides timed out)")
            print("Total matches consistency: unavailable (one or both benchmark sides timed out)")

        # Verify index usage in plan
        index_used = any("idx_cat_item_cat" in str(row) for row in plan_with)
        print(f"Composite index used in plan: {'YES' if index_used else 'NO'}")


if __name__ == "__main__":
    main()
