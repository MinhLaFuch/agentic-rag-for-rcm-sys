
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sqlite3
import time
import unicodedata
import uuid

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STOPWORDS = frozenset("a an the for with and or of to in on at by from is are be i me my we our you your want need looking find get some any good best cheap new under over below".split())
MAX_QUERY_TOKENS = int(yaml.safe_load((PROJECT_ROOT / "configs/agent/tools.yaml").read_text(encoding="utf-8"))["tools"]["semantic_search"]["max_query_tokens"])


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


file_hash = digest


def mapping_hash(mapping):
    values = list(mapping.values())
    if any(type(v) is not int or v < 0 for v in values) or sorted(values) != list(range(len(values))):
        raise ValueError("mapping indices must be unique contiguous nonnegative integers")
    payload = json.dumps(sorted((str(k), v) for k, v in mapping.items()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tokenize(query):
    try:
        query.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("normalized retrieval query must be ASCII") from exc
    words = re.findall(r"[a-z0-9][a-z0-9-]*", query.lower())
    return list(dict.fromkeys(w for w in words if len(w) > 1 and w not in STOPWORDS and not w.replace("-", "").isdigit()))[:MAX_QUERY_TOKENS]


def _history_title_query(title):
    title = title.translate(str.maketrans({"®": " ", "™": " ", "©": " ", "–": "-", "—": "-", "’": "'", "‘": "'"}))
    decomposed = unicodedata.normalize("NFKD", title)
    query = " ".join("".join(c if ord(c) < 128 else " " for c in decomposed if not unicodedata.combining(c)).split())
    return query


def _paths(tag):
    config = yaml.safe_load((PROJECT_ROOT / "configs/path/data_paths.yaml").read_text(encoding="utf-8"))["paths"]
    paths = {key: PROJECT_ROOT / value for key, value in config.items()}
    corpus_name = f"corpus_{tag}.sqlite"
    tagged_corpus = paths["corpus_dir"] / tag
    flat_corpus = paths["corpus_dir"]
    paths["corpus_file"] = tagged_corpus if (tagged_corpus / corpus_name).exists() else flat_corpus
    return paths


def _verify_source(source):
    hashes = json.loads((source / "artifact_hashes.json").read_text(encoding="utf-8"))
    required = {"config.yaml", "metrics.json", "records.jsonl", "requests.jsonl"}
    if not required <= hashes.keys():
        raise ValueError("source experiment has an incomplete artifact manifest")
    for name, expected in hashes.items():
        path = (source / name).resolve()
        if path.parent != source.resolve() or file_hash(path) != expected:
            raise ValueError(f"source artifact provenance mismatch: {name}")
    return hashes


def _top_exact(query, vectors, item_keys, valid, seen, limit, block_rows):
    """Exact cosine top-k over every valid unseen catalog row, with stable ties."""
    best_ids = np.empty(0, dtype=np.int64)
    best_scores = np.empty(0, dtype=np.float32)
    seen = set(seen)
    for start in range(0, len(item_keys), block_rows):
        stop = min(start + block_rows, len(item_keys))
        mask = np.array(valid[start:stop], dtype=bool, copy=True)
        if seen:
            mask &= np.fromiter((item not in seen for item in item_keys[start:stop]),
                                dtype=np.bool_, count=stop-start)
        local = np.flatnonzero(mask)
        if not len(local):
            continue
        scores = vectors[start+local] @ query
        ids = start + local
        if len(scores) > limit:
            pick = np.lexsort((item_keys[ids], -scores))[:limit]
            ids, scores = ids[pick], scores[pick]
        best_ids = np.concatenate((best_ids, ids))
        best_scores = np.concatenate((best_scores, scores))
        if len(best_ids) > limit:
            pick = np.lexsort((item_keys[best_ids], -best_scores))[:limit]
            best_ids, best_scores = best_ids[pick], best_scores[pick]
    order = np.lexsort((item_keys[best_ids], -best_scores))
    best_ids, best_scores = best_ids[order][:limit], best_scores[order][:limit]
    return [int(x) for x in best_ids], [float(x) for x in best_scores]


def _bm25(conn, query, seen, limit, timeout_seconds):
    tokens = _tokenize(query)
    if not tokens:
        return [], [], "no_searchable_title_tokens"
    match = " OR ".join('"' + token + '"' for token in tokens)
    excluded = sorted(seen)
    where = "items.item_id NOT IN (" + ",".join("?" for _ in excluded) + ")" if excluded else "1=1"
    sql = ("SELECT items.item_id, -bm25(items_fts) AS score "
           "FROM items_fts JOIN items ON items.rowid=items_fts.rowid "
           f"WHERE items_fts MATCH ? AND {where} "
           "ORDER BY score DESC, items.rating_number DESC, items.item_id LIMIT ?")
    deadline = [time.monotonic() + timeout_seconds]
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline[0]), 10000)
    try:
        rows = conn.execute(sql, [match, *excluded, limit]).fetchall()
    except sqlite3.OperationalError as exc:
        if "interrupt" in str(exc).lower():
            raise TimeoutError(f"BM25 query exceeded {timeout_seconds}s") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
    return [r[0] for r in rows], [float(r[1]) for r in rows], None


def _combine(cf, content, budget):
    out = []
    seen = set()
    for idx in cf + content:
        idx = int(idx)
        if idx not in seen:
            out.append(idx); seen.add(idx)
    if len(out) > budget:
        raise ValueError("candidate union exceeds the preregistered budget")
    return out


def _user_metrics(rows, item_count):
    eligible = [r for r in rows if r["targets"]]
    if not eligible:
        return dict(users=len(rows), eligible_users=0, candidate_recall=None,
                    candidate_coverage=None, hit_rate=None, mean_candidate_set_size=None,
                    catalog_coverage=0.0, empty_ground_truth=len(rows))
    recalls, hits, retrieved, targets, returned, sizes = [], 0, 0, 0, set(), []
    for row in eligible:
        candidates, gt = row["candidates"], set(row["targets"])
        found = len(set(candidates) & gt)
        recalls.append(found / len(gt)); hits += found; targets += len(gt)
        retrieved += found; returned.update(candidates); sizes.append(len(candidates))
    return dict(users=len(rows), eligible_users=len(eligible), empty_ground_truth=len(rows)-len(eligible),
                candidate_recall=float(np.mean(recalls)), candidate_coverage=retrieved/targets,
                hit_rate=float(np.mean([x > 0 for x in recalls])),
                mean_candidate_set_size=float(np.mean(sizes)), catalog_coverage=len(returned)/item_count,
                unique_items_retrieved=len(returned), target_interactions=targets)


def _paired_ci(left, right, seed, samples):
    a = np.asarray(left, dtype=np.float64); b = np.asarray(right, dtype=np.float64)
    delta = a-b
    if not len(delta):
        return dict(mean_delta=None, paired95_ci=None)
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=np.float64)
    for start in range(0, samples, 500):
        n = min(500, samples-start)
        indexes = rng.integers(0, len(delta), size=(n, len(delta)))
        means[start:start+n] = delta[indexes].mean(axis=1)
    return dict(mean_delta=float(delta.mean()), paired95_ci=np.percentile(means, [2.5, 97.5]).tolist(),
                improved=int((delta > 0).sum()), worse=int((delta < 0).sum()), unchanged=int((delta == 0).sum()))


def _segment_metrics(rows, item_count, seed, samples):
    grouped = defaultdict(lambda: defaultdict(list))
    user_recall = defaultdict(dict)
    for row in rows:
        segment = str(row["history_unique_items"])
        grouped[segment][row["policy"]].append(dict(candidates=row["candidates"], targets=row["targets"]))
        targets = set(row["targets"])
        if targets:
            user_recall[(segment, row["user_idx"])][row["policy"]] = len(set(row["candidates"]) & targets) / len(targets)
    summaries = {seg: {name: _user_metrics(values, item_count) for name, values in policies.items()}
                 for seg, policies in grouped.items()}
    paired = defaultdict(lambda: defaultdict(list))
    for (segment, user), recalls in user_recall.items():
        if {"dense", "bm25", "cf_plus_dense", "cf_plus_bm25"} <= recalls.keys():
            paired["dense_vs_bm25"][segment].append((recalls["dense"], recalls["bm25"]))
            paired["cf_plus_dense_vs_cf_plus_bm25"][segment].append((recalls["cf_plus_dense"], recalls["cf_plus_bm25"]))
    paired_summary = {comparison: {segment: _paired_ci([x[0] for x in values], [x[1] for x in values], seed, samples)
                                   for segment, values in segments.items()}
                      for comparison, segments in paired.items()}
    return summaries, paired_summary


def evaluate(args):
    started = time.perf_counter()
    source_hashes = _verify_source(args.source)
    source_cfg = yaml.safe_load((args.source / "config.yaml").read_text(encoding="utf-8"))
    dataset = source_cfg["run"]["dataset"]
    if dataset["eval_on"] != "validation" or dataset["tag"] != "multi_domain":
        raise ValueError("this protocol requires the fixed multi_domain validation source")
    manifest_path = args.embeddings / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = manifest["identity"]
    if manifest.get("status") != "complete" or manifest.get("quality_evaluated") is not False:
        raise ValueError("semantic embedding manifest must be complete and retrieval-unscored")
    for name, expected in manifest["artifact_hashes"].items():
        if digest(args.embeddings / name) != expected:
            raise ValueError(f"embedding artifact hash mismatch: {name}")
    if identity["source_hashes"] != source_hashes:
        raise ValueError("embeddings were built from a different source experiment")
    if identity["mapping_hash"] != dataset["mapping_hash"]:
        raise ValueError("embedding/source mapping hash mismatch")
    paths = _paths(dataset["tag"])
    mapped_dir = paths["mapped_dir"] / dataset["tag"]
    corpus_path = args.corpus or paths["corpus_file"] / f"corpus_{dataset['tag']}.sqlite"
    if file_hash(corpus_path) != identity["corpus_sha256"]:
        raise ValueError("SQLite corpus differs from the exact snapshot used for embeddings")
    users = json.loads((mapped_dir / "user2id.json").read_text(encoding="utf-8"))
    item2id = json.loads((mapped_dir / "item2id.json").read_text(encoding="utf-8"))
    users = {str(k): int(v) for k, v in users.items()}
    item2id = {str(k): int(v) for k, v in item2id.items()}
    if mapping_hash(item2id) != dataset["mapping_hash"] or mapping_hash(users) != dataset["user_mapping_hash"]:
        raise ValueError("user/item mappings differ from the source experiment")
    if file_hash(paths["splits_dir"] / dataset["tag"] / "train.parquet") != dataset["split_files"]["train"]["sha256"]:
        raise ValueError("train split changed since the cohort was selected")
    if file_hash(paths["splits_dir"] / dataset["tag"] / "validation.parquet") != dataset["split_files"]["validation"]["sha256"]:
        raise ValueError("validation split changed since the cohort was selected")
    inverse = {idx: item for item, idx in item2id.items()}

    cohort_manifest = None
    if args.cohort:
        cohort_manifest_path = args.cohort / "cohort_manifest.json"
        cohort_manifest = json.loads(cohort_manifest_path.read_text(encoding="utf-8"))
        if (cohort_manifest.get("status") != "complete" or cohort_manifest.get("seed") != args.seed or
                cohort_manifest.get("users") != args.users or
                cohort_manifest.get("source", {}).get("semantic_anchor_hashes") != source_hashes):
            raise ValueError("confirmation cohort manifest/anchor protocol mismatch")
        cohort_requests_path = args.cohort / "requests.jsonl"
        if digest(cohort_requests_path) != cohort_manifest.get("requests_sha256"):
            raise ValueError("confirmation cohort request hash mismatch")
        ranking_source = Path(cohort_manifest["source"]["ranking_source"])
        ranking_config = ranking_source / "config.yaml"
        if digest(ranking_config) != cohort_manifest["source"]["ranking_config_sha256"]:
            raise ValueError("ranking cohort source config changed after cohort freeze")
        for name, expected in cohort_manifest["source"]["ranking_artifact_hashes"].items():
            if digest(ranking_source / name) != expected:
                raise ValueError(f"ranking cohort source artifact changed: {name}")
        itemknn_path = Path(cohort_manifest["item_knn"]["path"])
        if digest(itemknn_path) != cohort_manifest["item_knn"]["sha256"] or digest(itemknn_path.with_suffix(".meta.json")) != cohort_manifest["item_knn"]["meta_sha256"]:
            raise ValueError("ItemKNN artifact changed after cohort freeze")
        if cohort_manifest["split_hashes"] != {k: dataset["split_files"][k]["sha256"] for k in ("train", "validation")}:
            raise ValueError("cohort split provenance differs from embedding/source dataset")
        requests_path = cohort_requests_path
    else:
        requests_path = args.source / "requests.jsonl"
    requests = [json.loads(line) for line in requests_path.open(encoding="utf-8")]
    by_user = {int(r["user_idx"]): r for r in requests}
    if len(by_user) != args.users or len(requests) != args.users:
        raise ValueError("cohort user count does not match the fixed protocol")
    rows_by_variant = defaultdict(dict)
    if not args.cohort:
        for line in (args.source / "records.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            if row.get("variant") in {"cf_1", "cf_bm25_rrf"}:
                u = int(row["user_idx"])
                if u in rows_by_variant[row["variant"]]:
                    raise ValueError("duplicate user/variant in source records")
                rows_by_variant[row["variant"]][u] = row
        if any(set(rows_by_variant[v]) != set(by_user) for v in ("cf_1", "cf_bm25_rrf")):
            raise ValueError("fixed source user cohort incomplete")
    elif any(not 1 <= len({int(h["item_idx"]) for h in r["history"]}) <= 4 for r in requests):
        raise ValueError("confirmation cohort is not sparse (expected 1-4 unique fit items)")

    ids = json.loads((args.embeddings / "item_ids.json").read_text(encoding="utf-8"))
    if len(ids) != manifest["rows"] or len(set(ids)) != len(ids) or ids != sorted(item2id, key=str):
        raise ValueError("embedding row order is not the complete sorted item mapping")
    if hashlib.sha256((args.embeddings / "item_ids.json").read_bytes()).hexdigest() != manifest["item_id_row_order_sha256"]:
        raise ValueError("embedding row order hash mismatch")
    if set(ids) != set(item2id):
        raise ValueError("embedding catalog item set differs from item mapping")
    item_ids = np.asarray([item2id[item] for item in ids], dtype=np.int64)
    vectors = np.load(args.embeddings / "vectors.npy", mmap_mode="r")
    valid = np.load(args.embeddings / "valid.npy", mmap_mode="r")
    if vectors.shape != (len(ids), identity["dimensions"]) or vectors.dtype != np.float32:
        raise ValueError("embedding matrix dimensions/dtype mismatch")
    if valid.shape != (len(ids),) or valid.dtype != np.bool_ or int(valid.sum()) != manifest["valid_rows"]:
        raise ValueError("embedding validity mask mismatch")
    if not valid.all():
        raise ValueError("invalid embedding rows exist; this catalog protocol requires a complete valid index")

    lock_path = args.encoder_lock or args.embeddings.parent / "encoder_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if digest(lock_path) != identity["encoder_lock_sha256"]:
        raise ValueError("encoder lock differs from embedding build")
    snapshot = Path(lock["snapshot"])
    for name, expected in lock["model_files"].items():
        if digest(snapshot / name) != expected:
            raise ValueError(f"locked encoder model file changed: {name}")
    pinned_env = identity["environment"]
    if platform.python_version() != pinned_env["python"]:
        raise ValueError(f"Python version mismatch: need {pinned_env['python']}, got {platform.python_version()}")
    mismatches = []
    for package, expected in pinned_env["packages"].items():
        # This evaluator intentionally does not import/install the editable
        # project distribution; all encoder and numeric dependencies stay pinned.
        if package.lower() == "ecom-agentic-recsys":
            continue
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            mismatches.append((package, expected, actual))
    if mismatches:
        summary = "; ".join(f"{name}=={expected} (found {actual or 'missing'})" for name, expected, actual in mismatches[:10])
        raise ValueError("semantic environment differs from the embedding lock: " + summary)

    conn = sqlite3.connect(corpus_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("SQLite quick_check failed")
    catalog_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0]
    if catalog_count != len(item2id) or fts_count != catalog_count:
        raise ValueError("SQLite items/FTS catalog count mismatch")

    # Read only metadata and inputs derived from fit history. Targets are held aside for scoring.
    pending, all_rows = [], []
    for u in sorted(by_user):
        request = by_user[u]
        history = request["history"]
        if not history:
            raise ValueError(f"missing fit history for user {u}")
        latest = max(history, key=lambda x: (int(x["timestamp"]), int(x["item_idx"])))
        latest_id = inverse[int(latest["item_idx"])]
        if args.cohort:
            cf_source = request.get("cf_candidates")
            if cf_source is None or len(cf_source) > args.source_quota or len(set(cf_source)) != len(cf_source):
                raise ValueError(f"invalid frozen one-seed CF candidate list for user {u}")
            targets = sorted(set(map(int, request["targets"])))
            saved_bm25, saved_bm25_scores = None, None
        else:
            base = rows_by_variant["cf_1"][u]
            hybrid = rows_by_variant["cf_bm25_rrf"][u]
            cf_events = [event for event in base.get("events", [])
                         if event.get("tool") == "ItemCFTool" and event.get("ok")]
            if len(cf_events) != 1 or [x["item_id"] for x in cf_events[0]["data"]["candidates"]] != base["candidates"]:
                raise ValueError(f"source CF retrieval failure or candidate-list mismatch for user {u}")
            if hybrid.get("status") != "ok":
                raise ValueError(f"source CF+BM25 chain failed for user {u}")
            for field in ("targets", "seeds", "candidate_budget", "history_unique_items"):
                if base[field] != hybrid[field]:
                    raise ValueError(f"paired source protocol mismatch for user {u}: {field}")
            if int(base["candidate_budget"]) != args.union_budget:
                raise ValueError("source candidate budget differs from requested fixed budget")
            if base.get("seeds") != [latest_id]:
                raise ValueError(f"saved one-seed CF query is not the latest fit item for user {u}")
            cf_source = hybrid["source_candidates"]["item_cf"]
            if cf_source != base["candidates"]:
                raise ValueError(f"CF baseline candidates changed in hybrid source for user {u}")
            search_events = [event for event in hybrid.get("source_events", [])
                             if event.get("tool") == "SemanticSearchTool" and event.get("ok")]
            if len(search_events) != 1:
                raise ValueError(f"expected one successful saved BM25 search for user {u}")
            saved_search_rows = search_events[0]["data"]["candidates"]
            if [x["item_id"] for x in saved_search_rows] != hybrid["source_candidates"]["bm25"]:
                raise ValueError(f"saved BM25 IDs disagree across source fields for user {u}")
            prior_query = hybrid.get("query_provenance", {}).get("sent")
            source_items = hybrid.get("query_provenance", {}).get("source_item_ids")
            title_row = conn.execute("SELECT title FROM items WHERE item_id=?", (latest_id,)).fetchone()
            if title_row is None or source_items != [latest_id] or prior_query != _history_title_query(title_row[0] or ""):
                raise ValueError(f"saved runtime query does not reproduce from latest fit title for user {u}")
            targets = sorted(set(map(int, request["targets"])))
            if targets != sorted(set(map(int, base["targets"]))):
                raise ValueError(f"saved request ground truth differs from records for user {u}")
            saved_bm25 = hybrid["source_candidates"]["bm25"]
            saved_bm25_scores = [float(x["score"]) for x in saved_search_rows]
        title_row = conn.execute("SELECT title FROM items WHERE item_id=?", (latest_id,)).fetchone()
        if title_row is None:
            raise ValueError(f"latest fit item absent from SQLite snapshot: {latest_id}")
        title = title_row[0] or ""
        query = _history_title_query(title)
        seen = {inverse[int(x["item_idx"])] for x in history}
        cf = [item for item in cf_source if item not in seen][:args.source_quota]
        pending.append(dict(user_idx=u, user_id=request["user_id"], query=query, latest_item=latest_id,
                            seen=seen, cf=cf, targets=targets,
                            history_unique_items=len(seen), saved_bm25=saved_bm25,
                            saved_bm25_scores=saved_bm25_scores))
    conn.close()

    print(f"[encoder] encoding {len(pending)} latest-fit-title queries from locked local model", flush=True)
    import torch
    from sentence_transformers import SentenceTransformer
    torch.manual_seed(int(identity["seed"]))
    torch.set_num_threads(int(identity["threads"]))
    encoder = SentenceTransformer(str(snapshot), local_files_only=True, trust_remote_code=False, device="cpu")
    encoder.max_seq_length = int(identity["max_seq_length"])
    encoder.eval()
    encode_started = time.perf_counter()
    texts = [r["query"] for r in pending]
    encodable = [i for i, text in enumerate(texts) if text.strip()]
    query_vectors = np.zeros((len(pending), identity["dimensions"]), dtype=np.float32)
    if encodable:
        query_vectors[encodable] = np.asarray(encoder.encode([texts[i] for i in encodable],
            batch_size=args.query_batch_size, normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False), dtype=np.float32)
    query_encode_seconds = time.perf_counter() - encode_started
    if query_vectors.shape != (len(pending), identity["dimensions"]) or not np.isfinite(query_vectors).all():
        raise ValueError("query encoder returned invalid vectors")
    if encodable and not np.allclose(np.linalg.norm(query_vectors[encodable], axis=1), 1.0, atol=1e-4):
        raise ValueError("query vectors are not normalized")

    conn = sqlite3.connect(corpus_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    timings = defaultdict(list)
    saved_bm25_equal = 0
    saved_bm25_scores_equal = 0
    candidates_path = args.output / "candidate_lists.jsonl"
    args.output.mkdir(parents=True, exist_ok=False)
    with candidates_path.open("x", encoding="utf-8") as stream:
        for pos, row in enumerate(pending, 1):
            begin = time.perf_counter()
            bm_ids, bm_scores, fallback = _bm25(conn, row["query"], row["seen"], args.source_quota, args.sqlite_timeout)
            timings["bm25_query_seconds"].append(time.perf_counter()-begin)
            bm = [item2id[i] for i in bm_ids]
            if bm_ids == row["saved_bm25"]:
                saved_bm25_equal += 1
                if len(bm_scores) == len(row["saved_bm25_scores"]) and np.allclose(
                        bm_scores, row["saved_bm25_scores"], rtol=1e-12, atol=1e-12):
                    saved_bm25_scores_equal += 1
            begin = time.perf_counter()
            if row["query"].strip():
                row_indices, de_scores = _top_exact(query_vectors[pos-1], vectors, np.asarray(ids), valid,
                    row["seen"], args.source_quota, args.block_rows)
                de_ids = [int(item_ids[i]) for i in row_indices]
            else:
                row_indices, de_scores = [], []
                de_ids = []
            timings["dense_exact_search_seconds"].append(time.perf_counter()-begin)
            cf_ids = [item2id[x] for x in row["cf"]]
            policies = {
                "bm25": bm,
                "dense": de_ids,
                "cf_plus_bm25": _combine(cf_ids, bm, args.union_budget),
                "cf_plus_dense": _combine(cf_ids, de_ids, args.union_budget),
            }
            for name, items in policies.items():
                if len(items) != len(set(items)) or len(items) > (args.source_quota if name in ("bm25", "dense") else args.union_budget):
                    raise ValueError(f"invalid candidate budget/deduplication in {name}")
                all_rows.append(dict(user_idx=row["user_idx"], policy=name, candidates=items,
                                     targets=row["targets"], history_unique_items=row["history_unique_items"]))
            stream.write(json.dumps(dict(user_idx=row["user_idx"], user_id=row["user_id"],
                history_unique_items=row["history_unique_items"], latest_fit_item=row["latest_item"],
                query=row["query"], target_ids=row["targets"], seen_items=sorted(row["seen"]),
                cf_ids=cf_ids, bm25_ids=bm, bm25_scores=bm_scores, bm25_fallback=fallback,
                dense_ids=de_ids, dense_scores=de_scores, policies=policies), ensure_ascii=False) + "\n")
            if pos % 25 == 0 or pos == len(pending):
                rate = pos / (time.perf_counter()-started)
                print(f"[retrieval] {pos}/{len(pending)} users | {rate:.2f} users/s", flush=True)
    conn.close()

    if file_hash(corpus_path) != identity["corpus_sha256"]:
        raise ValueError("SQLite corpus changed during retrieval evaluation")
    for name, expected in manifest["artifact_hashes"].items():
        if digest(args.embeddings / name) != expected:
            raise ValueError(f"embedding artifact changed during retrieval evaluation: {name}")

    policy_rows = defaultdict(list)
    pair_recalls = defaultdict(list)
    for row in all_rows:
        policy_rows[row["policy"]].append(dict(candidates=row["candidates"], targets=row["targets"]))
        gt = set(row["targets"])
        pair_recalls[(row["user_idx"], row["policy"])].append(
            len(set(row["candidates"]) & gt) / len(gt) if gt else None)
    metrics = {name: _user_metrics(rows, len(item2id)) for name, rows in policy_rows.items()}
    metrics["latency"] = {}
    comparisons = {}
    for left, right in (("dense", "bm25"), ("cf_plus_dense", "cf_plus_bm25")):
        a, b = [], []
        for user in sorted(by_user):
            av, bv = pair_recalls[(user, left)][0], pair_recalls[(user, right)][0]
            if av is not None and bv is not None:
                a.append(av); b.append(bv)
        comparisons[f"{left}_vs_{right}"] = _paired_ci(a, b, args.seed, args.bootstrap_samples)
    for key, values in timings.items():
        metrics["latency"][key] = dict(mean=float(np.mean(values)), p50=float(np.percentile(values, 50)),
                                       p95=float(np.percentile(values, 95)))
    metrics["latency"]["query_encode_batch_seconds"] = query_encode_seconds
    metrics["latency"]["query_encode_amortized_seconds_per_user"] = query_encode_seconds/len(pending)
    metrics["latency"]["dense_total_amortized_seconds_per_user"] = (
        query_encode_seconds/len(pending) + metrics["latency"]["dense_exact_search_seconds"]["mean"])
    bm25_comparison_users=sum(row["saved_bm25"] is not None for row in pending)
    metrics["source_consistency"] = dict(users=len(pending), historical_bm25_comparison_users=bm25_comparison_users,
                                           saved_bm25_top25_exact_id_matches=saved_bm25_equal,
                                           saved_bm25_id_match_rate=(saved_bm25_equal/bm25_comparison_users if bm25_comparison_users else None),
                                           saved_bm25_exact_score_matches=saved_bm25_scores_equal,
                                           saved_bm25_score_match_rate=(saved_bm25_scores_equal/bm25_comparison_users if bm25_comparison_users else None),
                                           candidate_budget_union=args.union_budget,
                                           per_source_quota=args.source_quota)
    metrics["paired_candidate_recall"] = comparisons
    metrics["history_segments"], metrics["paired_candidate_recall_by_history"] = _segment_metrics(
        all_rows, len(item2id), args.seed, args.bootstrap_samples)
    metrics["qualification"] = ("independent 1000-user sparse validation sample relative to semantic exp_004; not an untouched holdout; retrieval-only"
                                 if cohort_manifest else "fixed 500-user development validation; retrieval-only; no ranking or production decision")
    metrics["runtime_seconds"] = time.perf_counter()-started

    config = dict(experiment_id=args.output.name, created_utc=datetime.now(timezone.utc).isoformat(),
        source=str(args.source.resolve()), source_hashes=source_hashes,
        confirmation_cohort=(dict(path=str(args.cohort.resolve()), manifest=cohort_manifest) if cohort_manifest else None),
        dataset=dict(tag=dataset["tag"], split=dataset["eval_on"], users=len(pending), seed=args.seed,
                     source_user_ids_sha256=hashlib.sha256(json.dumps(sorted(by_user)).encode()).hexdigest(),
                     train_sha256=dataset["split_files"]["train"]["sha256"],
                     validation_sha256=dataset["split_files"]["validation"]["sha256"],
                     mapping_hash=dataset["mapping_hash"], user_mapping_hash=dataset["user_mapping_hash"]),
        corpus=dict(path=str(corpus_path.resolve()), sha256=identity["corpus_sha256"], items=catalog_count,
                    fts_rows=fts_count, read_only=True),
        embeddings=dict(path=str(args.embeddings.resolve()), manifest_sha256=digest(manifest_path),
                        artifact_hashes=manifest["artifact_hashes"], model_id=identity["model_id"],
                        revision=identity["revision"], encoder_lock_sha256=identity["encoder_lock_sha256"],
                        dimensions=identity["dimensions"], dtype=identity["dtype"], normalized=True),
        protocol=dict(query="latest fit-history item title only; history_title_query/ascii_fold v1",
            target_used_for_query=False, seen_filter="all fit-history item IDs, applied to dense/BM25/CF",
            similarity="exact cosine over every valid catalog embedding; normalized float32", block_rows=args.block_rows,
            standalone_budget=args.source_quota, union_budget=args.union_budget,
            cf_source=("provenance-checked ItemKNN one-seed latest-item top-25 lists frozen from the same train-fit cache"
                       if cohort_manifest else "same saved one-seed CF candidate list as exp_004; first per-source quota after seen filter"),
            merge="stable CF-first deduplicated union; no refill", bm25="SQLite FTS5 BM25 on the exact embedding corpus snapshot",
            metadata_policy=identity["metadata_policy"], sqlite_timeout_seconds=args.sqlite_timeout,
            ranking="excluded", production_changed=False),
        environment=dict(python=identity["environment"]["python"], packages=identity["environment"]["packages"]))
    (args.output / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    hashes = {name: file_hash(args.output / name) for name in ("config.yaml", "metrics.json", "candidate_lists.jsonl")}
    (args.output / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--cohort", type=Path, help="frozen independent cohort from prepare_semantic_candidate_cohort.py")
    ap.add_argument("--embeddings", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--encoder-lock", type=Path)
    ap.add_argument("--users", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--source-quota", type=int, default=25)
    ap.add_argument("--union-budget", type=int, default=50)
    ap.add_argument("--block-rows", type=int, default=32768)
    ap.add_argument("--query-batch-size", type=int, default=64)
    ap.add_argument("--sqlite-timeout", type=float, default=5.0)
    ap.add_argument("--bootstrap-samples", type=int, default=10000)
    args = ap.parse_args()
    if args.users not in (500, 1000) or args.seed != 42 or (args.cohort and args.users != 1000) or (not args.cohort and args.users != 500) or min(args.source_quota, args.union_budget, args.block_rows,
                                                    args.query_batch_size, args.sqlite_timeout) <= 0:
        ap.error("protocol requires source=500 users or --cohort=1000 users, seed 42; sizes/timeouts must be positive")
    evaluate(args)


if __name__ == "__main__":
    main()
