"""Multi-signal Learning-to-Rank CandidateScorer combining retrieval ranks, CF, popularity, and domain/category affinity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pickle
from typing import Any, Mapping, Sequence

import numpy as np

from .baseline_scorer import BaselineScorer

FEATURE_NAMES = (
    "rrf_popularity",
    "rrf_domain_cat_pop",
    "rrf_item_cf",
    "rrf_bm25",
    "rrf_dense",
    "rrf_fused_score",
    "source_hit_count",
    "cf_sim_raw",
    "cf_sim_user_norm",
    "fit_pop_norm",
    "log_fit_pop",
    "log_user_history_len",
    "is_cold_user",
    "same_domain_as_history",
    "domain_affinity_ratio",
    "cat_affinity_ratio",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class MultiSignalReranker(BaselineScorer):
    """Request-scoped or reusable LTR CandidateScorer backed by an sklearn classifier/ranker.

    When called through RankTool.score(user_idx, item_idxs), it builds the 16-feature matrix
    from the underlying ItemKNN model, optional request-scoped retrieval source ranks, and
    optional item domain/category affinity tables.
    """

    def __init__(
        self,
        model: Any,
        estimator: Any,
        *,
        id2item: Mapping[int, str] | None = None,
        source_attribution: Mapping[str, dict[str, Any]] | None = None,
        domain_pop: Any | None = None,
        seen_items_for_user: Sequence[str] | None = None,
        rrf_k: float = 60.0,
        name: str = "multi_signal_ltr",
    ) -> None:
        if isinstance(model, BaselineScorer):
            self.__dict__.update(model.__dict__)
            self.popularity_weight = 0.0
        else:
            super().__init__(model, popularity_weight=0.0)
        counts = np.asarray(self.user_items.sum(axis=0)).ravel().astype(np.float64)
        peak = float(counts.max()) if len(counts) else 0.0
        self._fit_pop_norm = counts / peak if peak > 0.0 else counts
        self._log_fit_pop = np.log1p(counts)
        self.estimator = estimator
        self.id2item = id2item or {}
        self.source_attribution = source_attribution or {}
        self.domain_pop = domain_pop
        self.seen_items_for_user = list(seen_items_for_user or [])
        self.rrf_k = float(rrf_k)
        self.name = name

    def for_request(
        self,
        source_attribution: Mapping[str, dict[str, Any]] | None = None,
        seen_items: Sequence[str] | None = None,
    ) -> "MultiSignalReranker":
        """Return a lightweight request-scoped view reusing immutable model & estimator arrays."""
        clone = object.__new__(MultiSignalReranker)
        clone.__dict__.update(self.__dict__)
        clone.source_attribution = source_attribution or {}
        clone.seen_items_for_user = list(seen_items or [])
        return clone

    def extract_features(self, user_idx: int, item_idxs: np.ndarray) -> np.ndarray:
        indices = np.asarray(item_idxs, dtype=np.int64)
        n = len(indices)
        feats = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float32)
        if n == 0:
            return feats
        valid = (indices >= 0) & (indices < self.num_items)
        safe = np.where(valid, indices, 0)

        known = self.is_known_user(user_idx)
        hist_len = int(self.user_items.getrow(user_idx).nnz) if known else len(self.seen_items_for_user)
        cf_raw = np.zeros(n, dtype=np.float64)
        cf_norm = np.zeros(n, dtype=np.float64)
        if self.similarity is not None and known:
            row = (self.user_items.getrow(user_idx) @ self.similarity).tocsr()
            peak = float(row.data.max()) if row.nnz else 0.0
            cf_raw[valid] = row[:, safe[valid]].toarray().ravel().astype(np.float64)
            if peak > 0.0:
                cf_norm[valid] = cf_raw[valid] / peak

        item_names = [self.id2item.get(int(i), "") for i in indices]
        if self.domain_pop is not None and self.seen_items_for_user:
            same_dom, dom_aff, cat_aff = self.domain_pop.affinity_features(self.seen_items_for_user, item_names)
        else:
            z = np.zeros(n, dtype=np.float32)
            same_dom, dom_aff, cat_aff = z, z, z

        k = self.rrf_k
        log_h = float(np.log1p(hist_len))
        is_cold = float(hist_len == 0)
        for j in range(n):
            if not valid[j]:
                continue
            idx = int(indices[j])
            info = self.source_attribution.get(item_names[j]) if item_names[j] else None
            sr = (info.get("source_ranks") or {}) if info else {}
            feats[j, 0] = 1.0 / (k + sr["popularity"]) if "popularity" in sr else 0.0
            feats[j, 1] = 1.0 / (k + sr["domain_cat_pop"]) if "domain_cat_pop" in sr else 0.0
            feats[j, 2] = 1.0 / (k + sr["item_cf"]) if "item_cf" in sr else 0.0
            feats[j, 3] = 1.0 / (k + sr["bm25"]) if "bm25" in sr else 0.0
            feats[j, 4] = 1.0 / (k + sr["dense"]) if "dense" in sr else 0.0
            feats[j, 5] = float(info.get("score", 0.0)) if info else 0.0
            feats[j, 6] = float(len(sr))
            feats[j, 7] = float(cf_raw[j])
            feats[j, 8] = float(cf_norm[j])
            feats[j, 9] = float(self._fit_pop_norm[idx])
            feats[j, 10] = float(self._log_fit_pop[idx])
            feats[j, 11] = log_h
            feats[j, 12] = is_cold
            feats[j, 13] = float(same_dom[j])
            feats[j, 14] = float(dom_aff[j])
            feats[j, 15] = float(cat_aff[j])
        return feats

    def score(self, user_idx: int, item_idxs: np.ndarray) -> np.ndarray:
        indices = np.asarray(item_idxs, dtype=np.int64)
        if len(indices) == 0:
            return np.empty(0, dtype=np.float64)
        feats = self.extract_features(user_idx, indices)
        if hasattr(self.estimator, "predict_proba"):
            probs = self.estimator.predict_proba(feats)
            scores = np.asarray(probs[:, 1] if probs.ndim == 2 and probs.shape[1] > 1 else probs.ravel(), dtype=np.float64)
        else:
            scores = np.asarray(self.estimator.predict(feats), dtype=np.float64).ravel()
        valid = (indices >= 0) & (indices < self.num_items)
        scores = np.where(valid, scores, 0.0)
        if scores.shape != indices.shape or not np.all(np.isfinite(scores)):
            raise RuntimeError("MultiSignalReranker produced invalid scores")
        return scores

    @staticmethod
    def save_estimator(estimator: Any, output_dir: Path | str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        model_path = out / "reranker.pkl"
        with model_path.open("wb") as f:
            pickle.dump(estimator, f)
        manifest = {
            "format": "multi_signal_reranker_v1",
            "status": "complete",
            "feature_names": list(FEATURE_NAMES),
            "estimator_type": type(estimator).__name__,
            **(metadata or {}),
            "checksums": {"reranker.pkl": _sha256_file(model_path)},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    @staticmethod
    def load_estimator(artifact_dir: Path | str, *, verify_checksum: bool = True) -> tuple[Any, dict[str, Any]]:
        root = Path(artifact_dir)
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Reranker artifact missing manifest.json: {root}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete" or manifest.get("format") != "multi_signal_reranker_v1":
            raise ValueError(f"Invalid reranker manifest: {root}")
        if list(manifest.get("feature_names", [])) != list(FEATURE_NAMES):
            raise ValueError("Reranker feature_names mismatch")
        model_path = root / "reranker.pkl"
        if verify_checksum and _sha256_file(model_path) != manifest["checksums"]["reranker.pkl"]:
            raise ValueError("Reranker artifact checksum mismatch")
        with model_path.open("rb") as f:
            est = pickle.load(f)
        return est, manifest
