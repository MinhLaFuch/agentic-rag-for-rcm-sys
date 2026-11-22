"""In-memory Okapi BM25 sparse term-by-document index for sub-100ms filtered lexical retrieval."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Sequence
import unicodedata

import numpy as np
from scipy import sparse

_STOPWORDS = frozenset(
    "a an the for with and or of to in on at by from is are be i me my we our you your "
    "want need looking find get some any good best cheap new under over below".split()
)
_TOKEN_RE = re.compile(r"[\w-][\w-]*")
_MAX_DOC_TOKENS = 256
_MIN_DF = 1


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tokenize_doc(text: str, *, cap: int = _MAX_DOC_TOKENS) -> list[str]:
    if not text:
        return []
    normalized = unicodedata.normalize("NFKD", text.lower())
    out: list[str] = []
    for w in _TOKEN_RE.findall(normalized):
        if len(w) > 1 and w not in _STOPWORDS and not w.replace("-", "").isdigit():
            out.append(w)
            if len(out) >= cap:
                break
    return out


def _tokenize_query(query: str, *, max_tokens: int = 20) -> list[str]:
    if not query:
        return []
    normalized = unicodedata.normalize("NFKD", query.lower())
    kept = [
        w for w in _TOKEN_RE.findall(normalized)
        if len(w) > 1 and w not in _STOPWORDS and not w.replace("-", "").isdigit()
    ]
    return list(dict.fromkeys(kept))[:max_tokens]


class SparseBM25Index:
    """Precomputed Okapi BM25 term-by-doc CSR matrix with exact pre-Top-K eligibility & seen filtering."""

    def __init__(
        self,
        item_ids: Sequence[str],
        vocab: dict[str, int],
        term_doc_csr: sparse.csr_matrix,
        *,
        k1: float = 1.2,
        b: float = 0.75,
        manifest: dict[str, Any] | None = None,
    ) -> None:
        ids = np.asarray(item_ids, dtype=object)
        if ids.ndim != 1 or len(ids) == 0:
            raise ValueError("item_ids must be a non-empty 1D sequence")
        if term_doc_csr.shape != (len(vocab), len(ids)):
            raise ValueError(
                f"term_doc_csr shape {term_doc_csr.shape} does not match (vocab={len(vocab)}, items={len(ids)})"
            )
        self.item_ids = ids
        self.id_to_pos = {str(item_id): idx for idx, item_id in enumerate(ids)}
        self.vocab = vocab
        self.matrix = term_doc_csr.tocsr()
        if self.matrix.dtype != np.float32:
            self.matrix = self.matrix.astype(np.float32)
        self.k1 = float(k1)
        self.b = float(b)
        self.manifest = dict(manifest or {})
        self._query_row_cache: dict[str, int | None] = {}

    def __len__(self) -> int:
        return int(len(self.item_ids))

    @classmethod
    def build_from_documents(
        cls,
        item_ids: Sequence[str],
        documents: Iterable[str],
        *,
        k1: float = 1.2,
        b: float = 0.75,
        min_df: int = _MIN_DF,
        max_doc_tokens: int = _MAX_DOC_TOKENS,
    ) -> "SparseBM25Index":
        ids = [str(i) for i in item_ids]
        n_docs = len(ids)
        if n_docs == 0:
            raise ValueError("Cannot build SparseBM25Index from empty catalog")
        if len(set(ids)) != n_docs:
            raise ValueError("item_ids must be unique")

        vocab: dict[str, int] = {}
        df = Counter()
        doc_lens = np.zeros(n_docs, dtype=np.int32)
        doc_term_lists: list[list[tuple[int, int]]] = []

        for doc_idx, text in enumerate(documents):
            toks = _tokenize_doc(text, cap=max_doc_tokens)
            doc_lens[doc_idx] = len(toks)
            if not toks:
                doc_term_lists.append([])
                continue
            counts = Counter(toks)
            pairs: list[tuple[int, int]] = []
            for term, tf in counts.items():
                tid = vocab.get(term)
                if tid is None:
                    tid = len(vocab)
                    vocab[term] = tid
                df[tid] += 1
                pairs.append((tid, tf))
            doc_term_lists.append(pairs)

        if min_df > 1:
            keep_old = {tid for tid, c in df.items() if c >= min_df}
            old_to_new: dict[int, int] = {}
            new_vocab: dict[str, int] = {}
            for term, old_id in vocab.items():
                if old_id in keep_old:
                    new_id = len(new_vocab)
                    new_vocab[term] = new_id
                    old_to_new[old_id] = new_id
            new_df = np.zeros(len(new_vocab), dtype=np.int32)
            for old_id, new_id in old_to_new.items():
                new_df[new_id] = df[old_id]
            vocab = new_vocab
        else:
            old_to_new = None
            new_df = np.zeros(len(vocab), dtype=np.int32)
            for tid, c in df.items():
                new_df[tid] = c

        if not vocab:
            raise ValueError("No indexable tokens found in documents")

        avgdl = float(doc_lens.mean()) if n_docs else 1.0
        if avgdl <= 0.0:
            avgdl = 1.0
        # Standard Lucene/Okapi IDF >= 0: ln(1 + (N - df + 0.5) / (df + 0.5))
        idf = np.log1p((n_docs - new_df.astype(np.float64) + 0.5) / (new_df.astype(np.float64) + 0.5)).astype(np.float32)

        nnz = sum(
            sum(1 for tid, _ in pairs if old_to_new is None or tid in old_to_new)
            for pairs in doc_term_lists
        )
        rows = np.empty(nnz, dtype=np.int32)
        cols = np.empty(nnz, dtype=np.int32)
        data = np.empty(nnz, dtype=np.float32)

        pos = 0
        k1_f = float(k1)
        b_f = float(b)
        for doc_idx, pairs in enumerate(doc_term_lists):
            if not pairs:
                continue
            dl_norm = k1_f * (1.0 - b_f + b_f * (float(doc_lens[doc_idx]) / avgdl))
            for tid, tf in pairs:
                if old_to_new is not None:
                    ntid = old_to_new.get(tid)
                    if ntid is None:
                        continue
                    tid = ntid
                score = float(idf[tid]) * (tf * (k1_f + 1.0)) / (tf + dl_norm)
                rows[pos] = tid
                cols[pos] = doc_idx
                data[pos] = score
                pos += 1

        mat = sparse.coo_matrix((data[:pos], (rows[:pos], cols[:pos])), shape=(len(vocab), n_docs), dtype=np.float32).tocsr()
        return cls(ids, vocab, mat, k1=k1_f, b=b_f)

    def save(self, output_dir: Path | str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        mat_path = out / "term_doc_csr.npz"
        ids_path = out / "item_ids.json"
        vocab_path = out / "vocab.json"
        manifest_path = out / "manifest.json"

        sparse.save_npz(mat_path, self.matrix, compressed=False)
        ids_path.write_text(json.dumps(self.item_ids.tolist()), encoding="utf-8")
        vocab_path.write_text(json.dumps(self.vocab), encoding="utf-8")

        manifest = {
            "format": "sparse_bm25_csr_v1",
            "status": "complete",
            "num_items": int(len(self.item_ids)),
            "vocab_size": int(len(self.vocab)),
            "nnz": int(self.matrix.nnz),
            "k1": self.k1,
            "b": self.b,
            **(metadata or {}),
            "checksums": {
                "term_doc_csr.npz": _sha256_file(mat_path),
                "item_ids.json": _sha256_file(ids_path),
                "vocab.json": _sha256_file(vocab_path),
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.manifest = manifest
        return manifest

    @classmethod
    def load(
        cls,
        artifact_dir: Path | str,
        *,
        expected_corpus_sha256: str | None = None,
        verify_checksums: bool = True,
    ) -> "SparseBM25Index":
        root = Path(artifact_dir)
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"SparseBM25Index missing manifest.json: {root}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete" or manifest.get("format") != "sparse_bm25_csr_v1":
            raise ValueError(f"Invalid SparseBM25Index manifest: {root}")
        if expected_corpus_sha256 is not None and manifest.get("corpus_sha256") != expected_corpus_sha256:
            raise ValueError("SparseBM25Index corpus_sha256 mismatch")
        if verify_checksums:
            for name, expected in manifest.get("checksums", {}).items():
                if _sha256_file(root / name) != expected:
                    raise ValueError(f"SparseBM25Index checksum mismatch: {name}")
        item_ids = json.loads((root / "item_ids.json").read_text(encoding="utf-8"))
        vocab = json.loads((root / "vocab.json").read_text(encoding="utf-8"))
        mat = sparse.load_npz(root / "term_doc_csr.npz").tocsr()
        return cls(item_ids, vocab, mat, k1=manifest.get("k1", 1.2), b=manifest.get("b", 0.75), manifest=manifest)

    def eligible_mask(self, eligible_ids: Iterable[str]) -> np.ndarray:
        mask = np.zeros(len(self.item_ids), dtype=bool)
        for item_id in eligible_ids:
            pos = self.id_to_pos.get(str(item_id))
            if pos is not None:
                mask[pos] = True
        return mask

    def search_with_scores(
        self,
        query: str,
        *,
        valid_mask: np.ndarray | None = None,
        seen: Iterable[str] | None = None,
        limit: int = 200,
        max_tokens: int = 20,
    ) -> list[tuple[str, float]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        tokens = _tokenize_query(query, max_tokens=max_tokens)
        term_ids = [self.vocab[t] for t in tokens if t in self.vocab]
        if not term_ids:
            return []

        sub = self.matrix[term_ids]
        if sub.nnz == 0:
            return []

        if len(term_ids) == 1:
            cols = sub.indices
            vals = sub.data
        else:
            # Sparse row-sum via (1 x k) @ (k x N) avoids allocating a full dense N-vector on small queries.
            q = sparse.csr_matrix(np.ones((1, len(term_ids)), dtype=np.float32))
            summed = q @ sub
            cols = summed.indices
            vals = summed.data

        if len(cols) == 0:
            return []

        if valid_mask is not None:
            keep = valid_mask[cols]
            if not np.any(keep):
                return []
            cols = cols[keep]
            vals = vals[keep]

        if seen:
            seen_pos = {self.id_to_pos[s] for s in seen if s in self.id_to_pos}
            if seen_pos:
                keep = np.fromiter((int(c) not in seen_pos for c in cols), dtype=bool, count=len(cols))
                if not np.any(keep):
                    return []
                cols = cols[keep]
                vals = vals[keep]

        if len(vals) > limit:
            # Keep a small tie buffer around the cutoff so deterministic item_id tie-breaks stay exact.
            kth = float(np.partition(-vals, limit - 1)[limit - 1])
            cutoff_score = -kth
            keep = vals >= cutoff_score
            if int(keep.sum()) <= limit * 4:
                cols = cols[keep]
                vals = vals[keep]
            else:
                strict = vals > cutoff_score
                strict_cols, strict_vals = cols[strict], vals[strict]
                tie_cols = cols[vals == cutoff_score]
                need = limit - len(strict_cols)
                if need > 0 and len(tie_cols) > 0:
                    tie_ids = self.item_ids[tie_cols]
                    pick_tie = np.argsort(tie_ids)[:need]
                    cols = np.concatenate((strict_cols, tie_cols[pick_tie]))
                    vals = np.concatenate((strict_vals, np.full(len(pick_tie), cutoff_score, dtype=np.float32)))
                else:
                    cols, vals = strict_cols, strict_vals

        cand_ids = self.item_ids[cols]
        order = np.lexsort((cand_ids, -vals))[:limit]
        return [(str(cand_ids[i]), float(vals[i])) for i in order]

    def search(
        self,
        query: str,
        *,
        valid_mask: np.ndarray | None = None,
        seen: Iterable[str] | None = None,
        limit: int = 200,
        max_tokens: int = 20,
    ) -> list[str]:
        return [
            item_id for item_id, _ in self.search_with_scores(
                query, valid_mask=valid_mask, seen=seen, limit=limit, max_tokens=max_tokens
            )
        ]
