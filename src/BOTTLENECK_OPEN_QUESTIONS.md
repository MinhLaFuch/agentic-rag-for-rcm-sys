# Open Questions — Retrieval/Reranking Bottleneck Investigation

Companion to `RETRIEVAL_RANKING_BOTTLENECK.md`. Each question lists the measured
evidence behind it and the decision it gates.

**STATUS 2026-11-20: the read-only investigation pass is COMPLETE.** Results are
in `investigations/INVESTIGATION_REPORT.md` (consolidated table) + per-item JSONs.
Questions marked **[ANSWERED]** now have measured numbers — they remain listed
because the *decision* they gate is still yours. Questions marked **[OPEN]** were
not resolved by data and still need your call.

Legend: ✅ measured/answered · 🔶 partially answered · ⬜ still open (decision)

---

## P0 — Candidate retrieval recall (~72% of targets die here)

### Q1. FilterTool category usage policy ✅ ANSWERED 2026-11-21 — keep optional leg
A/B on the same 152 requests, post-F2 (`experiments/agent_eval/filter_ab/`):
- A (always-on leaf-category prompt): FilterTool used in 126/152 reqs (58 w/
  cat filter) vs B 74/152 (16 w/ cat) — prompt compliance confirmed.
- task_success: A 0.589 vs B **0.679** — always-on is WORSE.
- target metrics identical: task_success_relevant 0.026, hit_rate@10 0.026,
  target_in_any_path_pool 0.897 both arms.

Pool coverage was already saturated; extra FilterTool calls added noise/
latency without target gains. **Baseline prompt stays.** Planner-level
retrieval levers are exhausted — remaining gains are scorer (Q5–Q7) and
retrieval enrichment (Q2).

### Q2. Uncategorized tail 🔶 → DECIDED 2026-11-21: build categorization layer
**STATUS 2026-11-22: BUILT, awaiting merge+eval** — prototype validated
(kNN top-1 vote ≈99% any-hit on categorized holdout; uncategorized items get
top-1 voted category). `investigations/q2_build_inferred_categories.py`
finished all 23 parts → `investigations/q2_inferred_cats/part_*.parquet`
(CUDA path, fp16 refs). Consumption wired: `apply_metadata_policy(
inferred_categories=...)` unions inferred rows for uncategorized visible
items only; `run_agent_eval` auto-loads
`resource/corpus/multi_domain/item_categories_inferred.parquet` if present.
Remaining: merge parts → artifact, sanity-check assignments, run agent eval
with/without inferred cats, measure category-filter recall on the tail.
**User decision:** create a layer that categorizes the uncategorized tail —
likely via embedding relations (cluster/nearest-neighbor into the existing
category taxonomy). Design needed: which items (~24% of targets affected),
which embedding (ties into user's multilingual-model evaluation), assignment
confidence threshold, and whether inferred categories feed FilterTool,
MemoryTool profiles, or doc text. Source-data gap confirmed (Q15) — this is
enrichment, not preprocessing repair.

### Q3. SearchTool timeouts ✅ ANSWERED (root cause = same bug as FilterTool)
108 SearchTool steps across both runs: **100 exceeded 5s-or-error, median
latency 6.1s**. But replaying the exact FTS5 MATCH+JOIN+ORDER on the raw corpus:
all 40 unique queries finish in **≤2.9s select / ≤0.6s count** — FTS itself is
fast. 77.5% of queries carried structured filters → the **pre-fix correlated
EXISTS** in `compile_filters` (same root cause as the FilterTool bug, already
fixed in the working tree). 0% of queries produced target hits anyway.
(`investigations/q3_search_timeouts.json`)

### Q4. FilterTool candidate ordering ✅ ANSWERED (rating_number is best by far)
On the §6.6 oracle sample (155 targets, per-target best-category rank,
visible items only — `investigations/q4_filter_orderings.json`):

| ordering | r@200 | r@1000 | median rank |
|---|---|---|---|
| **rating_number DESC** | **38.7%** | **49.0%** | **42** |
| price ASC | 16.8% | 37.4% | 252 |
| first_seen_ts DESC (recency) | 7.7% | 34.2% | 419 |
| average_rating DESC | 9.0% | 31.0% | 399 |
| item_id ASC (**eval's actual order under Q18 masking**) | **0.65%** | **12.3%** | 586 |

`rating_number` is the clear winner — AND it's the field Q18 masks to NULL.
Review count ≈ rating_number (Q16: it's the Amazon rating count, Spearman 0.73
vs interactions). Recency (first_seen) is worst-ish. **Popularity ordering is
correct — the bug is that eval can't see it.**

---

## P1 — Ranking / scoring (measured second bottleneck)

### Q5. Scorer strategy 🔶 → DECIDED 2026-11-21: keep both, more evidence
**User decision:** keep baseline AND learned scorer; gather more evidence
before wiring. Next step queued: rerun `ranktool_injection_probe` +
`q6_scorer_comparison_v2` on the two post-F2 filter_ab runs (fresh candidate
pools, real FilterTool ordering) to see if v5_honest's 71.4% rescue@10
replicates outside the exp_5 injection setup.
Prior evidence (`q6_scorer_comparison_v2.json`, 126 targets w/ competition,
reproduces §6.7's 31.75% exactly):
- **pure popularity alone = 60.3% rescue@10** — the CF term actively HURTS
- honest learned reranker [pop, cf, cat_match] CV-by-request = **71.4%**
- retrieval-blend variants couldn't be fairly tested via injection (injected
  targets have retr=0 by construction → biased down; needs live A/B)

### Q6. Retrieval-score blending 🔶 (probe run — result is nuanced)
Ran the offline comparison (`investigations/q6_scorer_comparison{,_v2}`).
Verdict: **cannot be validated by injection** — any variant weighting retrieval
scores is structurally biased because injected targets have retr=0. What IS
measurable offline: popularity+cat_match learning gives 71.4%. Recommendation:
test retrieval blending in a live A/B (union candidates already carry
`retrieved_by` provenance), not offline.

### Q7. Popularity's role in ranking 🔶 (evidence in, decision yours)
Popularity tiebreak decides most rank-1s AND pure popularity beats the CF
baseline 60.3% vs 31.75%. Targets are ~16× more popular than retrieved
candidates (`feature_target_means` in q6 JSON). Evidence says: **keep popularity,
elevate it** — possibly as the primary signal for cold users. Your call on
exact weighting.

---

## P2 — Collaborative filtering

### Q8. Is a different CF model in scope? ⬜ (decision still yours — now better informed)
ItemKNN is structurally dead (§6.5, §6.8) and k-core K is exonerated (Q12:
co-occurrence 98→94 targets across K=none→5; max_sim p90 ≈0.004). Only a
fundamentally different model (MF/two-tower on full 48.8M train — note train_core
keeps only 19.4M) could create signal. Still your scope decision.

---

## P3 — Eval validity / temporal policy

### Q9. Is the ~18% `first_seen` hiding real or artifact? 🔶 → REOPENED 2026-11-21
**User:** masking is fixed (Q18 commit dc100d1) — take another look at the
temporal policy itself. Next step: field-level audit of which metadata fields
(price, average_rating, rating_number, categories, first_seen) are masked vs
exposable under `historical_static_catalog`, and whether any masked field has
a causal pre-cutoff proxy (like the new train-count popularity) worth wiring.

**Field-level audit 2026-11-21** (`items` schema = item_id, domain,
original_item_id, first_seen_ts, title, store, price, average_rating,
rating_number, main_category):

| field | status under historical_static_catalog | causal proxy available? |
|---|---|---|
| item_id, domain, original_item_id, title, store, main_category | exposed | n/a (static-ish; title/store mutability unverified but low-risk) |
| first_seen_ts | visibility filter (≤ as_of) | proxy IS the filter; ~24% catalog / ~18% targets hidden — real launch dates don't exist upstream |
| rating_number | masked NULL | ✅ DONE — fit-split interaction count (dc100d1, ~87% of leaky ordering quality) |
| average_rating | masked NULL | ✅ **available, not yet wired** — train.parquet has per-interaction `rating` (48.8M rows, 0 nulls, mean 4.17); mean train rating per item covers all 2,003,873 visible items. Same mechanism as popularity could expose it |
| price | masked NULL | ❌ none — reviews don't record price; only option is category-level bands (weak) or accepting the mask |

So the masking re-look yields one concrete upgrade: causal `average_rating`
proxy. `min_rating` FilterTool filter could then work causally instead of
erroring. Price stays masked — that's a real information gap, not a fixable one.
**STATUS 2026-11-22: IMPLEMENTED** — `apply_metadata_policy(ratings=...)`
builds temp `item_rating` (mean fit-split rating per item); FilterTool
`min_rating` → causal `avg_rating >= ?` subquery and `order_by=average_rating`
→ causal-rating index path; `min_rating_number`/`price` remain fail-loud.
`run_agent_eval` now loads the `rating` split column. 25/25 policy tests pass.
`first_seen_ts` = min timestamp per namespaced item over *cleaned* parquet.
Cleaning = drop missing-required + dedup(user,asin,**timestamp**) keep-last +
optional rating∈[1,5] & ts∈[1995,2024) validation; **NO verified-purchase
filter**. Distribution: 75.97% of catalog ≤cutoff_1, 24.03% after, 12.12% after
cutoff_2. Hidden targets: 36/196 (Electronics 24, Toys 9, VG 3 — matches mix).

The proxy hides items with zero *cleaned interactions* pre-cutoff — real
availability data does not exist upstream (meta has no launch date).
`snapshot`/`no_filter` sensitivity run still open (Phase 4).

### Q10. What are we actually optimizing? 🔶 (decision recorded: flexible target)
**Decision 2026-11-21:** report BOTH exact-item hit and category-level hit.
First measurement (`investigations/q10_category_hit.json`): exact hits in
final recommendations = **0/196**; category-level target-hit = domain 55.6%,
main_cat 42.9%, any_cat 51.5%, specific_cat only 13.8%. Interpretation:
even the relaxed metric shows recommendations are mostly off-target — the
binding constraint is upstream retrieval, not metric strictness. Category-hit
adopted as a secondary A/B metric going forward.

Context bounds for exact-hit: pure popularity r@1000=10.2% (E-Q10); 24.5% of
targets share zero surface signal (E-Q11); ~7pp lost to temporal proxy
(Q13d). Realistic exact-recall ceiling ≈62% *candidate* recall.

---

## Data preprocessing pipeline

### Q11. Cross-domain user identity 🔶 (collision implausible; pollution measurable)
**20.25%** of 18,743,004 train users (3,794,676) are active in >1 domain.
`user2id` keys are raw Amazon IDs — `tag_domain.py` states the merge is
deliberate. **Collision check** (`investigations/q11_collision_proxy.json`):
Amazon reviewer IDs are account-level so same-ID=same-person is plausible and
no positive collision evidence exists; per-domain rating means are consistent
(4.21/4.20/4.40) — no different-population signal.

**But the measurable harm is real:** among the 140 campaign_005 eval users,
38.6% have multi-domain history; mean 26.9% of a user's train history sits
OUTSIDE the request's domain; 20.8% of requests have majority-outside
history; 28 requests have the target domain as the *minority* history domain.
Merged history can pollute MemoryTool.top_categories / SimilarTool seeds with
cross-domain items. Open: does restricting history to the request domain help
or hurt? (needs an eval ablation — not measurable offline.)

### Q12. `train_core` k-core threshold ✅ ANSWERED (K=5 is fine — not the problem)
Swept K∈{none,2,3,5,10} replicating the exact iterative bipartite filter on
48.69M unique train pairs (`investigations/q12_kcore_sweep.json`):

| K | pairs | core items | targets w/ ANY cooc | max_sim p90 |
|---|---|---|---|---|
| none | 48.7M | 2.00M | 98/392 | ~0.002 |
| 2 | 37.8M | 1.23M | 98 | ~0.004 |
| 3 | 29.7M | 861k | 96 | ~0.004 |
| **5 (current)** | **19.4M** | **487k** | **94** | ~0.005 |
| 10 | 7.55M | 158k | 74 | ~0.008 |

Attrition uniform across domains (~40% of pairs kept @K=5). **Lowering K gains
~4 co-occurrence targets while tripling data — the CF signal is absent, not
filtered.** K=5 was a deliberate protocol choice (`temporal_train_core`,
train-only filtering, documented in stage_3.manifest.json).

### Q13. `first_seen_ts` provenance ✅ ANSWERED — **deepened 2026-11-20 (user recheck)**
Cleaning chain: drop missing-required + dedup(user,asin,**timestamp**) keep-last
+ optional rating∈[1,5] & ts∈[1995,2024) validation; **NO verified-purchase
filter**. Distribution: 75.97% of catalog ≤cutoff_1, 24.03% after, 12.12% after
cutoff_2.

**Decomposition** (`investigations/q13c_hidden_decomp.json`): the 36 hidden
targets are NOT one phenomenon — hidden-rate rises with target distance from
cutoff (<1mo 0% → 1-3mo 11% → 3-6mo 15% → 6-12mo 23% → >12mo 40%). Of the 36:
6 have first_seen ≤30d after cutoff (possible proxy error — item may have
existed earlier), 14 ≤90d, 22 >90d; **8 have first_seen == target timestamp**
(the item's first-ever interaction IS the held-out target → invisible under
*any* rewind, true cold-start); 0 have first_seen ≤cutoff but hidden.

**Protocol comparison** (`investigations/q13d_protocols.json`; ceiling =
best-category rank≤K under rating_number ordering, oracle-category upper
bound, all-196 denominator):

| protocol | hidden | r@200 | r@1000 |
|---|---|---|---|
| A current (single cutoff + first_seen) | 36 (18.4%) | 56.6% | 68.4% |
| B per-target rewind | 8 (4.1%) | 59.7% | 75.0% |
| C cutoff near end-of-data | 0 | 59.7% | 75.5% |
| D no visibility filter | 0 | 59.7% | 75.5% |

**`Date First Available` check** (`investigations/q13b_date_available.json`,
2,638,155 meta rows scanned): parseable coverage = Electronics 93.7%,
Video_Games 93.6%, **Toys_and_Games only 18.4%**. Where both exist, lag
(first_seen − available) median ≈ 174–231 days, p90 ≈ 3.4–4.9 years — i.e.,
items are typically *reviewed* ~6–8 months after they become available, so
first_seen systematically **overstates** the hidden ceiling (proxy error is
real, direction = ceiling too pessimistic). Noise: 6–9.7% of items have
available-date AFTER first review (junk dates exist, e.g. "July 6, 1931"),
and Toys' 18% coverage means it can't serve as a universal filter.
**Important:** availability date is a fixed historical fact, NOT a mutable
snapshot — unlike rating_number it is causal-safe under every protocol and
could legitimately replace/augment first_seen_ts (needs junk-date cleaning +
Toys fallback).

So the proxy costs ~7pp of ceiling vs B and ~7pp vs C/D — real but not the
dominant loss. **Critical caveat for C/D:** meta `rating_number`/`price`/
`average_rating` are scrape-time snapshots → they carry post-cutoff (future)
information under EVERY protocol; only train-derived signals are causal.
Protocol B is the only one that is both causal-friendly (per-request as_of)
and keeps almost all targets visible — but it requires per-request corpus
snapshots the current single-corpus design doesn't support.

### Q14. Item dedup / catalog integrity ✅ ANSWERED (catalog is clean)
- ASINs appearing in >1 domain: **0 / 2,637,776** — domains are disjoint at
  ASIN level (no `Domain::ASIN` collisions possible).
- Within-domain duplicate ASINs: **0** (meta dedup keep-most-complete worked).
- Exact normalized-title dup groups: 95,783, but only **1,073 span domains** —
  mostly same-domain re-releases/variants (e.g., "SteelSeries Arctis Pro" two
  ASINs). Catalog inflation is modest; not a retrieval-noise source.
(`investigations/q11_q13_q16_probes.json` → Q14)

### Q15. Missing category metadata ✅ ANSWERED (source-data gap, not preprocessing)
Raw meta scan of all 3 `meta_*.jsonl.gz` joined to corpus
(`investigations/q15_raw_vs_processed.json` + `q15_meta_flags.parquet`):
- raw has_categories: VG 90.8%, Toys 90.0%, Electronics 92.0%
- corpus identical to 3 decimals; **preprocessing loss = 0 items**
  (the 379 meta rows absent from corpus are unmapped items, not drops)
- missing-cat rate vs rating_number: <5→10.9%, 5–49→9.6%, 50–499→5.6%, ≥500→3.1%
  → uncategorized items are also lower-popularity (double penalty confirmed)

Enrichment (option d-ish) remains a choice, but it's fixing *source* sparsity.

### Q16. `rating_number` as popularity proxy ✅ ANSWERED (it's real and good)
= raw meta `rating_number` string → numeric (Amazon "global ratings" count).
Distribution over 2.64M items: **median 15, p90 239, max 1,034,896;
27.2% of items have <5 ratings; 0 NULLs.** Spearman vs train interaction
count = **0.731**, vs held-out interactions = **0.650** — it genuinely
predicts what users interact with. Implication: Q18's masking hides the
single best ordering signal the system has.

### Q17. Interaction dedup/binarization ✅ ANSWERED (no leakage)
- 72,093 duplicate (user_idx,item_idx) rows in train = same pair at *different*
  timestamps — cleaning dedups on (user,parent_asin,**timestamp**), so repeat
  purchases legitimately survive. `user_items` is binary (presence).
- train∩validation shared pairs: **2,669** (0.03% of val pairs); train∩test:
  **855** — repeat purchases across the boundary, NOT target leakage
  (targets = first val interaction per `select_fit_target`).
- User-side leak: 1,353/1,353 sampled cohort users have train-pair count ≥
  recorded `history_size`; `user_items` is built from train only
  (`prepare_train_core`/`build_core_model` code path verified).
(`investigations/q17_q20_splits.json`)

### Q18. Mutable-field masking ✅ ANSWERED — **CONFIRMED BUG**
`historical_static_catalog` NULLs price/average_rating/rating_number for ALL
2,003,873 visible items. Consequences measured on the real corpus
(`investigations/q18_null_masking.json`):
- FilterTool `ORDER BY rating_number` degenerates to `item_id` order —
  empty-filter "popularity" top-10 vs true ranking = **0/10 overlap**
- `price_max`/`min_rating`/`min_rating_number` filters return **0 matches**
  (snapshot control: 424k / 1.33M / 67k matches)
- Cascade: ~70% of FilterTool trajectory calls were empty-filter popularity
  dumps → arbitrary-ordered candidates; price-constrained requests silently
  got 0 candidates; **and §6.6's category recall numbers were themselves
  corrupted** (Q4: true ceiling is 38.7% r@200, not 21.3%)

Fix decision: **IMPLEMENTED** (user approved causal-proxy approach).
`apply_metadata_policy` accepts `popularity={item_id: fit_interaction_count}`
→ temp `item_popularity` table w/ covering indexes; `run_agent_eval` passes
fit_df counts; FilterTool remaps masked `order_by` → `popularity` (index-driven
~1s query) or falls back to item_id order + explicit note when no proxy;
masked-field filters now raise ToolInputError instead of silent 0 matches.
`rating_number` stays masked (scrape-time snapshot = future leak under every
protocol). Verified: 1.05s empty-filter, category filters fast, 207 tests pass.
Other eval callers (candidate_recall/ranking_eval/policy_chain_eval/
planner_query_replay) don't pass popularity yet → item_id fallback + note.

### Q19. Dense embedding inputs ✅ ANSWERED (not title-only; test blocked)
`build_semantic_embeddings.py` doc text = `title\nstore\nmain_category\ncategories`
field-lines — categories ARE included. Unused: description, features, price,
ratings. `metadata_policy='runtime_snapshot_not_historical_causal'` — embeddings
see current metadata, not as-of. Enriched-text recall test is **blocked by the
read-only constraint** (needs full-catalog re-embed; oracle-sample-only can't
produce catalog-wide recall). Cheaper open hypothesis: query/doc format
mismatch (field-line docs vs raw query text).

### Q20. Split boundary sanity ✅ ANSWERED (clean, intended)
- Timestamps: train max = cutoff_1 exactly, 0 rows past; validation strictly
  inside (c1,c2]; test strictly after c2 — **0 violations**.
- Segments: cold=0 / sparse=1–4 / warm≥5 verified on 1,353 sampled cohort users
  (exact match 1,343, train≥recorded 1,353, recorded>train **0**).
- Cutoffs are **global across domains by code** — single cutoff_1/cutoff_2 in
  `_streaming_temporal_stage3`; intended since merged user histories need one
  timeline. All 3 domains respect both.
(`investigations/q17_q20_splits.json`)

---

## EDA coverage gaps

The read-only pass covered most of these. Status per item:

| E-Q | status | where |
|---|---|---|
| E-Q1 cross-domain users | ✅ done → Q11 | q11_q13_q16_probes.json |
| E-Q2 item duplication | ✅ done → Q14 | same |
| E-Q3 k-core attrition | ✅ done → Q12 | q12_kcore_sweep.json (per-domain kept%: E 39.7/T 38.4/VG 46.5 @K=5 — uniform) |
| E-Q4 first_seen bias | ✅ done → Q13/Q9 | distribution + per-domain hidden shares measured; boundary-crowding histogram not separately computed (minor gap) |
| E-Q5 category coverage | ✅ done → Q15 | raw-vs-processed join, missing-rate vs rating_number |
| E-Q6 rating_number dist | ✅ done → Q16 | median/p90/max, <5 share, Spearman 0.73/0.65 |
| E-Q7 dedup & leakage | ✅ done → Q17/Q20 | q17_q20_splits.json |
| E-Q8 text-field coverage | ✅ done → `eq8_text_fields.json`: titles ~never empty (median 11–19 tok); **description 58–66% coverage (median ~500 chars) and features 71–80% exist in raw meta but are UNUSED** (corpus has no columns for them; embeddings don't use them) — available enrichment material for Q2/Q19 |
| E-Q9 temporal density | ✅ done → `eq9_temporal_density.json`: 64M rows/302 months; post-cutoff months run 0.72–1.08× trailing median — **val/test windows are NOT atypical; held-out targets representative of deployment** |
| E-Q10 popularity ceiling | ✅ done | eq10_popularity_ceiling.json |
| E-Q11 predictability ceiling | ✅ done | eq11_target_predictability.json |

**All E-Q1–E-Q11 are now done.** The EDA questionnaire is fully closed.

---

## Process

### Q21. Commit strategy ⬜ (still yours — and now blocked by scope)
The FilterTool SQL fix + index are in the working tree uncommitted, alongside
the earlier union-candidate changes. Note: the read-only investigation added
only `investigations/` scripts+outputs (no pipeline changes). Decide commit
batching whenever ready.

### Q22. Branch/PR scope ⬜ (still yours)
### Q23. Sample size for A/Bs ⬜ (still yours — one campaign so far)

---

## What changed in the bottleneck picture after this pass

1. **Q18 is the single highest-impact confirmed bug** — it corrupted FilterTool
   ordering AND silently zeroed all price/rating filters AND invalidated part
   of our own §6.6 evidence. Fixing it likely matters more than any retrieval
   or ranking change.
2. **The category-filter ceiling is ~2× higher than reported** (38.7% r@200
   true vs 21.3% corrupted) — Phase 1's expected gain went UP.
3. **Popularity is validated as the dominant usable signal**: pure popularity
   60.3% rescue@10 vs baseline 31.75%; learned pop+cat_match 71.4%; rating_number
   Spearman 0.73 with real interactions. CF is dead at every k-core K.
4. **~62% is the realistic eval ceiling** (75.5% signal-sharing × 81.6% temporal
   visibility) — bounds all absolute numbers.
5. **Data pipeline is largely exonerated**: splits clean, no leakage, k-core
   fine, catalog clean, categories lossless, cross-domain merge deliberate.
