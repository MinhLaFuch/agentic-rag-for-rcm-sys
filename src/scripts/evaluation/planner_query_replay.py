"""Replay the retrieval calls a planner actually made and measure target recall.

For every ok SearchTool/FilterTool/SimilarTool step in a run's trajectories.jsonl,
this script re-executes the SAME recorded args offline (same corpus, same
first_seen metadata policy, same dense artifacts, same ItemKNN core model) and
then re-executes with larger candidate budgets. It answers:

  - fidelity:    does offline replay reproduce the candidates the run logged?
  - recorded:    did the target appear in the candidates the planner actually saw?
  - extended:    would a bigger limit/top_k have surfaced the target, and at which rank?

"target in extended but not recorded" = loss caused by the candidate budget cutoff,
not by query formulation or the retriever itself.

Usage (from src/):
    python scripts/evaluation/planner_query_replay.py <run_dir> [<run_dir> ...]
    # run_dir = experiments/agent_eval/campaigns/<campaign>/<exp>/run_<N>
    # options: --budgets 200,500  --max-requests N  --no-extended  --output report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from package.config import get_data_paths, load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.corpus import load_corpus
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.data.mapping import load_mappings
from package.data.pipeline import build_meta_files
from package.embeddings.build_dense_retrieval import build_dense_retrieval
from package.recommenders.shared.load_item_knn import load_item_knn
from package.tools import FilterTool, SearchTool, SimilarTool
from package.tools.base import ToolCallLogger

RETRIEVAL_TOOLS = ("SearchTool", "FilterTool", "SimilarTool")
BUDGET_ARG = {"SearchTool": "limit", "FilterTool": "limit", "SimilarTool": "top_k"}


# ----------------------------------------------------------------------------- io


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _find_key(d: dict, key: str):
    """Depth-first search for a config key (config.yaml nests policies differently per version)."""
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    for v in d.values():
        found = _find_key(v, key)
        if found is not None:
            return found
    return None


# ----------------------------------------------------------------------------- shared resources


class ReplayResources:
    """Corpus + tools + ItemKNN similarity, loaded once and shared across run dirs."""

    def __init__(self, budgets: list[int], use_dense: bool = True):
        self.budgets = sorted(budgets)
        self.data_paths = resolve_bundle_paths()
        cfg = load_config("agent/agent_eval")["agent_eval"]
        self.min_coverage = float(cfg["min_metadata_coverage"])
        self.allow_missing = bool(cfg.get("allow_missing_corpus_sources", True))

        # item2id only (user2id is ~1 GB and unneeded: we skip the user_items matrix)
        with open(self.data_paths.mapped_dir / "item2id.json", encoding="utf-8") as f:
            self.item2id = json.load(f)
        self.id2item = {v: k for k, v in self.item2id.items()}
        self._corpus_cache: dict[tuple, object] = {}
        self._tool_cache: dict[tuple, object] = {}

        # dense retrieval leg (same artifacts the eval used)
        self.vector_store = self.query_encoder = None
        self.rrf_k = 60
        dense_cfg = load_config("eval/dense_retrieval")["dense_retrieval"]
        if use_dense and dense_cfg.get("enabled"):
            src_root = Path(__file__).resolve().parents[2]
            self.vector_store, self.query_encoder, prov = build_dense_retrieval(
                src_root / dense_cfg["artifacts_dir"],
                src_root / dense_cfg["encoder_lock"],
                rrf_k=int(dense_cfg.get("rrf_k", 60)),
            )
            self.rrf_k = int(dense_cfg.get("rrf_k", 60))
            print(f"  dense retrieval: {prov['valid_rows']}/{prov['rows']} items", flush=True)

        self._knn_model = None  # lazy: only needed if a run has SimilarTool steps

    # ---- corpus per (policy, as_of); apply_metadata_policy is one-shot per corpus object
    def corpus_for(self, policy: str, as_of: int):
        key = (policy, as_of)
        if key not in self._corpus_cache:
            meta_files = build_meta_files(self.data_paths)
            corpus, _ = load_corpus(
                self.data_paths.corpus_path, meta_files, self.item2id,
                self.min_coverage, allow_missing_sources=self.allow_missing,
            )
            apply_metadata_policy(corpus, policy, as_of_timestamp=as_of)
            self._corpus_cache[key] = corpus
            print(f"  corpus ready (policy={policy}, as_of={as_of})", flush=True)
        return self._corpus_cache[key]

    def tool_for(self, name: str, corpus):
        """Lazily build one tool; SimilarTool triggers the (expensive) KNN load only when needed."""
        key = (name, id(corpus))
        if key not in self._tool_cache:
            if name == "SearchTool":
                tool = SearchTool(
                    corpus, logger=ToolCallLogger(),
                    vector_store=self.vector_store, query_encoder=self.query_encoder,
                    rrf_k=self.rrf_k,
                )
            elif name == "FilterTool":
                tool = FilterTool(corpus, logger=ToolCallLogger())
            elif name == "SimilarTool":
                tool = SimilarTool(self._similarity_model(corpus), self.item2id,
                                   corpus=corpus, logger=ToolCallLogger())
            else:
                raise KeyError(name)
            self._tool_cache[key] = tool
        return self._tool_cache[key]

    def _similarity_model(self, corpus):
        """ItemKNN core model with similarity remapped to the global item2id space.

        Mirrors build_core_model's remap but skips the user_items interaction
        matrix (only needed by RankTool, not by SimilarTool).
        """
        if self._knn_model is not None:
            return self._knn_model

        paths = self.data_paths
        manifest = paths.splits_dir / "stage_3.manifest.json"
        proto = json.loads(manifest.read_text(encoding="utf-8")).get("flags", {}).get("data_protocol")
        if proto != "temporal_train_core":
            raise RuntimeError(f"unexpected data_protocol {proto!r}; SimilarTool replay needs temporal_train_core")

        users, items = load_mappings(paths.mapped_dir / "fit_core")
        pairs = pd.read_parquet(paths.splits_dir / "train_core.parquet",
                                columns=["user_idx", "item_idx"])
        k = int(load_config("eval/baselines")["baselines"]["item_knn"]["k"])
        cache = paths.item_knn_path("validation")
        model = load_item_knn(cache, k, pairs, user2id=users, item2id=items,
                              eval_on="validation", tag=paths.tag, fit_splits=["train_core"])

        # core-space -> global item2id remap (same as build_core_model)
        item_indices = np.empty(len(items), dtype=np.int64)
        for key, index in items.items():
            item_indices[index] = self.item2id[key]
        coo = model.similarity.tocoo()
        model.similarity = sparse.csr_matrix(
            (coo.data, (item_indices[coo.row], item_indices[coo.col])),
            shape=(len(self.item2id), len(self.item2id)))

        class _M:  # minimal shim: SimilarTool only reads .similarity
            pass
        self._knn_model = _M()
        self._knn_model.similarity = model.similarity
        print(f"  ItemKNN core similarity ready (k={k}, {model.similarity.nnz} nnz)", flush=True)
        return self._knn_model


# ----------------------------------------------------------------------------- replay


def _candidate_ids(data: dict | None) -> list[str]:
    return [c["item_id"] for c in (data or {}).get("candidates", [])]


def report_run(run_dir: Path, res: ReplayResources, max_requests: int = 0,
               check_fidelity: bool = True) -> dict:
    requests_path = run_dir / "requests.jsonl"
    if not requests_path.exists():
        return {"run": str(run_dir), "error": "no requests.jsonl"}
    requests = {r["request_id"]: r for r in _load_jsonl(requests_path)}

    # trajectory file: prefer the one named in config.yaml, else trajectories.jsonl
    cfg = {}
    cfg_path = run_dir / "config.yaml"
    if cfg_path.exists():
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    traj_name = _find_key(cfg, "trajectory_file") or "trajectories.jsonl"
    traj_path = run_dir / traj_name
    if not traj_path.exists():
        traj_path = run_dir / "trajectories.jsonl"
    if not traj_path.exists():
        return {"run": str(run_dir), "error": "no trajectories file"}

    # as_of + metadata policy from the recorded config (fallback: trajectory field)
    as_of = int(_find_key(cfg, "as_of_timestamp") or _find_key(cfg, "target_timestamp_min"))
    policy = _find_key(cfg, "metadata_policy")
    policy_name = policy.get("name") if isinstance(policy, dict) else (policy or "historical_static_catalog")

    corpus = res.corpus_for(policy_name, as_of)

    # per-request target names (global idx -> namespaced id)
    def target_names(req):
        return {res.id2item.get(i) for i in req.get("targets", [])} - {None}

    stats = {
        "run": str(run_dir),
        "trajectory_file": traj_path.name,
        "policy": policy_name, "as_of": as_of,
        "budgets": res.budgets,
        "steps": Counter(),                 # tool -> ok retrieval steps replayed
        "fidelity_exact": 0, "fidelity_mismatch": 0,
        "target_step_hits_recorded": Counter(),   # tool -> #targets found in recorded candidates
        "target_step_hits_budget": {b: Counter() for b in res.budgets},
        "requests_with_targets": 0,
        "requests_hit_recorded": 0,          # any target in any recorded candidate list
        "requests_hit_budget": {b: 0 for b in res.budgets},
        "requests_no_retrieval_step": 0,
        "best_rank_extended": [],            # best position of a target in extended lists
        "per_request": [],
    }

    cache: dict[tuple, list[str]] = {}

    def ids_for(tool_name, args, budget):
        key = (tool_name, json.dumps(args, sort_keys=True, default=str), budget)
        if key not in cache:
            budget_arg = BUDGET_ARG[tool_name]
            call = dict(args)
            if budget is not None:
                call[budget_arg] = min(budget, 1000)
            try:
                cache[key] = _candidate_ids(res.tool_for(tool_name, corpus).execute(**call))
            except Exception as exc:
                cache[key] = []
                cache[("__err__",) + key] = str(exc)
        return cache[key]

    n = 0
    for row in _load_jsonl(traj_path):
        req = requests.get(row.get("request_id"))
        if req is None:
            continue
        targets = target_names(req)
        if not targets:
            continue
        if max_requests and n >= max_requests:
            break
        n += 1
        stats["requests_with_targets"] += 1

        retrieval_steps = [s for s in row.get("steps", [])
                           if s.get("tool") in RETRIEVAL_TOOLS and s.get("ok")]
        if not retrieval_steps:
            stats["requests_no_retrieval_step"] += 1

        req_hit_recorded = set()
        req_hit_budget = {b: set() for b in res.budgets}
        best_rank = None

        for step in retrieval_steps:
            tname = step["tool"]
            args = step.get("args") or {}
            recorded = _candidate_ids(step.get("data"))
            stats["steps"][tname] += 1

            # fidelity: replay recorded args, compare to logged candidates
            if check_fidelity:
                replayed = ids_for(tname, args, None)
                if replayed == recorded:
                    stats["fidelity_exact"] += 1
                else:
                    stats["fidelity_mismatch"] += 1

            hit_rec = targets & set(recorded)
            stats["target_step_hits_recorded"][tname] += len(hit_rec)
            req_hit_recorded |= hit_rec
            for t in hit_rec:
                pos = recorded.index(t) + 1
                best_rank = pos if best_rank is None else min(best_rank, pos)

            recorded_budget = int(args.get(BUDGET_ARG[tname]) or 0)
            for b in res.budgets:
                if b <= recorded_budget:
                    continue
                ext = ids_for(tname, args, b)
                ext_set = set(ext)
                hit = targets & ext_set
                stats["target_step_hits_budget"][b][tname] += len(hit)
                req_hit_budget[b] |= hit
                for t in hit:
                    pos = ext.index(t) + 1
                    if best_rank is None or pos < best_rank:
                        best_rank = pos

        if req_hit_recorded:
            stats["requests_hit_recorded"] += 1
        for b in res.budgets:
            if req_hit_budget[b]:
                stats["requests_hit_budget"][b] += 1
        if best_rank is not None:
            stats["best_rank_extended"].append(best_rank)
        stats["per_request"].append({
            "request_id": row.get("request_id"), "kind": req.get("kind"),
            "segment": req.get("segment"), "n_targets": len(targets),
            "n_retrieval_steps": len(retrieval_steps),
            "hit_recorded": bool(req_hit_recorded),
            "hit_budget": {str(b): bool(req_hit_budget[b]) for b in res.budgets},
        })

    ranks = stats.pop("best_rank_extended")
    stats["steps"] = dict(stats["steps"])
    stats["target_step_hits_recorded"] = dict(stats["target_step_hits_recorded"])
    stats["target_step_hits_budget"] = {str(b): dict(c) for b, c in stats["target_step_hits_budget"].items()}
    stats["requests_hit_budget"] = {str(b): v for b, v in stats["requests_hit_budget"].items()}
    if ranks:
        stats["best_rank_extended"] = {
            "n": len(ranks), "median": float(np.median(ranks)),
            "p90": float(np.percentile(ranks, 90)), "max": int(max(ranks)),
        }
    else:
        stats["best_rank_extended"] = None
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--budgets", default="200,500",
                    help="comma-separated absolute candidate budgets for the extended replay")
    ap.add_argument("--max-requests", type=int, default=0, help="cap requests per run (0 = all)")
    ap.add_argument("--no-dense", action="store_true", help="skip the dense retrieval leg")
    ap.add_argument("--no-fidelity", action="store_true", help="skip re-executing recorded args")
    ap.add_argument("--output", type=Path, default=None, help="write combined JSON report")
    args = ap.parse_args()

    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]
    res = ReplayResources(budgets=budgets, use_dense=not args.no_dense)

    reports = []
    for run_dir in args.run_dirs:
        print(f"== {run_dir}", flush=True)
        t0 = time.time()
        rep = report_run(run_dir, res, max_requests=args.max_requests,
                         check_fidelity=not args.no_fidelity)
        rep["elapsed_s"] = round(time.time() - t0, 1)
        reports.append(rep)
        if "error" in rep:
            print(f"   ERROR: {rep['error']}", flush=True)
            continue
        r = rep
        print(f"   requests_with_targets={r['requests_with_targets']} "
              f"retrieval_steps={sum(r['steps'].values())} "
              f"fidelity={r['fidelity_exact']}ok/{r['fidelity_mismatch']}mismatch", flush=True)
        print(f"   requests_hit_recorded={r['requests_hit_recorded']} "
              f"hit_budget={r['requests_hit_budget']}", flush=True)
        print(f"   target_step_hits_recorded={r['target_step_hits_recorded']}", flush=True)
        print(f"   target_step_hits_budget={r['target_step_hits_budget']}", flush=True)
        print(f"   best_rank_extended={r['best_rank_extended']}", flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
