"""Audit target losses from saved agent evaluation trajectories."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import yaml


TOOLS = ("SearchTool", "SimilarTool", "FilterTool")
PATHS = dict(zip(TOOLS, ("semantic", "itemcf", "sql")))


def read_rows(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def ids(rows):
    return [row["item_id"] if isinstance(row, dict) else row for row in rows]


def membership(data, key, target):
    rows = data.get(key)
    return target in ids(rows) if isinstance(rows, list) else None


def trace_target(item_id, steps, recommended, eligibility):
    calls = defaultdict(list)
    for index, step in enumerate(steps, start=1):
        data = step.get("data") or {}
        tool = step["tool"]
        if tool in TOOLS:
            generation = step.get("candidate_generation") or {}
            calls[tool].append({
                "step": index,
                "ok": step["ok"],
                "error_kind": step.get("error_kind"),
                "returned": membership(data, "candidates", item_id) if step["ok"] else None,
                "generated": (generation.get("targets") or {}).get(item_id),
                "generation_scope": generation.get("scope"),
            })

    rankers = [(index, step.get("data") or {}) for index, step in enumerate(steps, start=1)
               if step["tool"] == "RankTool" and step["ok"]]
    # Match the recommendation extractor's preference for the last non-empty rank result.
    selected = next(((i, data) for i, data in reversed(rankers) if data.get("ranked")), None)
    rank_step, ranker = selected or (rankers[-1] if rankers else (None, {}))
    ranked = ids(ranker.get("ranked") or [])
    rank = ranked.index(item_id) + 1 if item_id in ranked else None
    pool = membership(ranker, "candidate_item_ids", item_id)
    seen = membership(ranker, "excluded_seen", item_id)
    unscored = membership(ranker, "unscored_item_ids", item_id)
    if rank is not None or seen or unscored:
        pool = True
    top_k = item_id in recommended if recommended is not None else None
    retrieval = [call for group in calls.values() for call in group]
    returned = any(call["returned"] for call in retrieval)
    generated = True if returned or any(call["generated"] is True for call in retrieval) else None
    if retrieval and all(call["generated"] is False and call["returned"] is False for call in retrieval):
        generated = False

    if top_k:
        stage = "survived"
    elif rank is not None and top_k is False:
        stage = "top_k"
    elif seen:
        stage = "rank_excluded_seen"
    elif unscored:
        stage = "rank_unscored"
    elif rank_step is not None and pool is True and seen is False and unscored is False:
        stage = "rank_tool_cutoff"
    elif rank_step is not None and pool is False and returned:
        stage = "candidate_pool"
    elif returned:
        stage = "downstream_unknown"
    elif all(eligibility.get(path) is False for path in PATHS.values()):
        stage = "eligible_catalog"
    elif retrieval and all(call["returned"] is False for call in retrieval):
        stage = "generation_or_tool_output"
        if generated is True:
            stage = "retrieval_tool_output"
        elif generated is False:
            stage = "candidate_generation"
    elif not calls:
        stage = "retrieval_not_called"
    else:
        stage = "retrieval_unknown"

    return {
        "eligible_by_path": eligibility,
        "candidate_generation": generated,
        "retrieval_calls": {tool: calls[tool] for tool in TOOLS},
        "candidate_pool": pool,
        "rank_tool_step": rank_step,
        "rank_tool_selected": selected is not None,
        "rank": rank,
        "rank_excluded_seen": seen,
        "rank_unscored": unscored,
        "top_k": top_k,
        "stage": stage,
    }


def catalog_visibility(corpus, targets, policy):
    if corpus is None:
        return {}
    where = ""
    parameters = ()
    if policy.get("first_seen_filter"):
        where = " AND first_seen_ts <= ?"
        parameters = (policy["as_of_timestamp"],)
    with closing(sqlite3.connect(corpus.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        return {
            target: connection.execute(
                "SELECT 1 FROM items WHERE item_id = ?" + where, (target, *parameters)
            ).fetchone() is not None
            for target in targets
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--mapping", type=Path, required=True, help="Matching item2id.json")
    parser.add_argument("--corpus", type=Path, help="Matching corpus snapshot for SQL/Search eligibility")
    parser.add_argument("--trajectories", type=Path, help="Optional replay trajectories for the same requests")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    document = yaml.safe_load((args.run / "config.yaml").read_text(encoding="utf-8"))
    config = document["config"]
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    payload = json.dumps(sorted(mapping.items()), ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if digest != document["run"]["dataset"]["mapping_hash"]:
        parser.error("item mapping differs from the evaluation run")
    inverse = {index: item_id for item_id, index in mapping.items()}
    requests = {row["request_id"]: row for row in read_rows(args.run / "requests.jsonl")}
    scored_path = args.run / "scored.jsonl"
    scored = {(row["request_id"], row["agent"]): row for row in read_rows(scored_path)} if scored_path.exists() else {}
    trajectories = read_rows(args.trajectories or args.run / "trajectories.jsonl")
    policy = config["protocol"]["metadata_policy"]
    k = config["k"]
    catalog = catalog_visibility(
        args.corpus, {inverse[t] for request in requests.values() for t in request["targets"]}, policy
    )

    results = []
    summary = defaultdict(Counter)
    by_agent = defaultdict(Counter)
    unmatched = Counter()
    for trajectory in trajectories:
        request_id = trajectory["request_id"]
        agent = trajectory["agent"]
        request = requests.get(request_id)
        if request is None:
            unmatched[agent] += 1
            continue
        pool_detail = scored.get((request_id, agent), {}).get("target_pool_detail") or {}
        rec = trajectory.get("recommended")
        recommended = set(list(dict.fromkeys(rec))[:k]) if isinstance(rec, list) else None
        expected_hit = scored.get((request_id, agent), {}).get(f"hit_rate@{k}")
        if expected_hit is not None and recommended is not None:
            if bool(expected_hit) != any(inverse[t] in recommended for t in request["targets"]):
                raise ValueError(f"Top-{k} disagrees with scored result for {request_id}/{agent}")
        for target in dict.fromkeys(request["targets"]):
            item_id = inverse[target]
            eligibility = dict.fromkeys(PATHS.values())
            if item_id in catalog:
                eligibility.update(sql=catalog[item_id], semantic=catalog[item_id])
            eligibility.update(pool_detail.get(str(target), {}))
            result = trace_target(item_id, trajectory.get("steps") or [], recommended, eligibility)
            summary[request["kind"]][result["stage"]] += 1
            by_agent[agent][result["stage"]] += 1
            results.append(dict(request_id=request_id, agent=agent, kind=request["kind"],
                                segment=request["segment"], target_idx=target, item_id=item_id, **result))

    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"run": args.run.as_posix(), "mapping_sha256": digest,
                   "corpus": args.corpus.as_posix() if args.corpus else None,
                   "catalog_cutoff": policy.get("as_of_timestamp"), "k": k,
                   "unmatched_trajectories": unmatched, "counts_by_kind": summary, "counts_by_agent": by_agent,
                   "targets": results}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
