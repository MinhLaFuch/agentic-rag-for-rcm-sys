# Phase 2 — spec_* metric backfill report

Date: 2026-11-24 · Branch: `distill-phase05-1` · Offline, zero LLM.
Question answered: **does arm ranking by spec_* flip vs task_success?**

## Method (all evidence reproducible)

- Metrics: `package/evaluation/spec/_metrics.py` (pure fns, 10 unit tests).
- Gold: request fields + held-out/seed taxonomy via `coarse_label` leaf-up
  ≥1000 + `main_category` fallback — same rule as Spec v1 (`_schema.py:32-48`).
- Item views: one streaming pass over `item_categories` (9.94M rows) →
  `item_spec_view.parquet` (2,637,776 items: coarse/ancestor/has_categories).
  Script: `scripts/evaluation/backfill_spec_metrics.py` (read-only on artifacts).
- Rows: `spec_backfill_rows.jsonl` (100 in-scope reqs/arm = 20 cold_text +
  40 similar + 40 exclusion; personalized/constrained/descriptive/
  ambiguous/unanswerable excluded per spec). Summary: `spec_backfill_summary.json`.
- Exclusion gold = `excluded_item_ids` + `excluded_categories`
  (`build_requests.py:117-126`, ORACLE/held-out-derived). Planner has NO
  category-exclusion filter — only `exclude_item_ids` (`_schema.py:8-20`),
  so category-label violations are the realistic failure mode.
- Baselines: random/popularity over the WHOLE catalog (sampling from S would
  trivially score 1.0). Popularity pool = top-1000 `rating_number`.

## Main table (means; n per kind constant across arms)

### cold_text (n=20, |S|≈5,176 items avg)

| arm | task_success | spec_precision@10 | lenient | hit@10 | ancestor@10 | coverage | random | popularity |
|---|---|---|---|---|---|---|---|---|
| baseline | 0.650 | 0.600 | 0.600 | 0.70 | 0.555 | 0.70 | 0.0196 | 0.0029 |
| **f3** | **1.000** | **0.935** | 0.935 | 1.00 | 0.865 | 1.00 | 0.0196 | 0.0029 |
| promptfix | 0.650 | 0.735 | 0.770 | 0.80 | 0.645 | 0.85 | 0.0196 | 0.0029 |
| hybrid | 0.700 | 0.685 | 0.685 | 0.75 | 0.605 | 0.75 | 0.0196 | 0.0029 |
| learned | 0.450 | 0.570 | 0.590 | 0.70 | 0.470 | 0.70 | 0.0196 | 0.0029 |
| camp5 | 0.500 | 0.525 | 0.535 | 0.60 | 0.475 | 0.60 | 0.0196 | 0.0029 |
| camp6 | 0.300 | 0.515 | 0.555 | 0.55 | 0.440 | 0.60 | 0.0196 | 0.0029 |

Paired bootstrap vs baseline (`spec_precision@10`, n=20, CI only — no point
conclusions per protocol): **f3 +0.335 [0.15, 0.535]** — the ONLY cold_text
diff whose CI excludes 0. All others include 0.

### similar (n=40, |S|≈10,555 items avg)

| arm | task_success | spec_precision@10 | lenient | hit@10 | ancestor@10 | coverage |
|---|---|---|---|---|---|---|
| baseline | 0.950 | 0.075 | 0.105 | 0.40 | 0.095 | 0.95 |
| f3 | 0.525 | 0.075 | 0.105 | 0.40 | 0.095 | 0.975 |
| promptfix | 0.950 | 0.075 | 0.105 | 0.40 | 0.095 | 0.95 |
| hybrid | 0.950 | 0.090 | 0.120 | 0.425 | 0.113 | 0.95 |
| learned | 0.950 | 0.068 | 0.120 | 0.40 | 0.085 | 0.95 |
| camp5 | 0.950 | 0.075 | 0.105 | 0.40 | 0.095 | 0.95 |
| camp6 | 0.950 | 0.075 | 0.103 | 0.40 | 0.088 | 0.95 |

Random baseline 0.040, popularity 0.009 — all arms ≈1.9× random, weak
discrimination (|S| is huge → "same coarse bucket" is a weak constraint).
hybrid +0.015 [0.0025, 0.03] CI excludes 0 but is practically negligible.

### exclusion (n=40)

| arm | task_success | violation_rate | coverage |
|---|---|---|---|
| baseline | 0.475 | 0.000 | 0.50 |
| f3 | 0.475 | 0.000 | 0.65 |
| promptfix | 0.250 | 0.075 | 0.35 |
| hybrid | 0.550 | 0.000 | 0.55 |
| learned | 0.425 | **0.100** | 0.525 |
| camp5 | 0.200 | 0.075 | 0.275 |
| camp6 | 0.250 | 0.050 | 0.30 |

learned +0.10 violation vs baseline, CI [0.025, 0.2] — excludes 0. Spot-checked
(exclusion-warm-1): recommended items literally carry the excluded `Swings`
label — real violations, not artifact. Violation rates are low everywhere;
**coverage (0.28–0.65) is the dominant exclusion signal**, consistent with
40/152 empty-list trajectories.

## Answers to the required questions

1. **Ranking reversal vs task_success?** YES, in an informative way —
   not arm-order flips but *kind-level divergence*:
   - **F3**: loses overall task_success (0.589 vs 0.679, driven by similar
     0.525 vs 0.950) yet is the ONLY arm with a significant spec gain —
     cold_text +0.335 precision, CI excludes 0. Its category filter does
     exactly what it claims on browse requests while breaking similar.
   - **task_success and spec_* agree on direction everywhere else** that
     differs at all (learned worse on both exclusion axes).
   - Interpretation: spec_* does NOT overturn the F3-negative verdict — it
     *explains* it. F3 wins the kind its filter targets and loses the kind
     where the forced category constraint is wrong.

2. **Binary saturation?** `spec_hit@10` saturates mildly (baseline cold_text
   0.70, f3 1.00) — graded precision is the better primary metric, as designed.

3. **Depth d vs d-1?** `spec_precision_ancestor@10` is consistently a bit
   below strict (cold_text baseline 0.555 vs 0.600; f3 0.865 vs 0.935) —
   ~5–8% of hits are only correct at the shallower ancestor level. Signal is
   mostly at the chosen coarse depth, not just "right department".

4. **Baseline lift:** pipeline beats random (~30×) and popularity (~200×) on
   cold_text — the metric is NOT just measuring "a filter ran". On similar it
   is barely above random (1.9×) — consistent with |S|≈10.5k being a weak spec.

5. **Normalized target recall:** `spec_target_recall_norm@10` (recall@10 ÷
   10/|S|) is huge where recall>0 (baseline cold_text 28.2) — confirms targets
   sit inside S but the metric saturates; reported for completeness only.

## Files changed

- `package/evaluation/spec/_metrics.py` (new) + `__init__.py` exports
- `scripts/evaluation/backfill_spec_metrics.py` (new)
- `tests/evaluation/spec/test_spec_metrics.py` (new, 10 tests)
- `investigations/distill_phase2/{item_spec_view.parquet,spec_backfill_rows.jsonl,spec_backfill_summary.json,REPORT.md}`

## Chưa xác minh / caveats

- cold_text gold coarse derives from the FIRST target's sequence (oracle,
  consistent with gold flagging); multi-target requests use targets[0] only.
- `spec_violation_rate` is per-request binary averaged — a request with 1 vs
  5 violating items scores identically (graded variant not implemented).
- popularity baseline uses top-1000 `rating_number` as proxy for the eval's
  popularity ordering (fit-derived popularity differs slightly — direction
  unchanged, magnitude approximate).
- uncategorized recommended items: strict=miss, lenient=hit — deltas are small
  (≤0.035) because few recommendations are uncategorized.
- exclusion `spec_set_size`/baselines are 0/degenerate by design (relevant set
  ≈ whole catalog) — violation+coverage are the meaningful columns.
- camp5/camp6 are reflect_rounds variants of the same planner config; their
  spec numbers being near-identical to each other is expected, not a bug.
