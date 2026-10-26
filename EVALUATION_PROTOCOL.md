# Evaluation protocol v2

## Scope and scientific interpretation

Validation fits **train**; final test fits **train + validation**. Test data must
not select parameters. Existing splits, models, metadata and experiment folders
are not migrated or overwritten by this implementation.

The existing cohort was filtered before temporal splitting. Item vocabulary,
titles, taxonomy and store metadata are a frozen static catalog with unverified
historical availability. Report results as an **offline static-catalog proxy**,
not a fully causal production simulation. All review pairs remain binary
positives regardless of stars; label-policy experiments require a new baseline.

## Metadata policy

Candidate, ranking and agent evaluation accept:

* `--metadata-policy historical_static_catalog` (default): mask `price`,
  `average_rating`, and `rating_number`. Their observation time is unknown.
  A temporary SQLite view supplies NULLs; an authorizer also rejects direct
  reads of these fields through `main.items`. Sources and persistent corpus
  tables are unchanged. Reload the corpus to switch policy or cutoff.
* `--metadata-policy snapshot`: retain these values for an explicitly non-causal
  snapshot comparison. Never merge these results with historical-policy runs.

Masked price/rating constraints cannot certify matches. SQL results may be empty;
FTS ties and default SQL ordering fall back to deterministic item IDs. Memory and
answer composition see the same masked values as retrieval. No historical price
is imputed. Marketplace aggregates are not reconstructed from reviews here.

This policy does **not** establish historical validity of titles, taxonomy, store,
catalog membership or FTS document statistics. A future fully temporal benchmark
requires versioned metadata/catalog availability. Timestamp cutoffs on user
history alone do not establish metadata validity.

History-title queries are offline proxies, not observed user queries.
`category_oracle` and target-derived agent constraints must remain labeled oracle.
Agent requests generated under masked price metadata can differ from snapshot
requests; compare only identical saved requests and compatible policies.

## ItemKNN and corpus provenance

New ItemKNN files use format v2 and bind exact sorted event pairs (including
duplicate events), little-endian int64 hash protocol, numeric mapping assignments,
dataset tag, fit split, k, algorithm version and artifact SHA256. Dictionary/row
order does not change identity. Assignment permutations do.

Dataset loaders supply both mappings, tag and evaluation split. Legacy v1 or
mismatched caches require refitting; they are never promoted by row counts or by
editing a manifest. LiveBackend records the rejection reason before fitting in
memory. Evaluation scripts always refit and save their fit hash and mapping/split
provenance; they do not overwrite the old cache. Numeric-only synthetic save/load
remains supported but cannot satisfy a dataset-bound load.

New corpus files use content SHA256, ordered source domains, assignment-sensitive
mapping hash and artifact checksum. Moving/touching unchanged metadata is valid;
changing bytes at the same size/mtime is not. Legacy v1 corpus loading retains
its strict original checks and records weaker provenance. A mismatch is not
silently skipped or converted to v2. Use `--no-prebuilt-corpus` for candidate and
ranking evaluation, or `--no-prebuilt` for agent evaluation, to build from current
sources in memory when an old corpus fails validation. This does not rewrite it.

## Diagnostic and metric definitions

* Event counts count rows; item coverage counts unique items.
* Item warm means **any** fit user interacted with an item.
* Repeat means the **same user-item pair** occurred in fit. A repeat event is not
  inherently leakage.
* Novel-warm eligibility is the fraction of unique target user-item pairs whose
  item is fit-warm and whose pair is absent from fit (micro denominator).
* Eligibility is not a universal macro Recall@K ceiling: content retrieval can
  return cold items. The diagnostic separately computes a catalog-restricted
  macro Recall@10 upper bound, including the top-10 capacity constraint.
* History length counts **unique fit items**, includes zero-history target users,
  and matches binary CSR segment assignment. Domain diagnostics use global fit
  history for users with targets in that domain.
* Explicitly named legacy train-only reference fields remain train-only.
  `fit_diagnostics.test` uses train + validation.
* Candidate quality uses all unique target items, including repeats; ranking
  evaluation uses novel targets and excludes users with no novel ground truth.
  Agent quality uses each saved request's targets, and ambiguous requests have
  no recommendation ground truth.
* `target_items_seen_in_fit` in candidate results is a compatibility alias for
  macro-user catalog familiarity, **not** same-user repeats. New output records
  the explicit names for both quantities.
* Per-segment samples are capped separately. A pooled sample average is not a
  population-weighted overall metric. Manifests record population/sample counts;
  preserve per-segment results and declare weighting in any aggregate report.

Protocol manifests include temporal boundaries, metadata policy, label/cohort
assumptions, mapping hashes and sample sizes. Experiment dataset records include
split file content hashes. Existing experiment writers record code fingerprint,
environment and seed. Protocol v1 and v2 scores need separate baseline identities.

Agent resume also checks a hash of code, protocol, fit hash, metadata content,
requests and runtime configuration. Legacy/mismatched logs are preserved and
rejected. Pick a new trajectory filename; non-resume runs cannot overwrite logs.

## Reproduction commands (PowerShell, repository root)

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& .\src\.venv\Scripts\python.exe -m pytest -c src/pyproject.toml src/tests --no-results -q -p no:cacheprovider
& .\src\.venv\Scripts\python.exe src/scripts/eda_diagnostic/diagnose_splits.py --tag multi_domain
```

Pilot examples below refit ItemKNN even with a small user sample; sampling does
not reduce model fit cost. They create **new** experiment directories. Run only
after choosing resource limits and fixing the sample; no test tuning.

```powershell
& .\src\.venv\Scripts\python.exe src/scripts/evaluation/candidate_recall.py --tag multi_domain --eval-on validation --seed 42 --per-segment 100 --query-modes history --metadata-policy historical_static_catalog --no-prebuilt-corpus
& .\src\.venv\Scripts\python.exe src/scripts/evaluation/ranking_eval.py --tag multi_domain --eval-on validation --seed 42 --per-segment 100 --popularity-weights 1e-6 --metadata-policy historical_static_catalog --no-prebuilt-corpus
& .\src\.venv\Scripts\python.exe src/scripts/evaluation/run_agent_eval.py --tag multi_domain --eval-on validation --agents baseline,type1 --inference-mode template --request-scope realistic --metadata-policy historical_static_catalog --no-prebuilt --trajectory-file agent_protocol_v2_seed42.jsonl
```

Do not interpret correctness tests or diagnostic coverage as recommendation
quality improvement. A new policy baseline must be measured before tuning.


Agent evaluation currently takes its seed from `eval/baselines.yaml` (42 at
verification); it has no `--seed` CLI option. The resolved seed is saved by the
experiment writer and included in resume identity.

## Implementation verification, 2026-10-25

* Full suite: **1052 passed, 3 skipped, 13 SparseEfficiencyWarnings**, 30.72 s.
  Command from `src`: `.\.venv\Scripts\python.exe -m pytest tests --no-results -q -p no:cacheprovider`,
  with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
* CLI import/help checks passed for candidate, ranking and agent scripts.
* Actual standalone Video_Games diagnostic CLI completed; optional domain is
  correctly reported absent. Its validation warm unique-pair fraction is
  72.859521%, repeat fraction 0.212681%, and novel-warm fraction 72.646841%.
* Full multi-domain diagnostic completed again with the optimized implementation
  in **110.08 s**, including data loading. Validation novel-warm eligibility:
  **81.239814%**, repeats **0.077846%**, cold users **5.960498%**. Test with
  train+validation fit: **70.845325%**, **0.063823%**, **4.118424%**, respectively.
* Randomized small-fixture results were checked against an independent Python
  set reference. Deterministic retrieve/rank/fetch with masked metadata passed.
  LiveBackend initialization tested both validated-cache and rejected-cache/refit
  branches with synthetic data and a mocked LLM health check.
* No full ItemKNN refit, recommendation quality baseline, real LLM evaluation,
  source-data rewrite or persistent artifact migration was run in this change.
  Test-split access was diagnostic only and did not select parameters.


## Pilot review and query normalization, 2026-10-26

See [RANKING_PILOT_REVIEW.md](RANKING_PILOT_REVIEW.md) for the exp_005 artifact
verification and next command. That pilot completed, but 385 metadata-derived
queries were rejected by the existing ASCII-only tool contract. Candidate and
ranking scripts support an explicit `--query-normalization ascii_fold`
intervention; default `raw` preserves the previous baseline. Normalization is
persisted in the protocol, and ranking records include raw/sent text and tool
health. Rebaseline with identical users before weight tuning. Folding is not
translation and does not establish historical validity of metadata.


## Ranking streaming runner, 2026-10-26

See [RANKING_STREAMING_RUNBOOK.md](RANKING_STREAMING_RUNBOOK.md). Ranking evaluation
now supports durable SQLite batches, stage progress, checkpoint/resume, streamed
JSONL publication and frozen candidate input. OS locking and input/code identity
checks guard resume. Scorer controls are confirmed against source metrics AND
per-user ranks/scores before other weights run on a merge. No old experiment was
rewritten. Local checkpoints and final exports both consume disk; memory for data
and model preparation and compact latency vectors is still required.

Exp_006 is the clean 3,000-user pilot: no retrieval errors or emptied queries;
normalization did not change any user's NDCG@10. This establishes an operational
pilot baseline, not a claim of quality improvement, full-validation confirmation,
or production readiness. The next long runs remain user-executed.
