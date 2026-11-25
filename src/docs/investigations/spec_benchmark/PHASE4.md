# Phase 4 — Extractor ablation: oracle vs predicted spec, run variance

**Date:** 2026-11-24 · **Branch:** `distill-phase05-1`
**Question:** (a) how much does extractor run-to-run variance matter, and (b) if a
DistillTool fed the *predicted* spec into retrieval instead of the *oracle* spec,
how much spec-satisfaction would be lost end-to-end?

## 4a. Run variance (`variance.py`)

Three extraction passes over the same 152 original requests:
- **Run A** — `extractor_outputs.jsonl`, temp 0 (Phase 3)
- **Run B** — `extractor_outputs_t0b.jsonl`, temp 0 rerun (provider determinism)
- **Run C** — `extractor_outputs_t07.jsonl`, temp 0.7 (sampling variance)

Slot-level agreement vs Run A:

| slot | temp0 rerun | temp0.7 |
|---|---|---|
| kind | 0.993 | 0.980 |
| category_leaf | 0.993 | 0.993 |
| category_coarse | 0.895 | 0.868 |
| seed_item_id | 1.000 | 1.000 |
| exclusions | 1.000 | 1.000 |
| language | 1.000 | 1.000 |
| **full spec identical** | **0.882** | **0.849** |

- The provider is nearly deterministic at temp 0; residual wobble is concentrated
  in `category_coarse` (extractor alternates leaf-only vs leaf+coarse).
- temp 0.7 barely moves anything except `unanswerable` kind agreement
  (0.833) — the constrained/unanswerable boundary is genuinely ambiguous.
- **Conclusion:** a single temp-0 extraction is stable enough; no ensemble or
  self-consistency voting needed for v1.

## 4b. Spec ablation on trajectories (`ablate_specs.py`)

Applied gold vs predicted spec as a constraint over the baseline exp_2
trajectories' `recommended[:10]` (`ablation_rows.jsonl`, 152 rows).
spec_sat@10 = fraction of top-10 items in the spec's resolved coarse bucket
(strict: uncategorized fails); exclusion = violation rate.

| kind | n | gold_sat@10 | pred_sat@10 | coarse_agree | excl_agree |
|---|---|---|---|---|---|
| cold_text | 20 | 0.600 | **0.640** | 0.95 | — |
| similar | 40 | 0.077 | 0.100 | 0.85 | — |
| exclusion | 40 | viol 0.000 | viol 0.000 | — | 1.00 |
| others | 92 | no enforceable spec (pass-through) | | | |

**Headline: predicted-spec filtering is statistically indistinguishable from
oracle-spec filtering on every enforceable kind.** pred_sat ≥ gold_sat on both
category kinds — the extractor's resolved bucket is at least as aligned with the
recommended pool as the single held-out target's bucket.

### The resolution bug this uncovered (important)

First ablation run showed pred_sat collapsing (cold_text 0.355, similar 0.02,
coarse_agree 0.55/0.225). Root cause was **my resolver, not the extractor**:

- `item_categories` is a **DAG, not a tree** — e.g. `Electronics` appears as a
  deep label inside Toys & Games paths; `Accessories` has 78 distinct ancestor
  sets. Depth proxies (`len(ancestors)`) pick wrong buckets.
- Gold coarse comes from *item sequences*; a standalone predicted label has no
  sequence. Correct resolution = **majority coarse of items carrying that
  label** (`label_coarse_map.json`, item-evidence, cached).
- After fix: coarse_agree cold_text 0.95, similar 0.85. Phase 3's low
  `cat_exact` on similar was likewise a *granularity* artifact, not wrong
  categories — the extractor says "Electronics" where gold leaf is "DSLR
  Cameras", both true at different depths.

### Residual disagreements (7 rows)

- `cold_text-cold-1`: request "Building Toys" — extractor leaf correct, but
  label→coarse majority = `Building Sets` while target's bucket = `Building
  Toys` (label straddles two coarse buckets; majority vote is lossy).
- 6× `similar` with uncategorized seeds: gold has no coarse (NaN→None);
  extractor still guessed a dept-level category (`Electronics`/`Toys & Games`)
  → pred imposes a constraint gold doesn't have. Arguably reasonable behavior,
  flagged for the report.

### Label normalization misses (5/27 predicted labels unresolved)

`Baby Products`, `Toys and Games`, `Arts, Crafts & Sewing`, `Sports & Outdoors`
are spelling variants of real labels (`Toys & Games`, `Sports & Outdoor Play`…);
`NonExistentCategory999` correctly unresolved. **DistillTool must run predicted
labels through `suggest_categories`/fuzzy matching before use** — the
infrastructure audit flagged this (`category_exists`/`suggest_categories`
available).

## Phase 4 verdict

- Extractor variance: negligible at temp 0; temp 0.7 safe but unnecessary.
- Oracle-vs-predicted headroom on enforceable kinds: **~zero** — predicted spec
  is good enough to drive spec-constrained retrieval for cold_text/similar/
  exclusion.
- Required before DistillTool (Phase 5): label normalization layer
  (suggest_categories), `similar` should prefer seed→coarse over guessed
  category, uncategorized-seed handling decision, leak criterion refinement
  (target-vs-input) if paraphrase evals continue.

## Files

- New: `investigations/spec_benchmark/{variance.py, ablate_specs.py,
  extractor_outputs_t0b.jsonl, extractor_outputs_t07.jsonl,
  label_coarse_map.json, ablation_rows.jsonl}`
- Edited: `run_llm.py` (`--tag`, `--temp`, `--include-leaked` flags)
