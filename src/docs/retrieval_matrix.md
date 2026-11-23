# Paired query, retrieval, fusion and ranking matrix

## Scope and compatibility

The audited-bundle entry point is `scripts/evaluation/candidate_recall.py --matrix-config ...`.
It uses the completed full embedding artifact, verified audit profile and validation splits.
The older `semantic_candidate_eval.py` remains a locked legacy source-experiment evaluator;
its frozen source checks are deliberately preserved. New experiments use the matrix path.
Without `--matrix-config`/`--matrix-from`, candidate evaluation retains the existing path.
Neither SearchTool's public output nor the CandidateScorer protocol changes.

Implementation and synthetic tests are prepared; tests and real-data evaluation have not
been run in this change. All new scorer/query settings remain opt-in. No production default
or previously published experiment is replaced.

## Query representation

`build_history_query` accepts fit events only: item ID, timestamp and visible metadata title.
It excludes timestamps at/after the prediction cutoff, sorts timestamp descending then item
ID ascending, and deduplicates history items by their latest event.

- `latest_title`: one latest item title, including the existing empty-title/no-input behavior.
- `multi_history`: up to max_history_items titles; equal-weight normalized dense centroid.
- `recency_weighted`: normalized dense centroid with weights decay**recency_rank.

BM25 receives the explicitly recorded newest-first concatenation. FTS OR matching does not
implement dense weights; repeated words do not pretend to weight BM25. Normalization is
explicit. Query components/weights/cutoff are persisted, so comparisons share the same users
and history. Targets are only used after query generation for metric labels. The raw default
is a latest-title control; reproducing an older ASCII-fold experiment requires configuring
the same normalization, cohort, metadata policy and tokenizer rather than comparing raw scores.

`HistoryQueryRetriever` is the shared runtime/evaluation adapter: construct with a BM25
SearchTool, vector store, encoder and the catalog IDs allowed by the active policy, then
call retrieve(history, seen=..., cutoff=..., mode=...). It does not alter SearchTool output.
Runtime callers must supply timestamped fit history and recompute eligibility when policy
or hard filters change. This change does not silently switch agent/demo defaults.

Dense exact search applies catalog eligibility and all seen exclusions BEFORE Top-K and
operates in blocks. Stable ties use item ID. It avoids the old global-shortlist-then-filter
failure, but remains an exact catalog scan; measure latency before deployment. Cold users
with no history have no semantic input. This matrix cannot prove cold-query quality without
an independent query/relevance dataset.

Eligibility setup enumerates the policy-visible TEMP items view in indexed ID ranges of
2,048 artifact rows, with progress logs. It never fetches the full catalog in one SQL call,
uses no OFFSET, and leaves the corpus authorizer and per-query timeout enabled. Failed
matrix outputs cannot be resumed; choose a fresh timestamp/output directory after a fix.

History metadata setup selects only the newest distinct pre-cutoff items needed by the
configured modes before reading titles. Its title-only lookup uses bounded indexed IN
queries and caches misses; it never joins/group-aggregates item_categories. All-history
seen filtering is retained independently, and metadata setup time is reported separately.

Matrix BM25 uses SearchTool's opt-in indexed_topk path with exact_count=False. It asks
FTS5 for rank-ordered prefixes, reads filtered metadata only for new row IDs in bounded
batches and expands prefixes until all boundary ties are covered. This retains the existing
score-desc/rating-desc/item-ID-asc order and hard filters without sorting every match.
No exact total match count is needed by the matrix (total_matches=None, already supported
by SearchTool). Default SearchTool calls remain unchanged. The exact scan cap is 131,072
rows; reaching it without an exactness proof or exceeding any SQL timeout fails the run,
rather than silently publishing approximate BM25 results. Large flat tie groups or very
restrictive filters may still need an explicit reviewed query/search-budget decision.

## Fusion and scoring

`fuse_candidates` supports RRF and weighted RRF, source-specific input caps (quotas), seen
exclusions, deduplication, deterministic item-ID ties, source rank attribution and a strict
output budget. Quotas are input caps, not guaranteed output allocations or refill targets.
Zero weights disable a source. Unknown source settings and invalid weights/budgets fail.

Matrix sources are CF, BM25, dense and BM25+dense hybrid. The primary fused list uses CF,
BM25 and dense directly; it does not count dense/BM25 a second time through hybrid. The
utility also accepts a hybrid source for explicit future ablations. Fixed CF history seeds
are shared across query modes, isolating query construction changes.

RankTool replays every frozen pool with:

- `baseline`: existing BaselineScorer unchanged.
- `cf_ties`: normalized popularity plus normalized retrieval RRF evidence break exact CF
  ties only. Every strict collaborative-score comparison is preserved. Request-local ordinal
  scores are not calibrated across candidate sets/requests. Cold/no-CF pools use secondary evidence.
- `additive_ablation`: explicitly allows secondary evidence to outweigh small CF differences;
  never a default deployment mode. Compare against cf_ties and baseline on the same pool.

Source evidence is computed from retrieval ranks, never relevance labels. EvidenceScorer
is request-scoped; callers must not reuse one user's evidence for another request. It conforms
to score/is_known_user/seen_items/has_personal_signal/num_items/name without extending RankTool.

## Outputs and metric interpretation

The matrix saves config/provenance, query components, seen IDs, targets and all source/fused
pools in candidate_sets.jsonl. The complete file is hashed in frozen.json BEFORE ranking.
Ranked lists, metrics and the completion artifact manifest are separate. Source failures stop
the run and cannot produce a completed quality report as if retrieval had succeeded.

Metrics include source/fused Recall@50/100/200 and hit rate; ranking Recall/NDCG/MRR/Hit at
K=5/10/20; paired bootstrap recall and ranking deltas; cold/sparse/warm breakdown; mean source
Jaccard overlap; no-input/query coverage; latency p50/p95. Means over the stratified sample
are not population-weighted. Bootstrap units are users, with a local seeded generator.
Seen target repeats are logged separately and excluded from both quality denominators;
novel targets outside the eligible catalog remain misses. Empty-target users are counted
and excluded from quality means, not turned into fake zero-recall users.

Timing separates source/query encode from RankTool. Dense latency includes query encoding.
retrieval_total includes CF, BM25, dense, hybrid/final fusion and query construction; it is
the serial research harness cost, not a production SLA. Repeated history modes warm OS/model
caches; record order and do not interpret one run as a cache-controlled latency study.

Gates initially have null thresholds and explicitly report not_set with passed=null. Set all
three before acceptance evaluation: minimum lower CI bound on fused Recall@100 improvement,
maximum matrix p95 latency and maximum segment recall regression. Missing paired/cohort
data reports insufficient_data. These gates measure retrieval acceptance; final recommendation
and deployment acceptance still require ranking/scorer ablations and independent cold queries.

## Local commands

Run tests before real-data evaluation, with profiles unset:

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"
Remove-Item Env:EVAL_BUNDLE_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:CONFIG_OVERLAY_PATH -ErrorAction SilentlyContinue
.\src\.venv-baseline\Scripts\python.exe -m pytest -q `
  src/tests/tools/evaluation/test_retrieval_matrix.py `
  src/tests/tools/evaluation/test_candidate_recall_protocol.py `
  src/tests/tools/retrieval src/tests/tools/ranking src/tests/config
```

If tests pass, start with 10 users/segment; increase only after reviewing runtime and errors:

```powershell
$env:EVAL_BUNDLE_PROFILE = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.profile.yaml").Path
$env:CONFIG_OVERLAY_PATH = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml").Path
$matrixStamp = Get-Date -Format "yyyyMMdd_HHmmss"
.\src\.venv-semantic\Scripts\python.exe -u -c "import torch,runpy; runpy.run_path('src/scripts/evaluation/candidate_recall.py',run_name='__main__')" `
  --tag multi_domain_v2_audit_20261030 --eval-on validation --query-mode history `
  --retrieval hybrid --per-segment 10 `
  --embeddings-path src/experiments/embedding_builds/minilm_v2_audit_cpu/artifact `
  --matrix-config src/configs/eval/retrieval_matrix.yaml `
  --matrix-output "src/experiments/retrieval_matrix/smoke_$matrixStamp"
```

PyTorch is loaded first to preserve the Windows DLL workaround verified by the pilots.
No frozen artifact is overwritten. For rank-only replay, replace --matrix-config with
--matrix-from <completed matrix directory>, keep the same embedding/data/profile, and choose
a NEW --matrix-output directory. Provenance and hashes must match; retrieval is not called.
Replay currently preserves the frozen scoring config rather than allowing untracked scorer
tuning. No resumable matrix execution is implemented; start a new output after a failed run.

Do not open test data for tuning. No conclusion that the bottleneck is solved is warranted
until quality/latency gates are set and met, final ranking is checked, and the chosen config
is integrated into the intended runtime with validated request-time provenance.

### ANN on frozen validation histories

Use the same audit profile and overlay as the matrix. Run from the repository root
in the semantic environment with FAISS installed. No catalog re-encoding is needed.

```powershell
$env:PYTHONPATH = "src"
$tag = "multi_domain_v2_audit_20261030"
$env:EVAL_BUNDLE_PROFILE = (Resolve-Path "src/configs/profiles/$tag.profile.yaml").Path
$env:CONFIG_OVERLAY_PATH = (Resolve-Path "src/configs/profiles/$tag.overlay.yaml").Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
foreach ($index in "flat_ip","hnsw_flat_ip") {
  .\src\.venv-semantic\Scripts\python.exe -u -c "import torch,runpy; runpy.run_module('scripts.evaluation.benchmark_dense_ann',run_name='__main__')" `
    --tag $tag --artifact src/experiments/embedding_builds/minilm_v2_audit_cpu/artifact `
    --history-matrix src/experiments/retrieval_matrix/smoke_20261118_105327 `
    --query-mode recency_weighted --budget 100 --index-type $index --ef-search 512 `
    --output "src/experiments/ann_benchmarks/history_${index}_$stamp"
  if ($LASTEXITCODE -ne 0) { throw "Benchmark failed: $index" }
}
```

Compare completed reports only: matrix hash, users, query mode, eligibility and
seen hashes must match. No-text histories are excluded. Recall measures overlap
with filtered exact neighbors, not held-out recommendation quality. Latency is
serial filtered search excluding encoding, index build and warmup; do not
compare it directly to the older batch-average latency reports.
