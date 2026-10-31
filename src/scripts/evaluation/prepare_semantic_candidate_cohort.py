"""Freeze an independent sparse validation cohort and its one-seed CF lists."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import scipy.sparse as sp
import yaml
from package.config import get_data_paths

from semantic_candidate_eval import PROJECT_ROOT, _verify_source, digest, mapping_hash


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ranking-source", type=Path)
    ap.add_argument("--semantic-source", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--users", type=int, default=1000)
    ap.add_argument("--skip-prefix", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    data_paths = get_data_paths("multi_domain")
    args.ranking_source = args.ranking_source or data_paths.experiments_dir / "ranking_eval" / "exp_009"
    args.semantic_source = args.semantic_source or data_paths.experiments_dir / "sparse_content_eval" / "exp_004"
    if args.users != 1000 or args.skip_prefix != 500 or args.seed != 42:
        ap.error("confirmation cohort is fixed to sparse list positions [500:1500], seed 42, 1000 users")

    ranking_cfg_path = args.ranking_source / "config.yaml"
    ranking_cfg = yaml.safe_load(ranking_cfg_path.read_text(encoding="utf-8"))
    ranking_artifacts = json.loads((args.ranking_source / "artifact_hashes.json").read_text(encoding="utf-8"))
    for name, expected in ranking_artifacts.items():
        if digest(args.ranking_source / name) != expected:
            raise ValueError(f"ranking source artifact hash mismatch: {name}")
    source_hashes = _verify_source(args.semantic_source)
    source_cfg = yaml.safe_load((args.semantic_source / "config.yaml").read_text(encoding="utf-8"))
    dataset = source_cfg["run"]["dataset"]
    ranking_dataset = ranking_cfg["run"]["dataset"]
    if dataset["tag"] != "multi_domain" or dataset["eval_on"] != "validation":
        raise ValueError("semantic anchor must be multi_domain validation")
    if ranking_dataset["tag"] != dataset["tag"] or ranking_dataset["eval_on"] != dataset["eval_on"]:
        raise ValueError("ranking cohort source dataset/split mismatch")
    for split in ("train", "validation"):
        expected = dataset["split_files"][split]["sha256"]
        if expected != ranking_dataset["split_files"][split]["sha256"]:
            raise ValueError(f"source split identity mismatch: {split}")
        if digest(dataset["split_files"][split]["path"]) != expected:
            raise ValueError(f"dataset split changed: {split}")

    selected_all = list(map(int, ranking_cfg["config"]["sampled_user_ids"]["sparse"]))
    if len(selected_all) != 5000 or len(set(selected_all)) != 5000:
        raise ValueError("ranking source must contain exactly 5000 fixed sparse users")
    selected = selected_all[args.skip_prefix:args.skip_prefix+args.users]
    prior = [json.loads(line) for line in (args.semantic_source / "requests.jsonl").open(encoding="utf-8")]
    prior_ids = [int(row["user_idx"]) for row in prior]
    if prior_ids != selected_all[:args.skip_prefix]:
        raise ValueError("prior semantic cohort is not the exact sparse-list prefix; independent sample cannot be established")
    if set(selected) & set(prior_ids) or len(selected) != args.users:
        raise ValueError("new confirmation sample overlaps the prior semantic cohort or is incomplete")

    mapped_dir = get_data_paths(dataset["tag"]).mapped_dir
    users = {str(k): int(v) for k, v in json.loads((mapped_dir / "user2id.json").read_text(encoding="utf-8")).items()}
    item2id = {str(k): int(v) for k, v in json.loads((mapped_dir / "item2id.json").read_text(encoding="utf-8")).items()}
    if mapping_hash(users) != dataset["user_mapping_hash"] or mapping_hash(item2id) != dataset["mapping_hash"]:
        raise ValueError("mapping provenance mismatch")
    user2id = {v: k for k, v in users.items()}
    id2item = {v: k for k, v in item2id.items()}
    selected_set = set(selected)
    selected_arr = np.asarray(selected, dtype=np.int64)

    histories = defaultdict(list)
    train_path = Path(dataset["split_files"]["train"]["path"])
    parquet = pq.ParquetFile(train_path)
    for batch in parquet.iter_batches(columns=["user_idx", "item_idx", "timestamp"], batch_size=1_000_000):
        u = batch.column(0).to_numpy(zero_copy_only=False)
        mask = np.isin(u, selected_arr)
        if not mask.any():
            continue
        i = batch.column(1).to_numpy(zero_copy_only=False)[mask]
        t = batch.column(2).to_numpy(zero_copy_only=False)[mask]
        for uid, item, timestamp in zip(u[mask], i, t):
            histories[int(uid)].append((int(item), int(timestamp)))

    validation_targets = defaultdict(set)
    validation_path = Path(dataset["split_files"]["validation"]["path"])
    parquet = pq.ParquetFile(validation_path)
    for batch in parquet.iter_batches(columns=["user_idx", "item_idx"], batch_size=1_000_000):
        u = batch.column(0).to_numpy(zero_copy_only=False)
        mask = np.isin(u, selected_arr)
        if not mask.any():
            continue
        i = batch.column(1).to_numpy(zero_copy_only=False)[mask]
        for uid, item in zip(u[mask], i):
            validation_targets[int(uid)].add(int(item))

    itemknn_path = None
    for item in source_cfg["config"]["identity"]["source"]:
        if item["path"].endswith("fit_item_knn.npz"):
            itemknn_path = Path(item["path"])
            if digest(itemknn_path) != item["sha256"]:
                raise ValueError("ItemKNN file differs from semantic source provenance")
            break
    if itemknn_path is None:
        raise ValueError("semantic source has no ItemKNN artifact reference")
    meta_path = itemknn_path.with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if digest(meta_path) != next(x["sha256"] for x in source_cfg["config"]["identity"]["source"] if x["path"] == str(meta_path)):
        raise ValueError("ItemKNN metadata sidecar hash mismatch")
    prov = meta["provenance"]
    if (prov.get("tag") != dataset["tag"] or prov.get("eval_on") != "validation" or
        prov.get("fit_splits") != ["train"] or prov.get("item_mapping_hash") != dataset["mapping_hash"] or
        prov.get("user_mapping_hash") != dataset["user_mapping_hash"] or
        meta.get("artifact_sha256") != digest(itemknn_path)):
        raise ValueError("ItemKNN artifact provenance is incompatible with this validation protocol")

    similarity = sp.load_npz(itemknn_path).tocsr()
    if similarity.shape != (len(item2id), len(item2id)) or meta.get("k") != 20:
        raise ValueError("ItemKNN dimensions or neighbor cap mismatch")
    prior_requests = {int(r["user_idx"]): r for r in prior}
    prior_cf = {}
    for line in (args.semantic_source / "records.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        if row.get("variant") == "cf_1":
            prior_cf[int(row["user_idx"])] = row["candidates"]
    if set(prior_cf) != set(prior_ids):
        raise ValueError("prior one-seed CF source does not cover its 500 users")

    out_rows = []
    for uid in selected:
        events = histories.get(uid, [])
        if not events:
            raise ValueError(f"sparse cohort user has no train history: {uid}")
        seen_indices = {item for item, _ in events}
        if not 1 <= len(seen_indices) <= 4:
            raise ValueError(f"sampled sparse user history is outside 1-4: {uid} has {len(seen_indices)}")
        latest_idx, _ = max(events, key=lambda x: (x[1], x[0]))
        if latest_idx not in id2item:
            raise ValueError("latest fit item missing from item mapping")
        simrow = similarity.getrow(latest_idx)
        cols = simrow.indices
        scores = simrow.data
        keep = cols != latest_idx
        cols, scores = cols[keep], scores[keep]
        order = np.lexsort((cols, -scores))[:25]
        cf_candidates = [id2item[int(i)] for i in cols[order]]
        if uid in prior_requests:
            old_history = {(int(h["item_idx"]), int(h["timestamp"])) for h in prior_requests[uid]["history"]}
            if old_history != set(events):
                raise ValueError(f"fit history changed for overlapping user {uid}")
            targets_old = set(map(int, prior_requests[uid]["targets"]))
            targets_new = validation_targets.get(uid, set()) - seen_indices
            if targets_old != targets_new:
                raise ValueError(f"novel validation targets changed for overlapping user {uid}")
            if cf_candidates != prior_cf[uid]:
                raise ValueError(f"one-seed ItemKNN candidates fail to reproduce for prior user {uid}")
        novel_targets = sorted(validation_targets.get(uid, set()) - seen_indices)
        out_rows.append(dict(user_idx=uid, user_id=user2id[uid],
            history=[dict(item_idx=i, timestamp=t) for i, t in events],
            targets=novel_targets, cf_candidates=cf_candidates))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f"cohort output exists; choose a new path: {args.output}")
    args.output.mkdir()
    requests_path = args.output / "requests.jsonl"
    with requests_path.open("x", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = dict(status="complete", users=args.users, seed=args.seed,
        selection="ranking_eval/exp_009 sparse sample positions [500:1500]; fixed source seed 42",
        prior_semantic_cohort_users=args.skip_prefix, overlap_with_prior=0,
        sparse_history_definition="1-4 unique train items", target_policy="validation unique items minus all fit-history items",
        item_knn=dict(path=str(itemknn_path.resolve()), sha256=digest(itemknn_path),
                      meta_sha256=digest(meta_path), k=meta["k"], fit_split="train",
                      train_split_sha256=dataset["split_files"]["train"]["sha256"]),
        source=dict(ranking_source=str(args.ranking_source.resolve()), ranking_config_sha256=digest(ranking_cfg_path),
                    ranking_artifact_hashes=ranking_artifacts, semantic_anchor=str(args.semantic_source.resolve()),
                    semantic_anchor_hashes=source_hashes),
        split_hashes={k: dataset["split_files"][k]["sha256"] for k in ("train", "validation")},
        mapping_hashes=dict(users=dataset["user_mapping_hash"], items=dataset["mapping_hash"]),
        requests_sha256=digest(requests_path), candidate_generation="ItemCFTool one latest fit item, top_k=25, input seed excluded")
    (args.output / "cohort_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Prepared {len(out_rows)} independent sparse users at {args.output}", flush=True)


if __name__ == "__main__":
    main()
