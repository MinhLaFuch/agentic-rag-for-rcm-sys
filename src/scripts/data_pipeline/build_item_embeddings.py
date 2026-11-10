"""
Build and save dense item embeddings for catalog retrieval.

Reads items from prebuilt ItemCorpus (SQLite) and writes:
  resource/corpus/<tag>/item_embeddings_<tag>.npz

Usage:
    PYTHONPATH=. python scripts/data_pipeline/build_item_embeddings.py --domain Video_Games
    PYTHONPATH=. python scripts/data_pipeline/build_item_embeddings.py  # all domains (multi_domain)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import numpy as np

from package.config import get_data_paths, load_config
from package.embeddings import VectorStore, build_embedding_encoder
from package.utils import ensure_utf8_stdout


def _fetch_items_for_embedding(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Fetch item_id and formatted text description from SQLite database."""
    cur = conn.execute(
        """
        SELECT i.item_id, i.title, i.store, i.main_category,
               COALESCE(GROUP_CONCAT(c.category, ', '), '') AS cats
        FROM items i
        LEFT JOIN item_categories c ON i.item_id = c.item_id
        GROUP BY i.item_id
        ORDER BY i.item_id
        """
    )
    rows = []
    for item_id, title, store, main_cat, cats in cur.fetchall():
        title_str = title or ""
        store_str = f"Store: {store}. " if store else ""
        cat_str = f"Categories: {cats}. " if cats else ""
        main_cat_str = f"Main: {main_cat}. " if main_cat else ""
        text = f"{title_str}. {store_str}{main_cat_str}{cat_str}".strip()
        rows.append((str(item_id), text))
    return rows


def build_embeddings_for_corpus(
    sqlite_path: Path,
    output_npz_path: Path,
    encoder_config: dict | None = None,
    batch_size: int = 256,
) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Corpus SQLite database not found at {sqlite_path}")

    print(f"Loading items from SQLite corpus: {sqlite_path}...")
    conn = sqlite3.connect(sqlite_path)
    try:
        items = _fetch_items_for_embedding(conn)
    finally:
        conn.close()

    total = len(items)
    print(f"Total catalog items to embed: {total}")
    if total == 0:
        print("Corpus is empty. Skipping embedding generation.")
        return

    item_ids = [item[0] for item in items]
    texts = [item[1] for item in items]

    encoder = build_embedding_encoder(encoder_config)
    print(f"Using encoder: {encoder.__class__.__name__} (dimension={encoder.dimension()})")

    start_time = time.time()
    embeddings_list = []
    for i in range(0, total, batch_size):
        chunk = texts[i : i + batch_size]
        vecs = encoder.encode(chunk)
        embeddings_list.append(vecs)
        if (i // batch_size) % 10 == 0 or (i + batch_size >= total):
            processed = min(i + batch_size, total)
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"  Processed {processed}/{total} items ({rate:.1f} items/s)...")

    embeddings = np.vstack(embeddings_list)
    store = VectorStore(item_ids=item_ids, embeddings=embeddings)

    output_npz_path.parent.mkdir(parents=True, exist_ok=True)
    store.save(output_npz_path)
    total_time = time.time() - start_time
    print(f"Done! Saved {len(store)} vectors to {output_npz_path} in {total_time:.2f}s.")


def main() -> None:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Build dense embeddings for item catalog")
    parser.add_argument("--domain", action="append", help="Domain name(s). Default: all domains (multi_domain)")
    parser.add_argument("--provider", default="hash", choices=["hash", "sentence_transformers", "openai_compatible"],
                        help="Embedding provider (default: hash for local test)")
    parser.add_argument("--model", help="Embedding model name (e.g. text-embedding-3-small or sentence-transformers model)")
    args = parser.parse_args()

    paths = get_data_paths(domains=args.domain)
    tag = paths.tag
    corpus_sqlite = paths.corpus_dir / f"corpus_{tag}.sqlite"
    output_npz = paths.corpus_dir / f"item_embeddings_{tag}.npz"

    encoder_config: dict = {"provider": args.provider}
    if args.model:
        encoder_config["model"] = args.model

    build_embeddings_for_corpus(
        sqlite_path=corpus_sqlite,
        output_npz_path=output_npz,
        encoder_config=encoder_config,
    )


if __name__ == "__main__":
    main()

