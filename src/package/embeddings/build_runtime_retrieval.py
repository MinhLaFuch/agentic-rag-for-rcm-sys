"""Shared retrieval initialization for live serving and agent evaluation."""
from pathlib import Path
from typing import Any


def build_runtime_retrieval(config: dict[str, Any], dense_cfg: dict[str, Any], *,
                            corpus_path: Path, default_embeddings: Path):
    """Return SearchTool keyword arguments and the actually activated provenance.

    Explicit runtime artifacts take precedence over the semantic-artifact loader.
    Evaluation supplies fallback_to_bm25=False to fail on invalid requested artifacts.
    """
    src_root = Path(__file__).resolve().parents[2]
    repo_root = src_root.parent

    def resolve_path(raw):
        path = Path(raw)
        return path if path.is_absolute() else repo_root / path

    retrieval_mode = str(config.get("retrieval_mode", "bm25"))
    if retrieval_mode not in {"bm25", "hybrid"}:
        raise ValueError(f"Unknown retrieval mode: {retrieval_mode}")
    fallback_to_bm25 = bool(config.get("fallback_to_bm25", True))
    translate_vietnamese = bool(config.get("translate_vietnamese", True))
    vector_store = None
    query_encoder = None
    dense_search = None
    bm25_index = None
    bm25_raw = config.get("bm25_index_path")
    if bm25_raw:
        try:
            from package.embeddings import SparseBM25Index
            bm25_index = SparseBM25Index.load(resolve_path(bm25_raw))
            print(f"[runtime bm25] active=sparse_bm25 ({len(bm25_index):,} items)")
        except Exception as exc:
            if not fallback_to_bm25:
                raise RuntimeError(f"SparseBM25Index load failed: {exc}") from exc
            print(f"[runtime bm25] fallback=sqlite_fts5 reason={type(exc).__name__}: {exc}")
    if retrieval_mode == "hybrid" or dense_cfg.get("enabled"):
        emb_raw = config.get("embeddings_path")
        emb_path = resolve_path(emb_raw) if emb_raw else (default_embeddings)
        try:
            if config.get("embeddings_path") or not dense_cfg.get("enabled"):
                from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
                from package.embeddings import TextEncoder
                vector_store, encoder_impl, emb_prov = load_validated_embeddings(emb_path, corpus_path)
                query_encoder = TextEncoder(encoder_impl.encode, dimension=vector_store.dimension)
            else:
                from .build_dense_retrieval import build_dense_retrieval
                if not dense_cfg.get("artifacts_dir") or not dense_cfg.get("encoder_lock"):
                    raise ValueError("enabled dense retrieval requires artifacts_dir and encoder_lock")
                vector_store, query_encoder, emb_prov = build_dense_retrieval(
                    src_root / dense_cfg["artifacts_dir"], src_root / dense_cfg["encoder_lock"],
                    rrf_k=int(dense_cfg.get("rrf_k", 60)),
                )
            ann_raw = config.get("ann_index_path")
            if ann_raw:
                from scripts.evaluation.ann_validation import build_ann_search
                import numpy as np
                ann_fn = build_ann_search(vector_store, {
                    "index": "hnsw_sq8", "m": 32, "ef_search": 1024, "warmup_queries": 100,
                    "index_path": str(resolve_path(ann_raw)),
                    "expected_embedding_build_id": emb_prov.get("build_id"),
                })
                all_valid = np.ones(len(vector_store.item_ids), dtype=bool)
                dense_search = lambda vec, k, _fn=ann_fn, _v=all_valid: _fn(vec, _v, set(), k)
            provenance = {
                "requested": "hybrid",
                "active": "hybrid",
                "dense_backend": "ann" if dense_search is not None else "exact",
                "bm25_backend": "sparse_bm25" if bm25_index is not None else "sqlite_fts5",
                "fallback_to_bm25": fallback_to_bm25,
                "embeddings_path": str(emb_path),
                "provider": emb_prov.get("provider"),
                "model_name": emb_prov.get("model_name"),
                "build_id": emb_prov.get("build_id"),
            }
            print(f"[runtime retrieval] active=hybrid dense={provenance['dense_backend']} bm25={provenance['bm25_backend']} ({len(vector_store):,} vectors)")
        except Exception as exc:
            if not fallback_to_bm25:
                raise RuntimeError(f"Hybrid retrieval initialization failed (fallback disabled): {exc}") from exc
            vector_store = None
            query_encoder = None
            dense_search = None
            provenance = {
                "requested": "hybrid",
                "active": "bm25_fallback",
                "fallback_to_bm25": True,
                "embeddings_path": str(emb_path),
                "reason": f"{type(exc).__name__}: {exc}",
            }
            print(f"[runtime retrieval] fallback=bm25_fallback reason={type(exc).__name__}: {exc}")
    else:
        provenance = {"requested": "bm25", "active": "bm25", "fallback_to_bm25": fallback_to_bm25}
        print("[runtime retrieval] active=bm25")
    provenance["bm25_backend"] = "sparse_bm25" if bm25_index is not None else "sqlite_fts5"
    provenance["translate_vietnamese"] = translate_vietnamese
    return {
        "vector_store": vector_store, "query_encoder": query_encoder,
        "dense_search": dense_search, "bm25_index": bm25_index,
        "fallback_to_bm25": fallback_to_bm25,
        "translate_vietnamese": translate_vietnamese,
        "rrf_k": int(dense_cfg.get("rrf_k", 60)),
    }, provenance
