"""Build a persisted SparseBM25Index (Okapi BM25 term-by-doc CSR) from a corpus SQLite database.

Two-pass streaming over SQLite keeps peak RAM well under 2 GB for 2.64M items.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import time

import numpy as np
from scipy import sparse

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.embeddings.sparse_bm25_index import SparseBM25Index, _sha256_file, _tokenize_doc
from package.utils import ensure_utf8_stdout


def _iter_corpus_docs(conn: sqlite3.Connection, batch_size: int = 20000):
    """Yield (item_id, concatenated_text) in stable item_id order using bounded range scans."""
    last_id = ""
    while True:
        rows = conn.execute(
            "SELECT item_id, title, store, main_category FROM items "
            "WHERE item_id > ? ORDER BY item_id ASC LIMIT ?",
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        ids = [r[0] for r in rows]
        last_id = ids[-1]
        marks = ",".join("?" for _ in ids)
        cat_map: dict[str, list[str]] = {}
        # Query categories in bounded chunks of 500 to stay below SQLite's variable limit.
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            c_marks = ",".join("?" for _ in chunk)
            for iid, cat in conn.execute(
                f"SELECT item_id, category FROM item_categories WHERE item_id IN ({c_marks})",
                chunk,
            ):
                if cat:
                    cat_map.setdefault(iid, []).append(str(cat))
        for iid, title, store, main_cat in rows:
            parts = [p for p in (title, store, main_cat) if p]
            cats = cat_map.get(iid)
            if cats:
                parts.extend(cats)
            yield str(iid), " ".join(parts)


def build_sparse_bm25_from_sqlite(
    corpus_path: Path,
    output_dir: Path,
    *,
    tag: str,
    k1: float = 1.2,
    b: float = 0.75,
    min_df: int = 2,
    max_doc_tokens: int = 128,
    batch_size: int = 20000,
) -> dict:
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus SQLite not found: {corpus_path}")
    t0 = time.perf_counter()
    print(f"[bm25-build] hashing corpus: {corpus_path}", flush=True)
    corpus_sha = _sha256_file(corpus_path)
    conn = sqlite3.connect(f"file:{corpus_path.resolve()}?mode=ro", uri=True)
    try:
        total_items = int(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])
        print(f"[bm25-build] pass 1/2: scanning {total_items:,} items for vocab/df/doc_len", flush=True)
        df_counter: Counter[str] = Counter()
        item_ids: list[str] = []
        doc_lens = np.empty(total_items, dtype=np.int32)
        seen_docs = 0
        for iid, text in _iter_corpus_docs(conn, batch_size=batch_size):
            toks = _tokenize_doc(text, cap=max_doc_tokens)
            item_ids.append(iid)
            doc_lens[seen_docs] = len(toks)
            if toks:
                for term in set(toks):
                    df_counter[term] += 1
            seen_docs += 1
            if seen_docs % 250_000 == 0:
                print(f"  pass 1: {seen_docs:,}/{total_items:,} ({time.perf_counter()-t0:.1f}s)", flush=True)
        if seen_docs != total_items:
            doc_lens = doc_lens[:seen_docs]
            total_items = seen_docs

        kept_terms = sorted(term for term, c in df_counter.items() if c >= min_df)
        vocab = {term: idx for idx, term in enumerate(kept_terms)}
        df_arr = np.array([df_counter[t] for t in kept_terms], dtype=np.float64)
        idf = np.log1p((total_items - df_arr + 0.5) / (df_arr + 0.5)).astype(np.float32)
        nnz = int(sum(df_counter[t] for t in kept_terms))
        avgdl = float(doc_lens.mean()) if total_items else 1.0
        if avgdl <= 0.0:
            avgdl = 1.0
        del df_counter
        print(
            f"[bm25-build] vocab={len(vocab):,} (min_df={min_df}), nnz={nnz:,}, avgdl={avgdl:.1f} "
            f"({time.perf_counter()-t0:.1f}s)",
            flush=True,
        )

        # Build directly in CSR by counting per-term offsets from df_arr (zero COO sorting memory!).
        indptr = np.zeros(len(vocab) + 1, dtype=np.int64)
        np.cumsum(df_arr.astype(np.int64), out=indptr[1:])
        write_ptr = indptr[:-1].copy()
        indices = np.empty(nnz, dtype=np.int32)
        data = np.empty(nnz, dtype=np.float32)

        print(f"[bm25-build] pass 2/2: populating term-by-doc CSR ({nnz:,} entries)", flush=True)
        t1 = time.perf_counter()
        doc_idx = 0
        for iid, text in _iter_corpus_docs(conn, batch_size=batch_size):
            toks = _tokenize_doc(text, cap=max_doc_tokens)
            if toks:
                dl_norm = k1 * (1.0 - b + b * (float(doc_lens[doc_idx]) / avgdl))
                counts = Counter(toks)
                for term, tf in counts.items():
                    tid = vocab.get(term)
                    if tid is None:
                        continue
                    slot = int(write_ptr[tid])
                    indices[slot] = doc_idx
                    data[slot] = float(idf[tid]) * (tf * (k1 + 1.0)) / (tf + dl_norm)
                    write_ptr[tid] = slot + 1
            doc_idx += 1
            if doc_idx % 250_000 == 0:
                print(f"  pass 2: {doc_idx:,}/{total_items:,} ({time.perf_counter()-t1:.1f}s)", flush=True)

        if not np.array_equal(write_ptr, indptr[1:]):
            raise RuntimeError("CSR pointer mismatch after pass 2")

        # Since doc_idx increases monotonically, every row's column indices are already sorted!
        mat = sparse.csr_matrix((data, indices, indptr), shape=(len(vocab), total_items), dtype=np.float32)
        mat.has_sorted_indices = True
        index = SparseBM25Index(item_ids, vocab, mat, k1=k1, b=b)
        build_seconds = time.perf_counter() - t0
        print(f"[bm25-build] saving to {output_dir} ...", flush=True)
        manifest = index.save(
            output_dir,
            metadata={
                "tag": tag,
                "corpus_path": str(corpus_path.resolve()),
                "corpus_sha256": corpus_sha,
                "min_df": min_df,
                "max_doc_tokens": max_doc_tokens,
                "avgdl": avgdl,
                "build_seconds": build_seconds,
            },
        )
        print(f"[bm25-build] complete in {build_seconds:.1f}s -> {output_dir}", flush=True)
        return manifest
    finally:
        conn.close()


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True, help="Bundle tag (e.g. multi_domain_v2_audit_20261030)")
    ap.add_argument("--output", type=Path, required=True, help="Output directory for persisted SparseBM25Index")
    ap.add_argument("--min-df", type=int, default=2, help="Minimum document frequency per term (default: 2)")
    ap.add_argument("--max-doc-tokens", type=int, default=128, help="Max tokens indexed per item (default: 128)")
    ap.add_argument("--k1", type=float, default=1.2)
    ap.add_argument("--b", type=float, default=0.75)
    args = ap.parse_args()
    paths = resolve_bundle_paths(tag=args.tag)
    build_sparse_bm25_from_sqlite(
        paths.corpus_path,
        args.output,
        tag=paths.tag,
        k1=args.k1,
        b=args.b,
        min_df=args.min_df,
        max_doc_tokens=args.max_doc_tokens,
    )


if __name__ == "__main__":
    main()
