# Ranking evaluation: clean pilot, checkpoints and controlled tuning

## Findings from exp_006 (2026-10-26)

* Same 3,000 sampled validation users as exp_005, seed 42.
* `ascii_fold` changed 163 sparse and 222 warm queries. No query became empty.
* SemanticSearch errors: **0**, compared with 385 in exp_005. ItemCF errors: **0**.
* Runtime **1,411.8 s (23 min 31.8 s)**; output **200,227,531 bytes (~191 MiB)**.
* Top-10 quality is unchanged for both merges. Paired per-user NDCG@10 deltas
  are zero for all 3,000 users; this is not a ranker-quality improvement.

| Segment | NDCG@10 | Recall@10 | Hit Rate@10 | MRR@10 |
|---|---:|---:|---:|---:|
| Cold | 0.003658 | 0.6247% | 2.3% | 0.005281 |
| Sparse | 0.001807 | 0.3167% | 0.5% | 0.002058 |
| Warm | 0.000938 | 0.1000% | 0.3% | 0.001476 |

Union_all candidate recall rose from 3.4964% to 3.6964% for sparse users and
2.9249% to 3.0374% for warm users. Union_rr sparse recall declined slightly,
from 2.2914% to 2.2771%; warm rose from 1.7923% to 1.8715%. These are query
preprocessing effects on fixed users, not scorer tuning. No confidence claim
is made for these small changes.

All candidate/scored records were read and checked against sample/mapping
identities. The new streaming accumulator reproduced exp_006 ranking/retrieval
quality, coverage, filtering and ranking/fetch latency summaries; maximum
ranking-metric absolute error was **1.7347e-18**. Original experiments are intact.
The pilot remains a static-catalog proxy with the label/cohort limitations in
EVALUATION_PROTOCOL.md; it is not full validation or a production qualification.

## Implemented safeguards

* `--batch-size` commits candidate/scored records to SQLite after each batch.
  Memory retains the active batch, not all candidate lists.
* `--progress-every` reports committed users, active-session speed and ETA for
  retrieval (separate cold/sparse/warm estimates), scoring and summary. Setup stages announce their start; ETA for a
  single corpus build/model fit is unknown rather than fabricated.
* `--work-dir` contains `run_manifest.json`, `checkpoint.sqlite3`, its WAL,
  `writer.lock`, and a validated local ItemKNN checkpoint. A manifest is available
  before expensive setup; these local files are ignored by Git at the documented
  checkpoint locations.
* `--resume` requires the same identity: code/environment, data/mapping/source
  hashes, sampling and quality parameters. Batch size/progress frequency may
  change; execution-session settings are recorded. Do not edit implementation or
  inputs between interruption and resume.
* An OS lock prevents simultaneous writers to one checkpoint. Transactions lose
  at most the uncommitted batch on interruption. Committed users are not rerun.
* Resume revalidates/reuses the checkpoint model. Corpus may be rebuilt in RAM;
  it is not persisted by this runner. A completed scoring checkpoint can finish
  summary/export without rebuilding corpus or models.
* Source inputs are rehashed before publication. JSONL exports stream through
  `.partial` files with flush/fsync and atomic replacement. An `exp_NNN` directory
  appears only after JSONL and manifests are complete. Recovery handles export
  interruption and a crash after publication but before its checkpoint marker.
* Exact latency percentiles use compact float64 timing vectors; catalog coverage
  uses catalog masks. Summary memory still scales with users/variants for timing
  vectors, and normal model/data setup still requires RAM. No full-run peak RAM
  measurement has been made.
* Runtime sums observed active sessions plus initial provenance hashing, excludes
  downtime, and is captured through export. A hard kill can lose timing after the
  last committed batch; the output states this limitation. Mixed-session latency
  measurements should not be treated as a fresh controlled performance benchmark.
* Disk usage includes SQLite checkpoints, model cache and final JSONL exports.
  Budget more than the final output size; no checkpoint is automatically deleted.

## 1. Confirm the baseline on the new runner

Run from the repository root in PowerShell. Frozen mode uses the exact saved
candidate inputs from exp_006 and validates sample, ground truth, fit hash,
mapping and retrieval settings. It does not run FTS again. Corpus and ItemKNN
setup are still required on the first invocation.

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONIOENCODING = 'utf-8'

& .\src\.venv\Scripts\python.exe -u src/scripts/evaluation/ranking_eval.py `
  --tag multi_domain --eval-on validation --seed 42 --per-segment 1000 `
  --candidate-budget 100 --seed-items 5 --query-items 3 --neighbors 20 `
  --ks "5,10,20" --popularity-weights "1e-6" `
  --metadata-policy historical_static_catalog --query-normalization ascii_fold `
  --no-prebuilt-corpus --batch-size 50 --progress-every 100 `
  --candidates-from src/experiments/ranking_eval/exp_006 `
  --work-dir src/experiments/checkpoints/ranking_ascii_confirm_seed42
```

Expected messages: `[baseline confirmed]` for both merges, then
`Saved ranking evaluation: ...`. Confirmation checks denominators, each quality
metric at the requested K values (absolute tolerance 1e-12), and catalog coverage.
It also compares each user's candidate/ranked IDs and scores against source scored.jsonl (score tolerance 1e-12). It stops if the baseline does not reproduce. New timings need not equal exp_006.

## 2. Tune one parameter group on those same candidates

After baseline confirmation, run:

```powershell
& .\src\.venv\Scripts\python.exe -u src/scripts/evaluation/ranking_eval.py `
  --tag multi_domain --eval-on validation --seed 42 --per-segment 1000 `
  --candidate-budget 100 --seed-items 5 --query-items 3 --neighbors 20 `
  --ks "5,10,20" --popularity-weights "1e-6,0,1e-4,1e-3,1e-2" `
  --metadata-policy historical_static_catalog --query-normalization ascii_fold `
  --no-prebuilt-corpus --batch-size 50 --progress-every 100 `
  --candidates-from src/experiments/ranking_eval/exp_006 `
  --work-dir src/experiments/checkpoints/ranking_ascii_weights_seed42
```

The baseline is evaluated/confirmed first for each merge, before other weights.
All variants use identical candidates. Retrieval latency is explicitly copied
from the source experiment; ranking/fetch latency is measured in this run. Legacy
source metadata snapshots may not have content hashes; the exact candidate file
and source configuration are pinned, not retroactively certified as causal data.

## 3. Resume and fresh retrieval

To resume, use the **same command** and append `--resume`. Keep the same work-dir
and quality parameters. If it already completed, it reports the published
experiment and does not create another one. A new weight set requires a new
work-dir, not resume.

For a fresh retrieval pilot, omit `--candidates-from` and choose a new work-dir.
The database is the checkpoint of record; final candidate_lists.jsonl/scored.jsonl
are exports at completion. Export `.partial` files are not valid experiments.

## Acceptance and remaining work

Implementation has been verified on small end-to-end fixtures and the complete
exp_006 saved records. A real run on the new runner, larger-validation
confirmation, peak-resource measurement and weight-tuning results are still
pending user execution. No full evaluation or new production configuration was
started automatically.

After tuning, compare paired per-user NDCG/Recall/Hit/MRR, segment regressions,
coverage, filtering, ties and measured costs. Confirm promising configurations
on a larger fixed validation sample, with uncertainty analysis. Do not use the
test set to choose weights or infer improvement from correctness tests alone.


## Regression verification

The complete suite passed **1,068 tests**, with **3 skips** and 13 existing
SparseEfficiencyWarnings. New tests cover raw/folded query contracts, unchanged
production ASCII rejection, atomic checkpoint prefixes, duplicate/identity/lock
rejection, interrupted retrieval and scoring, interrupted export/publication,
identical continuous/resumed candidates and scores, frozen-input reuse without
retrieval, and stopping tuning when baseline confirmation fails. Commands:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& .\src\.venv\Scripts\python.exe -m pytest -c src/pyproject.toml src/tests --no-results -q -p no:cacheprovider
```
