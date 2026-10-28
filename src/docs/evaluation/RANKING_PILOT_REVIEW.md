# Ranking pilot review — 2026-10-26

## Verified experiment

`src/experiments/ranking_eval/exp_005` completed on 2026-10-25. The earlier
`ranking_pilot_20261025_153737.log` has no completion marker; do not infer that it
produced another completed experiment.

* Validation, seed 42, 1,000 users per cold/sparse/warm segment; 3,000 unique users.
* Historical static catalog policy; unversioned price/rating aggregates masked.
* Fresh ItemKNN fit, neighbors 20, fit hash
  `090b6f0179c2f5f37308a59478bfe7c9317f0087d8d2a7d28ea0cceb1c00ab9e`.
* Candidate budget 100/source, 5 seed items, 3 history-title items, scorer weight
  1e-6; both union_rr and union_all evaluated.
* Runtime 1,360.73 s (22 min 40.73 s); ItemKNN fit 98.16 s.
* Total output 189,126,573 bytes (~180.4 MiB); 3,000 candidate records and 6,000
  scored records, accounting for two merges.

Read-only verification matched both mapping assignment hashes, all three split
content hashes and the implementation fingerprint before the query-normalization
change in this review. Sample IDs match the manifest; candidates are unique;
ranked candidates are members of their saved candidate sets; scores are ordered.
All saved ranking metric values were recomputed from scored records and match
within absolute tolerance 1e-14. Metadata fetch failures: zero.

## Quality and bottlenecks

Top-10 metrics below are identical between merges. NDCG/MRR use the [0,1] scale;
Recall/Hit Rate are percentages. This is a pilot, not full validation.

| Segment | NDCG@10 | Recall@10 | Hit Rate@10 | MRR@10 |
|---|---:|---:|---:|---:|
| Cold | 0.003658 | 0.6247% | 2.30% | 0.005281 |
| Sparse | 0.001807 | 0.3167% | 0.50% | 0.002058 |
| Warm | 0.000938 | 0.1000% | 0.30% | 0.001476 |

Union_all contains more candidates for sparse/warm users (239.439/271.193 on
average versus 100 for union_rr) and improves candidate recall, but not the
reported top-10 metrics. This supports investigating the scoring stage; it does
not establish which scoring variant is better. Post-merge seen/unscored losses
are zero. The reported boundary-tie rates use max-K=20, not K=10.

Population-standardized pilot estimates, using actual segment population
weights: NDCG@10 0.001442; Recall@10 0.2163%; Hit Rate@10 0.4977%; MRR@10
0.001931. These are estimates from a stratified sample, without confidence
intervals, not measured full-validation results.

### Blocker: metadata-title queries rejected by the ASCII contract

There are **385 SemanticSearch errors**:

> `query` must contain only ASCII characters (English text). Translate non-English queries before searching.

* Sparse: 163/1,000 users (16.3%).
* Warm: 222/1,000 users (22.2%).
* Cold: history queries are unavailable by design.

All recorded source errors have this message; they are not SQL timeout errors.
An English catalog title can contain Unicode trademarks, punctuation or Latin
letters with accents. ASCII compliance is not equivalent to language detection.
The existing metrics correctly describe the chain including these failures, but
are not a clean baseline of retrieval with available metadata-title queries.

Semantic calls consumed ~974.04 s, ~71.6% of total pilot runtime. Full validation
also remains blocked by the script's in-memory accumulation and lack of
checkpoint/resume. A crude linear extrapolation is ~142 hours and ~66.3 GiB of
serialized output; neither is an ETA or a RAM estimate. Do not launch full
validation using the present script.

## Intervention implemented

Candidate and ranking scripts now accept `--query-normalization raw|ascii_fold`.
Default remains `raw`, preserving the old protocol. The explicit ASCII-fold
intervention normalizes Unicode typography, decomposes accented Latin letters,
and separates unsupported symbols. It is **not translation** and can lose
non-Latin content. Entirely emptied queries remain unavailable, not successful.

Ranking candidate records persist raw/sent queries, normalization identity and
empty/changed flags. Metrics include per-segment tool health. The protocol
records the normalization; ablation compatibility checks reject a raw/folded
protocol mixture. Production tokenization and production configuration are
unchanged. No old experiment was modified.

AST parsing, CLI argument discovery and manual tokenizer examples were checked.
No full test suite or long quality evaluation was run for this intervention.

## Next action: rebaseline the same pilot before weight tuning

Run from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONIOENCODING = 'utf-8'
$log = "ranking_ascii_baseline_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
& .\src\.venv\Scripts\python.exe -u src/scripts/evaluation/ranking_eval.py `
  --tag multi_domain --eval-on validation --seed 42 --per-segment 1000 `
  --candidate-budget 100 --seed-items 5 --query-items 3 --neighbors 20 `
  --ks "5,10,20" --popularity-weights 1e-6 `
  --metadata-policy historical_static_catalog --query-normalization ascii_fold `
  --no-prebuilt-corpus 2>&1 | Tee-Object -FilePath $log
```

Verify sample IDs match exp_005; inspect `tool_health`, empty queries, metrics,
runtime and output size. Any difference from exp_005 is a query-preprocessing
intervention, not proof of ranker improvement. Other source errors must be
resolved or explicitly included in the baseline contract before tuning.

Only after this baseline is accepted, run the same command with
`--popularity-weights "0,1e-6,1e-4,1e-3,1e-2"`. All variants in that experiment
receive identical saved candidate inputs. Compare segments, candidate coverage,
latency and paired per-user metrics; do not select from mean Recall alone.
Do not use the test set to select parameters. This pilot does not support production promotion.


## Follow-up, 2026-10-26

Exp_006 completed the prescribed ASCII-fold pilot on identical users: 385 query
failures were eliminated, none were emptied, and top-10 quality remained
unchanged. See RANKING_STREAMING_RUNBOOK.md for verified results and the new
checkpoint/confirmation/tuning workflow. Earlier statements above about missing
checkpoint support describe the exp_005 implementation, before this follow-up.
