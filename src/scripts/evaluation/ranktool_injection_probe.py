"""Stage-isolation probe: inject held-out targets into RankTool and measure rescue.

For every request in an agent-eval run, this script:

  1. Collects the union of all candidates the planner's retrieval steps actually
     returned (recorded trajectory outputs — no re-execution).
  2. Appends the request's held-out targets to that candidate list (at the END,
     so input-order tiebreaks don't favor them).
  3. Runs the REAL RankTool.execute with the SAME scorer the eval used
     (BaselineScorer/HybridScorer per configs/agent/scoring.yaml, ItemKNN
     train_core model) and the SAME corpus metadata policy.

This answers the counterfactual the stage funnel cannot: "if retrieval had
worked perfectly, would ranking have saved the target?" Each target gets a
fate classification mirroring the stage taxonomy:

  hidden_policy      - dropped by first_seen temporal filter (pool-stage loss)
  unscored_other     - not in item2id / outside model matrix
  seen_excluded      - dropped by exclude_seen (user already interacted)
  ranked             - scored; record rank, score, CF term

Usage (from src/):
    python scripts/evaluation/ranktool_injection_probe.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from package.config import get_data_paths, load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.corpus import load_corpus
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.data.pipeline import build_meta_files
from package.tools import RankTool

from ranktool_score_audit import build_scorer, _load_jsonl

RETRIEVAL_TOOLS = ("SearchTool", "FilterTool", "SimilarTool")


def _find_key(d: dict, key: str):
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    for v in d.values():
        found = _find_key(v, key)
        if found is not None:
            return found
    return None


def _candidate_ids(data: dict | None) -> list[str]:
    return [c["item_id"] for c in (data or {}).get("candidates", [])]


def corpus_for(policy: str, as_of: int, cache: dict):
    key = (policy, as_of)
    if key not in cache:
        data_paths = resolve_bundle_paths()
        with open(data_paths.mapped_dir / "item2id.json", encoding="utf-8") as f:
            item2id = json.load(f)
        meta_files = build_meta_files(data_paths)
        corpus, _ = load_corpus(
            data_paths.corpus_path, meta_files, item2id,
            float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
            allow_missing_sources=True,
        )
        apply_metadata_policy(corpus, policy, as_of_timestamp=as_of)
        cache[key] = corpus
        print(f"  corpus ready (policy={policy}, as_of={as_of})", flush=True)
    return cache[key]


def probe_run(run_dir: Path, scorer, user2id, item2id, corpus) -> dict:
    requests = {r["request_id"]: r for r in _load_jsonl(run_dir / "requests.jsonl")}
    traj_path = run_dir / "trajectories.jsonl"
    if not traj_path.exists():
        cands = list(run_dir.glob("*trajectories.jsonl"))
        if not cands:
            return {"run": str(run_dir), "error": "no trajectories file"}
        traj_path = cands[0]

    id2item = {v: k for k, v in item2id.items()}
    tool = RankTool(scorer, user2id, item2id, corpus=corpus)

    fate = Counter()
    ranks = []
    cf_vals = []
    score_margins = []  # target score minus best non-target score
    per_kind = {}
    per_request = []

    for row in _load_jsonl(traj_path):
        req = requests.get(row.get("request_id"))
        if req is None:
            continue
        targets = [id2item[i] for i in req.get("targets", []) if i in id2item]
        if not targets:
            continue
        kind = req.get("kind") or "?"
        pk = per_kind.setdefault(kind, Counter())

        # union of recorded retrieval outputs, deduped, first-seen order
        union: list[str] = []
        seen: set[str] = set()
        for step in row.get("steps", []):
            if step.get("tool") in RETRIEVAL_TOOLS and step.get("ok"):
                for cid in _candidate_ids(step.get("data")):
                    if cid not in seen:
                        seen.add(cid)
                        union.append(cid)

        injected = [t for t in targets if t not in seen]
        combined = union + injected  # targets last: conservative on ties
        if not combined:
            continue

        out = tool.execute(user_id=req["user_id"], candidates=combined,
                           top_k=None, exclude_seen=True)

        unscored = set(out["unscored_item_ids"])
        excluded = set(out["excluded_seen"])
        ranked_ids = [r["item_id"] for r in out["ranked"]]
        rank_pos = {iid: r["rank"] for r, iid in zip(out["ranked"], ranked_ids)}
        score_by_id = {r["item_id"]: r["score"] for r in out["ranked"]}

        # CF term for targets (same math as BaselineScorer internals)
        user_idx = user2id.get(req["user_id"], -1)
        target_idxs = np.array([item2id[t] for t in targets], dtype=np.int64)
        cf = np.zeros(target_idxs.shape, dtype=np.float64)
        if scorer.similarity is not None and scorer.is_known_user(user_idx):
            cf_row = (scorer.user_items.getrow(user_idx) @ scorer.similarity).tocsr()
            cf = cf_row[:, target_idxs].toarray().ravel().astype(np.float64)
        cf_by_id = {t: float(c) for t, c in zip(targets, cf)}

        # best non-target score for margin
        non_target_scores = [s for iid, s in score_by_id.items() if iid not in set(targets)]
        best_other = max(non_target_scores) if non_target_scores else float("nan")

        req_fates = Counter()
        for t in targets:
            if t in excluded:
                f = "seen_excluded"
            elif t in unscored:
                idx = item2id.get(t, -1)
                if idx < 0 or idx >= scorer.num_items:
                    f = "unscored_outside_matrix"
                else:
                    f = "hidden_policy"  # in matrix but dropped by first_seen filter
            elif t in rank_pos:
                f = "ranked"
                ranks.append(rank_pos[t])
                cf_vals.append(cf_by_id[t])
                score_margins.append(score_by_id[t] - best_other)
            else:
                f = "dropped_unknown"
            fate[f] += 1
            pk[f] += 1
            req_fates[f] += 1

        per_request.append({
            "request_id": row.get("request_id"), "kind": kind,
            "n_targets": len(targets), "n_union_candidates": len(union),
            "fates": dict(req_fates),
            "target_ranks": {t: rank_pos.get(t) for t in targets if t in rank_pos},
            "target_scores": {t: score_by_id.get(t) for t in targets if t in score_by_id},
            "target_cf": cf_by_id,
        })

    n_targets = sum(fate.values())
    n_ranked = fate.get("ranked", 0)

    def rescue(k):
        return sum(1 for r in ranks if r <= k)

    out_stats = {
        "run": str(run_dir),
        "n_requests": len(per_request),
        "n_targets": n_targets,
        "fate_counts": dict(fate),
        "fate_frac": {k: v / n_targets for k, v in fate.items()} if n_targets else {},
        "ranked_rescue": {
            f"@{k}": rescue(k) for k in (1, 5, 10, 20, 50, 100)
        },
        "ranked_rescue_frac": {
            f"@{k}": rescue(k) / n_ranked for k in (1, 5, 10, 20, 50, 100)
        } if n_ranked else {},
        "rank_dist": {
            "n": len(ranks),
            "median": float(np.median(ranks)) if ranks else None,
            "p90": float(np.percentile(ranks, 90)) if ranks else None,
            "max": int(max(ranks)) if ranks else None,
        },
        "cf_nonzero_frac_ranked": float(np.mean([c > 0 for c in cf_vals])) if cf_vals else None,
        "score_margin_vs_best_other": {
            "median": float(np.median(score_margins)) if score_margins else None,
            "frac_beats_best_other": float(np.mean([m > 0 for m in score_margins])) if score_margins else None,
        },
        "per_kind": {k: dict(v) for k, v in per_kind.items()},
        "per_request": per_request,
    }
    return out_stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    scorer, user2id, item2id, mode = build_scorer(args.eval_on)
    print(f"  scorer mode={mode} name={scorer.name}", flush=True)

    cfg_cache: dict = {}
    reports = []
    for run_dir in args.run_dirs:
        print(f"== {run_dir}", flush=True)
        cfg_path = run_dir / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        as_of = int(_find_key(cfg, "as_of_timestamp") or _find_key(cfg, "target_timestamp_min") or 0)
        policy = _find_key(cfg, "metadata_policy")
        policy_name = policy.get("name") if isinstance(policy, dict) else (policy or "historical_static_catalog")
        corpus = corpus_for(policy_name, as_of, cfg_cache)

        rep = probe_run(run_dir, scorer, user2id, item2id, corpus)
        reports.append(rep)
        if "error" in rep:
            print(f"   ERROR: {rep['error']}", flush=True)
            continue
        print(f"   requests={rep['n_requests']} targets={rep['n_targets']}", flush=True)
        print(f"   fates={rep['fate_counts']}", flush=True)
        print(f"   rescue={rep['ranked_rescue']} rank_dist={rep['rank_dist']}", flush=True)
        print(f"   cf_nonzero_frac_ranked={rep['cf_nonzero_frac_ranked']} "
              f"margin={rep['score_margin_vs_best_other']}", flush=True)

    if args.output:
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
