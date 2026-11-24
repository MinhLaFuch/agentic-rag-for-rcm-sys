# Read-only investigation report — retrieval/ranking bottleneck

Date: 2026-11-20. Scope: Priority A (bugs) → B (ceilings/floors) → C (diagnostics)
per task spec. **No pipeline code, data, configs modified; nothing committed.**
All scripts + raw outputs under `investigations/`. Fixed target set: campaign_005
exp_5 run_1 (152 requests, 196 held-out targets; 116 requests have targets).

Per-item detail (counts, exact method/query, example rows, confidence + failure
modes) lives in the referenced JSONs; this file is the consolidated verdict.

---

## A. Confirmed bugs

| item | key number | confidence | implication for Phase 1–5 |
|---|---|---|---|
| **Q18 NULL masking breaks FilterTool** | price/avg_rating/rating_number NULL for **all 2,003,873** visible items under `historical_static_catalog`; empty-filter top-10 vs true popularity = **0/10 overlap**; price/rating filters = **0 matches** (snapshot: 424k/1.33M/67k) | **High** — real FilterTool queries on real corpus, both policies | **Phase 1 blocker→fix first.** Every recorded FilterTool "popularity" result was item_id-ordered noise; price-constrained requests silently got 0 candidates. Needs a pre-cutoff popularity proxy exposed to tools (design decision) |
| **Q18 cascade — §6.6 recall was corrupted** | category_sql_recall read rating_number through the masked view → its "popularity" ranks were item_id order. TRUE rating_number best-cat recall: **r@200=38.7%, r@1000=49.0%** (median rank 42) vs eval-actual item_id order **0.65%/12.3%** | **High** — same target set, same method, only ordering key changed (`q4_filter_orderings.json`) | The category-filter ceiling is ~2× what we reported — the upside of fixing Q18 is larger than believed. Phase 1 expected gain should be re-estimated upward |
| SearchTool timeouts (Q3) | 100/108 steps >5s-or-error, median 6.1s — but raw FTS replay of all 40 unique queries ≤2.9s select/≤0.6s count; 77.5% carried structured filters hitting the **pre-fix** correlated EXISTS | **High** for root cause (same bug as FilterTool, already fixed in tree); **Med** that masked-view overhead adds residual latency | Phase 3 deprioritized — timeouts were the filter bug, not FTS. Re-measure after fix lands |

## B. Ceilings and floors (MEASURED)

| item | key number | confidence | implication |
|---|---|---|---|
| E-Q10 popularity-only ceiling | Global rating_number rank of 196 targets: **r@10=1.5%, r@100=2.0%, r@1000=10.2%**, r@10k=25.5%, r@100k=63.3%; median target rank **48,063/2.64M** | **High** — exact ranking, all targets found in catalog | A trivial popularity list beats the whole agent pipeline (~0% tool recall). Phase 2/5: popularity is a strong prior, not noise — scorer design must exploit it |
| E-Q11 target predictability | **75.5%** of targets share ≥1 surface signal; **24.5% (48/196) share NOTHING**. By kind: cold_text 55%, personalized 63%, similar 86%, exclusion 96% | **Med-High** — definitions are generous (any shared flat category string counts); Vietnamese tokenization likely understates cold_text text-overlap | Hard ceiling: even perfect retrieval+ranking caps ~75% target recall (×~82% temporal visibility ≈ **~62% realistic max**). Phase 5 eval interpretation must use this bound |
| Q6 scorer comparison (126 competition-conditioned targets) | BaselineScorer exact = **31.75%** rescue@10 (=§6.7 ✓); **pure popularity = 60.3%**; honest learned rerank [pop,cf,cat_match] CV-by-request = **71.4%**; retrieval-blend variants biased-down (injected targets have retr=0) | **High** for v1a/v1b/v5 (no retrieval features used); **Med** for v2–v4 (structural bias); v5-all-features=100% was leakage, discarded | **Phase 2 confirmed + redirected:** CF term actively hurts; popularity+category-affinity learning doubles rescue. Retrieval-score blending cannot be validated by injection — needs production A/B. Phase 5: replace CF, don't tune it |

## C. Data/retrieval diagnostics (MEASURED)

| item | key number | confidence | implication |
|---|---|---|---|
| Q17 split hygiene | 0 cutoff violations; 72,093 dup train rows = same pair at different timestamps (dedup key includes ts → legitimate repeats); train∩val pairs 2,669 (0.03%), train∩test 855; 1,353/1,353 sampled cohort histories ≤ train counts | **High** | No leakage bug. Phase 4 can report absolute numbers without split-integrity caveat |
| Q20 segments/cutoffs | cold 4.96M / sparse 3.41M / warm 1.25M; boundaries exact (0 / 1–4 / ≥5); cutoffs global across domains **by code** (single cutoff_1/2, merged user timelines) | **High** | Intended design, verified. Phase 4: fine as-is |
| Q11 cross-domain users | **20.25%** of 18.74M train users active in >1 domain (E+Toys 2.33M, E+VG 835k, all-3 471k); histories merged into one user_items row; user2id keys raw Amazon IDs, no prefix | **High** for counts/merge; **Low-Med** on collision (unprovable) | Deliberate per tag_domain.py. Phase 5: cross-domain history may actually HELP warm-segment signal; not a bug |
| Q12 k-core sweep | K∈{none,2,3,5,10}: pairs 48.7M→7.6M, core items 2.00M→158k; targets with ANY co-occurrence **98→98→96→94→74**; max_sim p90 ≈0.003–0.008 at every K | **High** — exact iterative k-core replication on unique pairs | K=5 is NOT the CF problem — lowering K to 2 gains ~4 targets while tripling data. Phase 5: CF needs a different model, not different K |
| Q13 first_seen provenance | min timestamp per namespaced item over cleaned parquet; cleaning = drop-missing + dedup(user,asin,ts) + optional rating∈[1,5]/ts∈[1995,2024); **no verified-purchase filter**. 24.0% of catalog first_seen >cutoff_1; hidden targets 36/196 (E24/T9/VG3) | **High** — code + distribution measured | Phase 4/P3: the ~18% hidden ceiling is a *proxy* artifact partly — items with zero pre-cutoff interactions are hidden even if purchasable. Sensitivity run still warranted |
| Q14 ASIN/title duplication | ASINs in >1 domain: **0**; within-domain ASIN dups: **0**; normalized-title dup groups 95,783 but only 1,073 cross-domain | **High** | Catalog is clean; no inflation-driven retrieval noise. Phase 1–3 unaffected |
| Q15 category coverage | Raw meta has_categories 90.0–92.0%/domain = corpus identical to 3 decimals; **preprocessing loss = 0**. Missing-cat rate vs rating_number: <5→10.9%, ≥500→3.1% | **High** — full raw-meta scan joined to corpus | The ~8–10% uncategorized tail (incl. 42/155 oracle targets) is a **source-data gap** — Phase 3 content path must not rely on categories alone |
| Q16 rating_number | = raw Amazon rating count; median 15, p90 239, max 1.03M; **27.2% of items <5 ratings**; Spearman vs train interactions **0.731**, vs held-out **0.650** | **High** | rating_number IS a good popularity proxy — which makes Q18's masking bug worse (the best ordering signal was hidden) and validates popularity-heavy scoring (Q6) |
| Q19 dense embedding inputs | Doc text = `title\nstore\nmain_category\ncategories` field-lines — **not title-only**; description/features/price/ratings unused; metadata_policy = runtime snapshot (not historical) | **High** (code read) | Enriched-text test **blocked** by task constraint (needs full-catalog re-embed). Cheaper open hypothesis: query/doc format mismatch (field-line docs vs raw query text) |

## D. Inferred (not directly measured — flagged)

| item | basis | confidence | implication |
|---|---|---|---|
| §6.6 "true" FilterTool ceiling ≈ 38.7% r@200 | measured ordering on unmasked data; assumes planner picks the target's own best category (oracle choice) | **Med** — planner category accuracy unmeasured | Phase 1 gain estimate should use this as upper bound, not 21.3% |
| Realistic max target recall ≈ 62% | 0.755 (E-Q11 union signal) × 0.816 (temporal visibility) | **Low-Med** — assumes signal⇒retrievable and independence | Use as eval-ceiling sanity bound, not a target |
| Cross-domain same-ID = same person | Amazon reviewer IDs are account-level; deliberate merge in tag_domain.py | **Med** — no collision evidence either way | If collisions exist they'd inflate warm-segment histories; effect unquantified |
| Q6 v2–v4 retrieval-blend variants | biased downward because injected targets have retr=0 by construction | n/a — measurement artifact | Retrieval-score blending must be evaluated in a live A/B, not offline injection |
| first_seen over-hides targets | proxy = first *cleaned interaction*, not launch date; items purchasable but unreviewed pre-cutoff are hidden | **Med** — direction certain, magnitude unknown | Phase 4 snapshot/no_filter run quantifies one direction only |

## E. Bug/fix queue implied by this pass (for later decision — NOT implemented)

1. **Q18**: expose a pre-cutoff popularity proxy to FilterTool/SearchTool ordering
   (e.g., interaction-count column computed ≤as_of, or snapshot-policy ordering
   for ORDER BY only). Highest measured impact.
2. Re-run `category_sql_recall`-style measurement with unmasked ordering to
   re-baseline §6.6 (numbers now in `q4_filter_orderings.json`).
3. Planner prompt (YAML): prefer precise leaf-category filters now that the SQL
   path is fast; avoid empty-filter popularity dumps (Q18 made them noise).
4. Scoring: popularity-heavy + category-affinity beats CF-dominated baseline
   (Q6); CF/ItemKNN confirmed dead at every K (Q12) — replacement is a research
   decision (Phase 5), not a tuning exercise.
5. Eval validity: temporal sensitivity run (snapshot/no_filter) still open;
   E-Q11's ~25% no-signal targets bound all absolute numbers.

## Files

- `investigations/q18_null_masking.{py,json}` — Q18
- `investigations/q17_q20_splits.{py,json}` — Q17/Q20
- `investigations/q11_q13_q16_probes.{py,json}` + `q16_q11_patch.py` — Q11/Q13/Q14/Q15/Q16
- `investigations/eq10_popularity_ceiling.{py,json}` — E-Q10
- `investigations/eq11_target_predictability.{py,json}` — E-Q11
- `investigations/q4_filter_orderings.{py,json}` — Q4
- `investigations/q6_scorer_comparison{,_v2}.{py,json}` + `.features.parquet` — Q6
- `investigations/q3_search_timeouts.{py,json}` — Q3
- `investigations/q12_kcore_sweep.{py,json}` — Q12
- `investigations/q15_meta_scan.py` + `q15_meta_flags.parquet` + `q15_raw_vs_processed.json` — Q15
- `docs/investigations/INVESTIGATION_REPORT.md` — this file
