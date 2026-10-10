"""
Agent evaluation: does the agent layer add anything over the plain recommender, and where?

One run builds a fixed set of simulated requests from held-out data, sends the SAME requests to every agent
listed in configs/agent/agent_eval.yaml and scores them (ranking metrics + agent metrics).  Request kinds:
  similar / personalized   built from the user's fit history only (honest)
  constrained / cold_text  category (+ price ceiling) taken from held-out items = ORACLE scenario, an upper bound
  ambiguous                missing information; the right move is to ask back instead of inventing ids
Agents: baseline (ItemKNN, no LLM) | type1 (fixed plan, no LLM) | planner (LLM, E6) | planner_memory (+MemoryTool, E7).

Reads splits/mappings from resource/ (data_paths.yaml) and meta_<Domain>.jsonl.gz from resource/raw/.
Trajectories are appended to a file as they finish, so an interrupted run continues with --resume.
Nothing here touches the test split unless you pass --eval-on test.

    PYTHONPATH=. python scripts/py/run_agent_eval.py --per-segment 2          # tiny trial first
    PYTHONPATH=. python scripts/py/run_agent_eval.py --agents baseline,type1  # no LLM calls at all
    PYTHONPATH=. python scripts/py/run_agent_eval.py --resume
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from itertools import islice
from typing import Any

import numpy as np
import pandas as pd

from package.agents import PlanExecutor, Type1Agent, build_tools
from package.agents.evaluation import (
    AGENTS,
    ORACLE_KINDS,
    PLANNER_AGENTS,
    AgentRequest,
    build_requests,
    extract_recommendations,
    score_trajectory,
    summarize,
)
from package.config import get_data_paths, get_domains, load_config
from package.data import ITEM_ID_SEPARATOR
from package.data.leakage import check_profile_snapshot
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.llm import build_llm_provider
from package.llm._error import LLMProviderError
from package.tools import BaselineScorer, ToolCallLogger
from package.tools.corpus import build_corpus
from package.tools.evaluation import next_experiment_dir, save_experiment, segment_users, select_fit_target
from package.tools.recommenders import ItemKNNRecommender
from package.utils.console import ensure_utf8_stdout

ERROR_CHARS = 300  # step/plan errors are cut to this many characters in the trajectory file

SUMMARY_COLUMNS = (  # printed per (agent, kind); the full set is in metrics.json
    "task_success", "recall@{k}", "ndcg@{k}", "constraint_satisfaction", "tool_selection_ok",
    "asked_clarification", "invented_ids", "n_steps", "llm_latency_seconds", "completion_tokens",
)


def empty_trajectory(request: AgentRequest, agent: str, tools_available: list[str]) -> dict[str, Any]:
    return {
        "request_id": request.request_id, "agent": agent, "text": request.text, "tools_available": tools_available,
        "plan": [], "ask_user": None, "steps": [], "recommended": [], "usage": {}, "error": None,
        "provider_error": False, "truncated": False, "wall_seconds": 0.0,
    }


def run_planner(executor: PlanExecutor, request: AgentRequest, agent: str, k: int) -> dict[str, Any]:
    traj = empty_trajectory(request, agent, sorted(executor.tools))
    started = time.perf_counter()
    try:
        results = executor.run(request.text)
        traj["steps"] = [
            {**{key: r.get(key) for key in ("tool", "ok", "invented_ids", "latency_seconds")},
             "error": None if r.get("error") is None else str(r["error"])[:ERROR_CHARS]}
            for r in results
        ]
        traj["recommended"] = extract_recommendations(results, k)
    except (ValueError, LLMProviderError) as exc:  # unparsable plan after retries, or the endpoint failed
        traj["error"] = f"{type(exc).__name__}: {exc}"[:ERROR_CHARS]
        traj["provider_error"] = isinstance(exc, LLMProviderError)
    traj.update(plan=executor.last_plan, ask_user=executor.last_question, truncated=executor.last_truncated,
                usage=dict(executor.last_usage))
    traj["wall_seconds"] = round(time.perf_counter() - started, 3)
    return traj


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml).")
    ap.add_argument("--domain", action="append", help="Domain có meta để nạp (lặp lại; mặc định: tất cả trong domains.yaml)")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--agents", help="Danh sách agent, cách nhau dấu phẩy (mặc định: agent_eval.agents)")
    ap.add_argument("--per-segment", type=int, help="Số request mỗi (kind, segment) (mặc định: agent_eval.per_segment)")
    ap.add_argument("--resume", action="store_true", help="Dùng lại trajectory đã ghi của lần chạy trước (cùng request text)")
    args = ap.parse_args()

    cfg = load_config("agent/agent_eval")["agent_eval"]
    baselines = load_config("eval/baselines")["baselines"]
    k, seed = int(cfg["k"]), int(baselines["seed"])
    agents = [a.strip() for a in (args.agents or ",".join(cfg["agents"])).split(",") if a.strip()]
    if set(agents) - set(AGENTS):
        raise SystemExit(f"Unknown agent(s) {sorted(set(agents) - set(AGENTS))}; choose from {list(AGENTS)}")
    per_segment = args.per_segment or int(cfg["per_segment"])
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    data_paths = get_data_paths(args.tag)
    meta_files = [(d, str(data_paths.meta_path(d))) for d in (args.domain or get_domains())]
    t_start = time.time()

    # ---- splits, mapping, fit/target (same protocol as run_baselines.py / candidate_recall.py)
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, args.eval_on)
    if "timestamp" not in fit_df.columns:
        raise SystemExit("Splits have no `timestamp` column: re-run stage3_map_split.sh")
    as_of = int(target_df["timestamp"].min())
    check_profile_snapshot(as_of_timestamp=as_of, source_interactions=fit_df)  # nothing the agent can read is from the future

    user2id, item2id = load_mappings(data_paths.mapped_dir)
    if not any(ITEM_ID_SEPARATOR in key for key in islice(item2id, 1000)):
        raise SystemExit("Mapping has plain item ids; the tools need namespaced 'Domain::asin' ids (run the multi-domain pipeline)")
    id2item, id2user = {v: k_ for k_, v in item2id.items()}, {v: k_ for k_, v in user2id.items()}
    num_users = len(user2id)

    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    hist_size = np.bincount(fit_df["user_idx"].to_numpy(), minlength=num_users)
    seg_of = segment_users(target_by_user, hist_size, sparse_max)
    latest = fit_df[fit_df["user_idx"].isin(list(target_by_user))].sort_values("timestamp").drop_duplicates("user_idx", keep="last")
    last_item_of = dict(zip(latest["user_idx"].tolist(), latest["item_idx"].tolist()))

    # ---- corpus + models + tools
    print("Build corpus")
    corpus, _, coverage = build_corpus(meta_files, item2id, True, float(cfg["min_metadata_coverage"]))

    print("Fit ItemKNN on fit data")
    knn = ItemKNNRecommender(int(baselines["item_knn"]["k"])).fit(fit_df[["user_idx", "item_idx"]])
    logger = ToolCallLogger()  # shared; cleared after every request so it never grows
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, fit_df, corpus, logger=logger, as_of_timestamp=as_of)

    runners: dict[str, Any] = {}
    if "type1" in agents:
        runners["type1"] = Type1Agent(tools.item_cf, tools.reco, tools.query)
    if any(a in PLANNER_AGENTS for a in agents):
        llm = build_llm_provider(load_config("agent/llm"))
        if not llm.health_check():
            raise SystemExit("LLM health check failed: check configs/agent/llm.yaml and LLM_API_KEY (or run with --agents baseline,type1)")
        runners["planner"] = PlanExecutor(llm, tools.for_planner())
        runners["planner_memory"] = PlanExecutor(llm, tools.for_planner_memory())

    # ---- requests (deterministic given the seed) and the trajectory file
    requests = build_requests(
        seg_of=seg_of, target_by_user=target_by_user, last_item_of=last_item_of, id2user=id2user, id2item=id2item,
        item2id=item2id, corpus=corpus, per_segment=per_segment, n_ambiguous=int(cfg["n_ambiguous"]),
        language=cfg["language"], k=k, price_slack=float(cfg["price_slack"]), price_round_to=float(cfg["price_round_to"]),
        rng=np.random.default_rng(seed),
    )
    counts = pd.Series([f"{r.kind}/{r.segment}" for r in requests]).value_counts().sort_index()
    print("requests:", ", ".join(f"{name}={n}" for name, n in counts.items()), f"| agents: {agents}")
    text_of = {r.request_id: r.text for r in requests}

    traj_path = data_paths.log_dir / cfg["trajectory_file"]
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    done: dict[tuple[str, str], dict[str, Any]] = {}
    if args.resume and traj_path.exists():
        for line in traj_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if text_of.get(rec["request_id"]) == rec["text"] and rec["agent"] in agents:  # drop stale records
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
                    traj = run_planner(runners[agent], request, agent, k)
                else:
                    traj = empty_trajectory(request, agent, [])
                    started = time.perf_counter()
                    if agent == "baseline":
                        traj["recommended"] = [id2item[i] for i in knn.recommend(request.user_idx, k)[:k] if i in id2item]
                    else:
                        out = runners["type1"].recommend(request.user_id, [request.seed_item_id], top_k=k)
                        if out["ok"]:
                            traj["recommended"] = [it["item_id"] for it in out["items"]][:k]
                        else:
                            traj["error"] = f"{out.get('stage')}: {out.get('error')}"
                    traj["wall_seconds"] = round(time.perf_counter() - started, 3)
                logger.records.clear()
                trajectories.append(traj)
                sink.write(json.dumps(traj, ensure_ascii=False) + "\n")
                sink.flush()
                errors_in_a_row = errors_in_a_row + 1 if traj["provider_error"] else 0
                print(f"[{len(trajectories)}/{total}] {agent:<14} {request.request_id:<22} rec={len(traj['recommended']):>2} "
                      f"steps={len(traj['steps'])} {traj['wall_seconds']:.1f}s" + (f"  ERROR {traj['error'][:80]}" if traj["error"] else ""))
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

    exp_dir = save_experiment(
        next_experiment_dir(data_paths.experiments_dir / cfg["experiments_subdir"]),
        config={"agents": agents, "k": k, "per_segment": per_segment, "n_ambiguous": cfg["n_ambiguous"], "language": cfg["language"],
                "price_slack": cfg["price_slack"], "price_round_to": cfg["price_round_to"], "sparse_max": sparse_max,
                "item_knn_k": baselines["item_knn"]["k"], "llm_model": load_config("agent/llm").get("model")},
        metrics={"k": k, "summary": summary},
        seed=seed,
        dataset_info={"splits_dir": str(data_paths.splits_dir), "eval_on": args.eval_on, "num_users": num_users,
                      "num_items": len(item2id), "metadata_coverage": round(coverage, 4), "n_requests": len(requests),
                      "profile_as_of_timestamp": as_of},
        runtime_seconds=time.time() - t_start,
        notes=(f"Kinds {list(ORACLE_KINDS)} take their category/price constraints from held-out items: an ORACLE upper bound, "
               "never report them as real-query results. 'similar' and 'personalized' use fit history only. "
               "Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting."),
    )
    shutil.copyfile(traj_path, exp_dir / "trajectories.jsonl")
    (exp_dir / "requests.jsonl").write_text("".join(json.dumps(r.to_dict(), ensure_ascii=False) + "\n" for r in requests), encoding="utf-8")
    (exp_dir / "scored.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\nsaved -> {exp_dir}")


if __name__ == "__main__":
    main()
