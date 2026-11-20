# Follow-up TODO — questionnaire answers + Q13 protocol re-check (read-only)

Started 2026-11-20 (same day, second pass). Same rules: no pipeline/data/config
changes, no commits; scripts + outputs only under `investigations/`.
Fixed target set = campaign_005 exp_5 (196 targets / 152 requests,
as_of=1617737606549).

## E-Q8/E-Q9 leftovers (user approved)

- [x] E-Q9 temporal density — `investigations/eq9_temporal_density.json` +
      `eq9_monthly_counts.csv`. 64.07M rows / 302 months. cutoff_1 (2021-04):
      post-cutoff months run 0.72–1.01× trailing-12m median — mild decline,
      no spike. cutoff_2 (2022-05): 0.83–1.08× — normal. Val/test windows are
      NOT atypical; held-out targets representative of deployment density.
- [x] E-Q8 text fields — `investigations/eq8_text_fields.json` +
      `eq8_meta_text.parquet` (2.64M meta rows). Corpus: titles ~never empty
      (median 11–19 tokens), store 0.6–3.2% empty. Raw meta: description is a
      LIST field, coverage 57.6% E / 65.7% T / 62.3% VG (median ~420–550
      chars) — UNUSED everywhere; features 71–80% coverage (median 5) —
      UNUSED. Corpus has NO description/features columns; embeddings use
      title+store+main_category+categories only. Truncation check on actual
      documents.jsonl: median 32 words, p99 56, max 381 → ~0% hit the 256-
      token cap; no truncation problem.

## Quick answers (no new computation)

- [x] Q11 collision: `investigations/q11_collision_proxy.json` — 140 eval users,
      38.6% multi-domain history; mean 26.9% of history outside request domain,
      20.8% of requests majority-outside, 28 requests target-domain = minority
      history domain. Rating means consistent (4.2/4.2/4.4) — no population-
      mismatch evidence. Verdict: ID collision unprovable but implausible
      (account-level IDs); REAL measurable issue = cross-domain history
      pollution for ~21% of requests.
- [x] Q12: the K-sweep (none/2/3/5/10) IS the grid — co-occurrence ~flat at
      every K, signal absent not filtered; finer grid adds no information.
- [x] Q14: answered inline (0 cross-domain ASINs, 0 within-domain dups,
      95,783 title-dup groups but only 1,073 cross-domain).
- [x] Q18: recommendation = expose causal train-interaction-count ordering
      (pre-cutoff by construction) instead of masked rating_number; meta
      rating_number is a scrape-time snapshot = future leak under ANY protocol.
- [x] Q19: not proven a bottleneck; dense ≤ BM25 but docs already include
      categories; cheap next step = query-format ablation on existing vectors.

## Q13 re-check (user flagged misunderstanding) — read-only

- [x] 1. `details` 'Date First Available' — `investigations/q13b_date_available.json`
      + `.parquet` (2,638,155 meta rows). Coverage: Electronics 93.7%,
      Video_Games 93.6%, Toys_and_Games only 18.4%. Lag first_seen−available:
      median 174–231d, p90 3.4–4.9y → first_seen OVERSTATES hidden ceiling
      (proxy error real). 6–9.7% have available-date AFTER first review
      (junk dates e.g. "July 6, 1931"). Availability date is causal-safe
      (fixed historical fact) → candidate replacement/augment for first_seen.
- [x] 2. Hidden decomposition — `investigations/q13c_hidden_decomp.json`
      + `q13c_targets.parquet`
      hidden-rate by months c1→target: <1mo 0%, 1-3mo 11.4%, 3-6mo 14.6%,
      6-12mo 23.2%, >12mo 40.0% (n=16/35/48/82/15).
      Of 36 hidden: 6 have first_seen ≤30d after c1, 14 ≤90d, 22 >90d;
      8 have first_seen == target_ts (first-ever interaction IS the target
      → invisible even under per-target rewind); 0 first_seen ≤c1 but hidden.
- [x] 3. Protocol comparison — `investigations/q13d_protocols.json`
      ceiling = best-category rank≤K under rating_number ordering (oracle-cat):
        A current:      hidden 36 (18.4%), r@200 56.6%, r@1000 68.4%
        B per-target:   hidden 8  (4.1%),  r@200 59.7%, r@1000 75.0%
        C late cutoff:  hidden 0,       r@200 59.7%, r@1000 75.5%
        D no filter:    hidden 0,       r@200 59.7%, r@1000 75.5%
      (C==D: fs-null items never crack top-1000 in target categories)
- [x] Update BOTTLENECK_OPEN_QUESTIONS.md Q13/Q11/Q18 + this file with results
