"""
Agent evaluation: does the agent layer add anything over the plain recommender, and where?

One run builds a fixed set of simulated requests from held-out data, sends the SAME requests to every agent
listed in configs/agent/agent_eval.yaml and scores them (ranking metrics + agent metrics).  Request kinds:
  similar / personalized   built from the user's fit history only (honest)
  constrained / cold_text  category (+ price ceiling) taken from held-out items = ORACLE scenario, an upper bound
  ambiguous                missing information; the right move is to ask back instead of inventing ids
Agents: baseline (ItemKNN, no LLM) | type1 (fixed plan, no LLM) | planner (LLM, E6) | planner_memory (+MemoryTool, E7).
By default, target-informed oracle request kinds are excluded (agent_eval.request_scope); set it to ``oracle``
to run only those cases.  ALL tunables live in YAML — there are no override flags:
configs/agent/agent_eval.yaml (agents, per_segment, request_scope, trajectory_file, ...),
configs/agent/agent.yaml (reflect_rounds), configs/agent/inference.yaml (mode), configs/eval/baselines.yaml (seed).

Inference (final answer, package/inference): after type1 / planner / planner_memory the agent's outcome is turned into a text answer.
It only PRESENTS what the agent chose, so `recommended`, task_success, recall... are unchanged; the answer is judged by its own columns
(answer_grounded, answer_fallback, answer_status_*, inference_* tokens/latency, kept apart from the planner's `usage`).
inference.mode=llm writes the answer with the LLM (checked against the tool data, template fallback; <= 1 + llm_retries extra calls
per answered request), inference.mode=template is deterministic and calls no LLM. The baseline has no answer.

Reads splits/mappings from resource/ (data_paths.yaml) and meta_<Domain>.jsonl.gz from resource/raw/.
Trajectories are appended to a file as they finish, so an interrupted run continues with --resume.
Nothing here touches the test split unless you pass --eval-on test.

    PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation
    PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from dataclasses import asdict
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from package.agents import PlanExecutor, Type1Agent, build_tools, Session
from package.agents import extract_recommendations, get_agent_limits, get_session_limits
from package.evaluation import (
    AGENTS,
    INFERENCE_AGENTS,
    ORACLE_KINDS,
    PLANNER_AGENTS,
    AgentRequest,
    build_requests,
    filter_requests_by_scope,
)
from package.evaluation import EVAL_SCHEMA_VERSION
from package.evaluation.trajectory import score_trajectory, summarize
from package.evaluation.provenance import build_run_provenance
from package.config import get_data_paths, get_domains, load_config
from package.config.load_config import ConfigError
from package.data import ITEM_ID_SEPARATOR, build_first_seen_timestamps
from package.data.leakage import check_profile_snapshot
from package.data.manifest import verify_tag_manifest
from package.data.mapping import load_mappings
from package.data.pipeline import build_meta_files
from package.data.split import load_splits
from package.api import build_llm_provider
from package.api import LLMProviderError
from package.inference import compose_answer, get_inference_limits, outcome_from_plan_results, outcome_from_type1
from package.tools import BaselineScorer, HybridScorer, ToolCallLogger
from package.recommenders.evaluation.hybrid_item_knn_recommender import HybridItemKNNRecommender
from package.recommenders.evaluation.item_knn_matrix_recommender import ItemKNNMatrixRecommender
from package.corpus.build_corpus import build_corpus
from package.corpus.load_corpus import load_corpus
from package.evaluation.recommender.experiment import next_experiment_dir, save_experiment
from package.evaluation.recommender.config import segment_users_by_history, select_fit_target
from package.evaluation.recommender.utils import sha256_file
from package.recommenders.runtime.item_knn_recommender import ItemKNNRecommender
from package.recommenders.shared import item_knn_data_hash, mapping_hash
from package.recommenders.shared.load_item_knn import load_item_knn
from package.recommenders.shared.save_item_knn import save_item_knn
from package.utils import ensure_utf8_stdout
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.evaluation.recommender.core.evaluation_protocol import evaluation_protocol
from package.evaluation.recommender.analysis.cohort_policy_for_paths import cohort_policy_for_paths

SUMMARY_COLUMNS = (  # printed per (agent, kind); the full set is in metrics.json
    "task_success", "precision@{k}", "recall@{k}", "ndcg@{k}", "map@{k}", "constraint_satisfaction", "tool_selection_ok",
    "asked_clarification", "invented_ids", "n_steps", "first_attempt_ok", "reflections", "llm_latency_seconds", "completion_tokens",
    "answer_status_ok", "answer_grounded", "answer_fallback",
)


def empty_trajectory(request: AgentRequest, agent: str, tools_available: list[str]) -> dict[str, Any]:
    return {
        "request_id": request.request_id, "agent": agent, "text": request.text, "tools_available": tools_available,
        "plan": [], "ask_user": None, "steps": [], "recommended": [], "usage": {}, "error": None,
        "provider_error": False, "truncated": False, "wall_seconds": 0.0,
        "reflections": 0, "first_attempt_ok": None, "reflect_rounds": None,
        # Session state (if enabled)
        "session_enabled": False, "session_state": None,
        # Inference (None / {} = this agent has no answer, e.g. the baseline); answer_fallback = why the template replaced the LLM text
        "answer": None, "answer_status": None, "answer_grounded": None, "answer_composer": None, "answer_fallback": None,
        "answer_reason": None, "inference_usage": {}, "inference_mode": None,
    }


def attach_answer(traj: dict[str, Any], answer: Any, inference_mode: str) -> None:
    """Copy an Inference Answer into the trajectory; the planner's `usage` and `recommended` are never touched."""
    traj.update(
        answer=answer.text, answer_status=answer.status, answer_grounded=answer.grounded, answer_composer=answer.composer,
        answer_fallback=answer.fallback_reason, answer_reason=answer.reason, inference_usage=dict(answer.usage),
        inference_mode=inference_mode,
    )


def is_resumable(
    rec: dict[str, Any], text_of: dict[str, str], agents: list[str], reflect_rounds: int, inference_mode: str | None = None,
    protocol_hash: str | None = None, session_enabled: bool = False,
) -> bool:
    """
    A saved trajectory is reused only for the same request text, a requested agent and (planners) the same reflect_rounds.
    Agents that get an answer (type1, planners) also need the same inference_mode, so LLM and template answers never mix in one
    experiment; a record without the field was written before Inference existed: it is reused and its answer columns stay empty.
    Session state must also match if enabled.
    """
    if protocol_hash is not None and rec.get("evaluation_protocol_hash") != protocol_hash:
        return False
    if text_of.get(rec["request_id"]) != rec["text"] or rec["agent"] not in agents:
        return False
    if inference_mode is not None and rec["agent"] in INFERENCE_AGENTS and rec.get("inference_mode", inference_mode) != inference_mode:
        return False
    if rec["agent"] in PLANNER_AGENTS and rec.get("reflect_rounds", 0) != reflect_rounds:
        return False
    # Session state must match
    if rec.get("session_enabled", False) != session_enabled:
        return False
    return True


def _error_chars() -> int:
    """Step/plan errors are cut to this many characters in the trajectory file (agent_eval.trajectory_error_chars)."""
    chars = int(load_config("agent/agent_eval")["agent_eval"]["trajectory_error_chars"])
    if chars <= 0:
        raise ConfigError("configs/agent/agent_eval.yaml: trajectory_error_chars must be > 0")
    return chars


def run_planner(
    executor: PlanExecutor, request: AgentRequest, agent: str, k: int, *, answerer: Any = None, inference_mode: str | None = None,
    session_enabled: bool = False,
) -> dict[str, Any]:
    """
    One planner trajectory. `answerer(AgentOutcome) -> Answer` (compose_answer bound to the LLM and mode) adds the final answer;
    it runs after the agent's own timing (wall_seconds keeps its old meaning) and never touches recommended / usage.
    If session_enabled=True, a fresh Session is created for this request (multi-turn conversations share a session
    across turns by reusing the same executor; single-turn requests with session_enabled get isolated sessions).
    """
    traj = empty_trajectory(request, agent, sorted(executor.tools))
    error_chars = _error_chars()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    
    # For multi-turn evaluation (agent_eval.enable_session), create a fresh session per request
    # to prevent cross-request contamination. The executor's session is replaced temporarily.
    original_session = executor.session
    if session_enabled:
        executor.session = Session(**asdict(get_session_limits()))
    try:
        results = executor.run(request.text)
        traj["steps"] = [
            {**{key: r.get(key) for key in ("tool", "ok", "invented_ids", "latency_seconds", "args", "output_summary", "note", "error_kind")},
             "error": None if r.get("error") is None else str(r["error"])[:error_chars]}
            for r in results
        ]
        traj["recommended"] = extract_recommendations(results, k)
    except (ValueError, LLMProviderError) as exc:  # unparsable plan after retries, or the endpoint failed
        traj["error"] = f"{type(exc).__name__}: {exc}"[:error_chars]
        traj["provider_error"] = isinstance(exc, LLMProviderError)
    traj.update(plan=executor.last_plan, ask_user=executor.last_question, truncated=executor.last_truncated,
                usage=dict(executor.last_usage), reflections=executor.last_reflections, reflect_rounds=executor.reflect_rounds,
                first_attempt_ok=executor.last_first_attempt_ok and traj["error"] is None)
    traj["wall_seconds"] = round(time.perf_counter() - started, 3)

    # Capture session state if enabled
    if executor.session is not None:
        traj["session_enabled"] = True
        traj["session_state"] = executor.session.to_dict()

    # Restore original session (which is None for single-turn evaluation)
    executor.session = original_session

    if answerer is not None:
        outcome = outcome_from_plan_results(request.text, results, question=executor.last_question, plan_error=traj["error"])
        attach_answer(traj, answerer(outcome), inference_mode)
    return traj


def run_type1(
    runner: Type1Agent, request: AgentRequest, k: int, *, answerer: Any = None, inference_mode: str | None = None,
) -> dict[str, Any]:
    """One type1 trajectory (fixed plan, no LLM for the recommendation); `answerer` as in run_planner."""
    traj = empty_trajectory(request, "type1", [])
    started = time.perf_counter()
    try:
        out = runner.recommend(request.user_id, [request.seed_item_id], top_k=k)
    except Exception as exc:
        out = {"ok": False, "stage": "exception", "error": f"{type(exc).__name__}: {exc}"}
    calls = list(getattr(runner, "last_tool_calls", []))
    traj["tools_available"] = ["SimilarTool", "RankTool", "LookupTool"]
    traj["tool_calls"] = calls
    traj["steps"] = [dict(tool=c["tool"], ok=c["output"]["ok"],
                          args=c.get("input"), input_hash=c.get("input_hash"),
                          timestamp=c.get("timestamp"), action=c.get("action"),
                          latency_seconds=c["latency_seconds"], output_summary=c["output"],
                          data=c.get("data") or {}, error=c["output"].get("error"),
                          invented_ids=[], error_kind=None if c["output"]["ok"] else "tool_error")
                     for c in calls]
    if out["ok"]:
        traj["recommended"] = [it["item_id"] for it in out["items"]][:k]
    else:
        traj["error"] = f"{out.get('stage')}: {out.get('error')}"
    traj["wall_seconds"] = round(time.perf_counter() - started, 3)
    if answerer is not None:
        attach_answer(traj, answerer(outcome_from_type1(request.text, out)), inference_mode)
    return traj


def _resume_agent_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """agent_eval config as hashed into resume_identity.

    ``multi_turn`` and ``campaign_id`` are excluded: neither affects
    trajectories (campaign_id is provenance — the trajectory_file name
    already carries it), so toggling them must not invalidate --resume.
    """
    return {k: v for k, v in cfg.items() if k not in ("multi_turn", "campaign_id")}


def run_optional_multi_turn(cfg: dict[str, Any], exp_dir_candidate: Path) -> dict[str, Any] | None:
    """Run the yaml-gated multi-turn step; never let it sink the main eval.

    Returns None when ``agent_eval.multi_turn.enabled`` is false (nothing
    changes downstream — metrics.json stays byte-identical). Any failure in
    the step itself is captured as ``status: "error"`` so the already-paid
    agent evaluation is still saved.
    """
    mt_cfg = cfg.get("multi_turn") or {}
    if not mt_cfg.get("enabled"):
        return None
    default_out = exp_dir_candidate / "multi_turn.json"
    try:
        from package.evaluation.multi_turn import run_multi_turn_for_eval

        return run_multi_turn_for_eval(mt_cfg, default_out)
    except Exception as exc:
        return {
            "status": "error",
            "resumed": False,
            "output_path": str(default_out),
            "summary": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", action="append",
                    help="Domain của bundle dữ liệu + meta để nạp (lặp lại). "
                         "Mặc định: tất cả domains.yaml -> bundle 'multi_domain'. "
                         "Đúng 1 domain -> bundle tên domain đó; tập con khác bị từ chối.")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--resume", action="store_true", help="Dùng lại trajectory đã ghi của lần chạy trước (cùng request text)")
    args = ap.parse_args()

    cfg = load_config("agent/agent_eval")["agent_eval"]
    baselines = load_config("eval/baselines")["baselines"]
    scoring_cfg = load_config("agent/scoring")["scoring"]
    scorer_mode = scoring_cfg["mode"]
    scorer_weight = float(scoring_cfg["hybrid_popularity_weight"])
    if scorer_mode not in ("baseline", "hybrid") or not np.isfinite(scorer_weight) or scorer_weight < 0:
        raise SystemExit("agent/scoring.yaml: mode must be baseline/hybrid and hybrid_popularity_weight finite and nonnegative")
    k, seed = int(cfg["k"]), int(baselines["seed"])
    agents = [str(a) for a in cfg["agents"]]
    if set(agents) - set(AGENTS):
        raise SystemExit(f"Unknown agent(s) {sorted(set(agents) - set(AGENTS))}; choose from {list(AGENTS)}")
    per_segment = int(cfg["per_segment"])
    reflect_rounds = get_agent_limits().reflect_rounds
    inference_mode = get_inference_limits().mode
    request_scope = str(cfg["request_scope"])
    session_enabled = bool(cfg["enable_session"])
    use_prebuilt = bool(cfg["use_prebuilt_corpus"])
    allow_missing = bool(cfg["allow_missing_corpus_sources"])
    metadata_policy_name = str(cfg["metadata_policy"])
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]

    data_paths = get_data_paths(domains=args.domain)
    tag_manifest = verify_tag_manifest(data_paths, domains=args.domain or get_domains())
    if tag_manifest["status"] == "legacy_unmanifested":
        print("!!! WARNING: tag has legacy artifacts without pipeline manifests; results will be marked legacy_unmanifested.", flush=True)
    elif tag_manifest["warnings"]:
        print(f"!!! WARNING: tag manifest chain has warnings: {tag_manifest['warnings']}", flush=True)
    meta_files = build_meta_files(data_paths, args.domain)
    t_start = time.time()

    # ---- splits, mapping, fit/target (same protocol as run_baselines.py / candidate_recall.py)
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, args.eval_on)
    if "timestamp" not in fit_df.columns:
        raise SystemExit("Splits have no `timestamp` column: re-run python scripts/data_pipeline/run_pipeline.py --stages 3")
    as_of = int(target_df["timestamp"].min())
    check_profile_snapshot(as_of_timestamp=as_of, source_interactions=fit_df)  # nothing the agent can read is from the future

    user2id, item2id = load_mappings(data_paths.mapped_dir)
    if not any(ITEM_ID_SEPARATOR in key for key in islice(item2id, 1000)):
        raise SystemExit("Mapping has plain item ids; the tools need namespaced 'Domain::asin' ids (run the multi-domain pipeline)")
    id2item, id2user = {v: k_ for k_, v in item2id.items()}, {v: k_ for k_, v in user2id.items()}
    num_users = len(user2id)

    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    hist_size = np.bincount(fit_df.drop_duplicates(["user_idx", "item_idx"])["user_idx"].to_numpy(), minlength=num_users)
    seg_of = segment_users_by_history(target_by_user, hist_size, sparse_max)
    latest = fit_df[fit_df["user_idx"].isin(list(target_by_user))].sort_values("timestamp").drop_duplicates("user_idx", keep="last")
    last_item_of = dict(zip(latest["user_idx"].tolist(), latest["item_idx"].tolist()))

    # ---- corpus + models + tools
    knn_artifact_status = "fit_fresh_no_prebuilt"
    if not use_prebuilt:
        print("Build corpus in RAM (agent_eval.use_prebuilt_corpus: false)")
        first_seen_ts = build_first_seen_timestamps([(d, data_paths.cleaned_path(d)) for d, _ in meta_files])
        corpus, meta, coverage, build_times = build_corpus(meta_files, item2id, float(cfg["min_metadata_coverage"]), timing=True, first_seen_ts=first_seen_ts)
        print(f"Corpus: built in {sum(build_times.values()):.2f}s")
    else:
        corpus_path = data_paths.corpus_path
        if not corpus_path.exists():
            raise SystemExit(
                f"Corpus file not found: {corpus_path}\n"
                f"Run: python scripts/data_pipeline/run_pipeline.py --stages 4 "
                f"(tag {data_paths.tag!r} derives from --domain; merged = all domains)\n"
                f"Or set agent_eval.use_prebuilt_corpus: false to build in RAM (slower, for debug or small datasets)"
            )
        print(f"Load corpus from {corpus_path}")
        corpus, coverage = load_corpus(
            corpus_path, meta_files, item2id, float(cfg["min_metadata_coverage"]),
            allow_missing_sources=allow_missing,
        )
        file_size_mb = corpus_path.stat().st_size / (1024 * 1024)
        print(f"Corpus: loaded from {corpus_path} in (see backup time above) ({file_size_mb:.1f} MB)")

    metadata_policy = apply_metadata_policy(corpus, metadata_policy_name, as_of_timestamp=as_of)
    # Agent request cohorts are recorded separately after request construction.
    protocol_manifest = evaluation_protocol(eval_on=args.eval_on, tag=data_paths.tag, fit_df=fit_df,
        target_df=target_df, user2id=user2id, item2id=item2id, segments=seg_of,
        sampled={}, metadata_policy=metadata_policy, evaluation_kind="agent",
        cohort_policy=cohort_policy_for_paths(data_paths))

    knn_k = int(baselines["item_knn"]["k"])
    fit_pairs = fit_df[["user_idx", "item_idx"]]
    knn_fit_data_hash = item_knn_data_hash(fit_pairs)
    knn_cache_data_hash = None
    item_knn_path = data_paths.item_knn_path(args.eval_on)
    cache_meta_path = item_knn_path.with_suffix(".meta.json")
    if cache_meta_path.exists():
        knn_cache_data_hash = json.loads(cache_meta_path.read_text(encoding="utf-8")).get("data_hash")

    # item_knn_reuse_cache (campaign overlay): fit once per cache location, then
    # siblings load the artifact — but only after load_item_knn validates
    # data_hash + fit provenance (mappings/split/tag) + k + sha256. Any mismatch
    # falls back to a fresh fit, which is always the gold standard.
    reuse_cache = bool(cfg.get("item_knn_reuse_cache", False))
    knn = None
    if reuse_cache and item_knn_path.exists():
        try:
            t0 = time.perf_counter()
            knn = load_item_knn(
                item_knn_path, knn_k, fit_pairs,
                user2id=user2id, item2id=item2id,
                eval_on=args.eval_on, tag=data_paths.tag,
            )
            knn_artifact_status = "loaded_cache"
            print(f"ItemKNN: loaded validated cache from {item_knn_path} ({time.perf_counter() - t0:.1f}s)")
        except Exception as exc:
            print(f"ItemKNN cache rejected ({exc}); fitting fresh")
            knn = None
    if knn is None:
        if reuse_cache:
            knn_artifact_status = "fit_fresh_cache_pending_save"
        else:
            print("Fit ItemKNN on current fit split (prebuilt cache ignored for evaluation provenance)")
            knn_artifact_status = "fit_fresh_cache_ignored"
        t0 = time.perf_counter()
        knn = ItemKNNRecommender(knn_k).fit(fit_pairs)
        fit_time = time.perf_counter() - t0
        knn._fit_time = fit_time
        print(f"ItemKNN: fitted in {fit_time:.1f}s")
        if reuse_cache:
            try:
                save_item_knn(
                    knn, item_knn_path, knn_k, fit_pairs,
                    user2id=user2id, item2id=item2id,
                    eval_on=args.eval_on, tag=data_paths.tag,
                )
                knn_artifact_status = "fit_fresh_cache_saved"
                print(f"ItemKNN: saved cache to {item_knn_path}")
            except Exception as exc:
                knn_artifact_status = "fit_fresh_cache_save_failed"
                print(f"ItemKNN cache save failed ({exc}); siblings will refit")

    logger = ToolCallLogger()  # shared; cleared after every request so it never grows
    scorer = HybridScorer(knn, scorer_weight) if scorer_mode == "hybrid" else BaselineScorer(knn)
    baseline_model = knn
    if scorer_mode == "hybrid":
        cf = ItemKNNMatrixRecommender(k=knn_k)
        cf.train_matrix = knn.user_items
        cf.num_users, cf.num_items = knn.user_items.shape
        cf.similarity = knn.similarity.T.tocsr()
        baseline_model = HybridItemKNNRecommender(cf, knn.user_items, scorer_weight)
    scorer_provenance = {
        "mode": scorer_mode, "name": scorer.name,
        "popularity_weight": scorer_weight if scorer_mode == "hybrid" else scorer.popularity_weight,
        "popularity_source": "full pre-target unique user-item history" if scorer_mode == "hybrid" else "CF fit popularity",
        "cf_normalization": "per-user full-catalog max before exclusion" if scorer_mode == "hybrid" else "none",
        "cf_provenance": protocol_manifest["item_knn"],
        "history_splits": ["train"] if args.eval_on == "validation" else ["train", "validation"],
        "candidate_ties": "input order (RecoModelTool)", "baseline_ties": "global item index",
    }
    protocol_manifest["scorer"] = scorer_provenance
    tools = build_tools(knn, scorer, user2id, item2id, fit_df, corpus, logger=logger, as_of_timestamp=as_of)

    runners: dict[str, Any] = {}
    if "type1" in agents:
        runners["type1"] = Type1Agent(tools.item_cf, tools.reco, tools.query)
    llm = None
    needs_llm = any(a in PLANNER_AGENTS for a in agents) or (inference_mode == "llm" and any(a in INFERENCE_AGENTS for a in agents))
    if needs_llm:
        llm = build_llm_provider(load_config("agent/llm"))
        if not llm.health_check():
            raise SystemExit("LLM health check failed: check configs/agent/llm.yaml and LLM_API_KEY "
                             "(or set agent_eval.agents to baseline,type1 and inference.mode to template in YAML)")
    if any(a in PLANNER_AGENTS for a in agents):
        # Single-turn evaluation: no session (session=None).
        # Multi-turn evaluation (agent_eval.enable_session): a fresh Session is created per request inside run_planner.
        # This prevents cross-request contamination of shown_items/candidates/constraints.
        runners["planner"] = PlanExecutor(llm, tools.for_planner(), reflect_rounds=reflect_rounds, session=None)
        runners["planner_memory"] = PlanExecutor(llm, tools.for_planner_memory(), reflect_rounds=reflect_rounds, session=None)

    # Build provenance (hashes of prompts, tool schemas, git state, limits)
    provenance = build_run_provenance(
        planner_tools=tools.for_planner(),
        memory_tools=tools.for_planner_memory() if "planner_memory" in agents else None,
    )

    def answerer(outcome: Any) -> Any:
        return compose_answer(outcome, llm, mode=inference_mode)

    # ---- requests (deterministic given the seed) and the trajectory file
    requests = build_requests(
        seg_of=seg_of, target_by_user=target_by_user, last_item_of=last_item_of, id2user=id2user, id2item=id2item,
        item2id=item2id, corpus=corpus, per_segment=per_segment, n_ambiguous=int(cfg["n_ambiguous"]),
        language=cfg["language"], k=k, price_slack=float(cfg["price_slack"]), price_round_to=float(cfg["price_round_to"]),
        rng=np.random.default_rng(seed),
    )
    requests = filter_requests_by_scope(requests, request_scope)
    protocol_manifest["request_ids"] = [r.request_id for r in requests]
    protocol_manifest["request_scope"] = request_scope
    protocol_manifest["request_content_sha256"] = hashlib.sha256(
        json.dumps([r.to_dict() for r in requests], sort_keys=True, default=str).encode()).hexdigest()
    # Resume identity includes implementation, dataset, inputs and temporal policy.
    from package.evaluation.recommender.experiment.save_experiment import _source_fingerprint
    resume_identity = {
        "protocol": protocol_manifest, "fit_data_hash": knn_fit_data_hash,
        "source_fingerprint": _source_fingerprint(), "seed": seed, "neighbors": knn_k,
        "k": k, "reflect_rounds": reflect_rounds, "inference_mode": inference_mode,
        "agent_config": _resume_agent_config(cfg),
        "llm_config": load_config("agent/llm"),
        "metadata_content_hashes": {d: sha256_file(p) if Path(p).exists() else None for d,p in meta_files},
        "requests": [r.to_dict() for r in requests],
    }
    protocol_hash = hashlib.sha256(json.dumps(resume_identity, sort_keys=True, default=str).encode()).hexdigest()
    protocol_manifest["resume_identity_sha256"] = protocol_hash
    counts = pd.Series([f"{r.kind}/{r.segment}" for r in requests]).value_counts().sort_index()
    print("requests:", ", ".join(f"{name}={n}" for name, n in counts.items()), f"| agents: {agents}")
    text_of = {r.request_id: r.text for r in requests}

    trajectory_name = str(cfg["trajectory_file"])
    if Path(trajectory_name).name != trajectory_name or not trajectory_name.endswith(".jsonl"):
        raise SystemExit("agent_eval.trajectory_file must be a simple .jsonl filename")
    traj_path = data_paths.log_dir / trajectory_name
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    if traj_path.exists() and not args.resume:
        raise SystemExit(f"Trajectory already exists: {traj_path}; use --resume with the identical protocol or set a new agent_eval.trajectory_file")
    done: dict[tuple[str, str], dict[str, Any]] = {}
    if args.resume and traj_path.exists():
        for line in traj_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("evaluation_protocol_hash") != protocol_hash:
                raise SystemExit("Resume protocol mismatch or legacy trajectory: source log preserved; set a new agent_eval.trajectory_file")
            if is_resumable(rec, text_of, agents, reflect_rounds, inference_mode, protocol_hash, session_enabled=session_enabled):  # drop stale records (other text / agent / reflect_rounds / session)
                done[(rec["request_id"], rec["agent"])] = rec
    traj_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8")
    print(f"resumed {len(done)} trajectories" if done else "starting from scratch")

    # ---- run
    trajectories: list[dict[str, Any]] = []
    errors_in_a_row, total = 0, len(requests) * len(agents)
    with open(traj_path, "a", encoding="utf-8") as sink:
        for request in requests:
            for agent in agents:
                key = (request.request_id, agent)
                applicable = {
                    "baseline": request.user_idx is not None,
                    "type1": request.kind == "similar",
                    "planner": True,
                    "planner_memory": True,
                }[agent]
                if not applicable:
                    continue
                if key in done:
                    trajectories.append(done[key])
                    continue
                if agent in PLANNER_AGENTS:
                    traj = run_planner(runners[agent], request, agent, k, answerer=answerer, inference_mode=inference_mode, session_enabled=session_enabled)
                elif agent == "type1":
                    traj = run_type1(runners["type1"], request, k, answerer=answerer, inference_mode=inference_mode)
                else:
                    traj = empty_trajectory(request, agent, [])
                    started = time.perf_counter()
                    predicted = (baseline_model.recommend(request.user_idx, k, exclude=knn.user_items)
                                 if scorer_mode == "hybrid" else baseline_model.recommend(request.user_idx, k))
                    traj["recommended"] = [id2item[i] for i in predicted[:k] if i in id2item]
                    traj["wall_seconds"] = round(time.perf_counter() - started, 3)
                logger.records.clear()
                traj["evaluation_protocol_hash"] = protocol_hash
                traj["metadata_policy"] = metadata_policy_name
                trajectories.append(traj)
                sink.write(json.dumps(traj, ensure_ascii=False) + "\n")
                sink.flush()
                errors_in_a_row = errors_in_a_row + 1 if traj["provider_error"] else 0
                print(f"[{len(trajectories)}/{total}] {agent:<14} {request.request_id:<22} rec={len(traj['recommended']):>2} "
                      f"steps={len(traj['steps'])} {traj['wall_seconds']:.1f}s" +
                      (f" ans={traj['answer_status']}/{traj['answer_composer']}" + ("!" if traj["answer_fallback"] else "") if traj["answer_status"] else "") + (f"  ERROR {traj['error'][:80]}" if traj["error"] else ""))
                if errors_in_a_row >= int(cfg["max_consecutive_llm_errors"]):
                    raise SystemExit(f"{errors_in_a_row} LLM errors in a row: stopping. Fix the endpoint, then re-run with --resume")

    # ---- score + report
    by_id = {r.request_id: r for r in requests}
    rows = [score_trajectory(by_id[t["request_id"]], t, item2id=item2id, corpus=corpus, k=k) for t in trajectories]
    summary = summarize(rows)
    columns = [c.format(k=k) for c in SUMMARY_COLUMNS]
    for agent, per_kind in summary.items():
        for kind, per_segment_stats in per_kind.items():
            stats = per_segment_stats["all"]
            shown = "  ".join(f"{c}={stats[c]:.3f}" for c in columns if c in stats)
            print(f"{agent:<14} {kind:<13} n={stats['n']:<4} {shown}")

    metadata_source_records = {
        domain: {
            "path": path,
            "exists": Path(path).exists(),
            "size_bytes": Path(path).stat().st_size if Path(path).exists() else None,
            "sha256": sha256_file(path) if Path(path).exists() else None,
        }
        for domain, path in meta_files
    }
    # ---- optional multi-turn step (yaml-gated; runs after the main eval) ----
    # output_dir=None -> <exp_dir>/multi_turn.json; a configured path (the
    # campaign overlay sets campaigns/<id>/multi_turn/) writes there instead,
    # so the artifact exists in exactly one place. Disabled -> mt_info is None
    # and nothing below changes (metrics.json stays byte-identical).
    exp_dir_candidate = next_experiment_dir(data_paths.output_dir("agent_eval"))
    mt_info = run_optional_multi_turn(cfg, exp_dir_candidate)

    exp_config = {"manifest_status": tag_manifest["status"], "manifest_sha256": tag_manifest["manifest_sha256"],
                "protocol": protocol_manifest, "agents": agents, "k": k, "per_segment": per_segment, "n_ambiguous": cfg["n_ambiguous"], "language": cfg["language"],
                "request_scope": request_scope,
                "price_slack": cfg["price_slack"], "price_round_to": cfg["price_round_to"], "sparse_max": sparse_max,
                "item_knn_k": baselines["item_knn"]["k"], "reflect_rounds": reflect_rounds if any(a in PLANNER_AGENTS for a in agents) else None,
                "inference_mode": inference_mode if any(a in INFERENCE_AGENTS for a in agents) else None,
                "trajectory_log": str(traj_path),
                "llm_model": load_config("agent/llm").get("model"), "knn_artifact_status": knn_artifact_status,
                "knn_fit_data_hash": knn_fit_data_hash, "knn_cache_data_hash": knn_cache_data_hash,
                "knn_cache_used": knn_artifact_status == "loaded_cache",
                "scorer": scorer_provenance,
                "eval_schema_version": EVAL_SCHEMA_VERSION,
                "provenance": provenance,
                "corpus_artifacts": {
                    "mode": "built_from_metadata_in_memory" if not use_prebuilt else "loaded_prebuilt",
                    "metadata_sources": metadata_source_records,
                    "sqlite_path": None if not use_prebuilt else str(data_paths.corpus_path),
                    "sqlite_sha256": sha256_file(data_paths.corpus_path) if data_paths.corpus_path.exists() and use_prebuilt else None,
                    "manifest_path": str(data_paths.corpus_path.with_suffix(".meta.json")),
                    "manifest_sha256": sha256_file(data_paths.corpus_path.with_suffix(".meta.json")) if data_paths.corpus_path.with_suffix(".meta.json").exists() and use_prebuilt else None,
                    "source_hash_semantics": getattr(corpus, "_source_provenance", {"source_hash_protocol": "built_from_current_sources"}),
                    "missing_sources": [path for _, path in meta_files if not Path(path).exists()],
                    "allow_missing_sources": allow_missing,
                }}
    if cfg.get("campaign_id"):
        exp_config["campaign_id"] = cfg["campaign_id"]
    if mt_info is not None:
        exp_config["multi_turn"] = {
            "enabled": True,
            "status": mt_info["status"],
            "output_path": mt_info["output_path"],
            "dataset": (cfg.get("multi_turn") or {}).get("dataset"),
        }
    exp_dir = save_experiment(
        exp_dir_candidate,
        config=exp_config,
        metrics={"k": k, "summary": summary},
        seed=seed,
        dataset_info={"tag": data_paths.tag, "splits_dir": str(data_paths.splits_dir), "eval_on": args.eval_on, "num_users": num_users,
                      "num_items": len(item2id), "metadata_coverage": round(coverage, 4), "n_requests": len(requests),
                      "profile_as_of_timestamp": as_of,
                      "mapping_hash": mapping_hash(item2id), "user_mapping_hash": mapping_hash(user2id),
                      "mapping_hash_protocol": "sorted_key_index_json_v1",
                      "split_files": {name: {"path": str(data_paths.split_path(name)),
                                             "size_bytes": data_paths.split_path(name).stat().st_size,
                                             "mtime_ns": data_paths.split_path(name).stat().st_mtime_ns, "sha256": sha256_file(data_paths.split_path(name))}
                                      for name in ("train", "validation", "test")}},
        runtime_seconds=time.time() - t_start,
        exist_ok=mt_info is not None,
        notes=(f"Kinds {list(ORACLE_KINDS)} take their category/price constraints from held-out items: an ORACLE upper bound, "
               "never report them as real-query results. 'similar' and 'personalized' use fit history only. "
               "Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting."),
    )
    shutil.copyfile(traj_path, exp_dir / "trajectories.jsonl")
    (exp_dir / "requests.jsonl").write_text("".join(json.dumps(r.to_dict(), ensure_ascii=False) + "\n" for r in requests), encoding="utf-8")
    (exp_dir / "scored.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\nsaved -> {exp_dir}")
    if mt_info is not None:
        print(f"multi_turn -> {mt_info['output_path']} [{mt_info['status']}]")


if __name__ == "__main__":
    main()
