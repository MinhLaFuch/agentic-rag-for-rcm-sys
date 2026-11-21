# Fix-phase TODO — post-investigation

Created 2026-11-20 after the read-only pass completed
(`todo-2026-11-20.md` + `todo-2026-11-20-q13-recheck.md` — all items done,
all E-Q1–E-Q11 closed). Evidence base: `investigations/INVESTIGATION_REPORT.md`
+ `BOTTLENECK_OPEN_QUESTIONS.md`.

## DECISIONS RECORDED 2026-11-21

- **Q1 → A/B both variants**: planner prompt always-on leaf-category
  FilterTool vs current optional-leg behavior, same 152 requests.
- **Q8 → A/B/C test**: compare CF strategies — (A) ItemKNN baseline,
  (B) BPR-MF (`package/recommenders/offline/bpr_mf_recommender.py` already
  exists), (C) no-CF/popularity-only. Two-tower only if B shows signal.
- **Q10 → flexible target**: exact-item hit AND category-level hit both
  reported; category granularity levels (leaf/main/ancestor) measured.

Rules for this phase: pipeline changes ARE allowed now, but each fix gets
GitNexus impact analysis before editing, `detect_changes` before commit,
and A/B on the same campaign_005 exp_5 152-request set for comparability.

## DONE

- [x] **F1. Commit checkpoint** — `a3a7eb5` on tools-building (268 files,
      includes FilterTool SQL fix + all investigation artifacts)

## READY — evidence-justified, no decision needed

- [ ] **F1. Commit the FilterTool SQL fix** (working tree, uncommitted)
      - `compile_filters.py` IN-subquery rewrite + `idx_temp_item_categories_category`
      - Verified: 'Enclosures' 38.6s→0.37s; 366 tests pass
      - Steps: `detect_changes(scope=all)` → commit (message: why = correlated
        EXISTS caused 15/15 category-filter timeouts + SearchTool latency)
      - Blocker: none, just your go-ahead (Q21 partially answered by this)

- [~] **F2. Q18 masking fix — causal popularity ordering** — IMPLEMENTED,
      verified on real corpus, tests pass; pending commit + Q4-harness confirm.
      - What landed:
        * `apply_metadata_policy(..., popularity={item_id: cnt})` — new optional
          arg; builds `temp.item_popularity` covering EVERY visible item
          (fit counts + cnt=0 fill), with `(cnt DESC, item_id)` and
          `(cnt ASC, item_id)` covering indexes. `items` view unchanged →
          count()/FTS/category paths unaffected.
        * `run_agent_eval.py` passes fit_df interaction counts (causal:
          train-only for validation eval, train+val for test eval — both
          pre-as_of by construction).
        * `FilterTool`: masked `order_by` (rating_number/average_rating/
          price) → remaps to `popularity` when available, else falls back to
          deterministic `item_id` order WITH an explicit `order_by_note`
          (backward compat for callers that don't pass popularity).
          Explicit `order_by='popularity'` supported via an index-driven
          CROSS JOIN query (~1s vs 24s naive sort).
        * Masked-field FILTERS (price_min/max, min_rating,
          min_rating_number) now raise ToolInputError instead of silently
          returning 0 matches. Tests updated to the new contract.
      - Verified: empty-filter 1.05s top-5 = plausible top-train-count items;
        'Enclosures' 0.73s / 3,421 matches; ASC ordering 1.06s; 207 tests pass.
      - Caveat: callers other than run_agent_eval (candidate_recall,
        ranking_eval, policy_chain_eval, planner_query_replay) don't pass
        popularity yet → they get the item_id fallback + note, i.e. old
        behavior. Wire them later if those paths matter for A/B.
      - Remaining: commit (detect_changes first), optionally re-run Q4
        harness to confirm ordering quality end-to-end.

## IN PROGRESS

- [ ] **F9. Q10 category-hit probe** — DONE pending writeup:
      `investigations/q10_category_hit.json` + `_requests.parquet`.
      Exact-item hits in final recommendations = **0/196 targets** (consistent
      with zero targets ever reaching candidates). Category-level target-hit:
      domain 55.6%, main_cat 42.9%, any_cat 51.5%, specific_cat only 13.8%.
      → even the flexible metric shows recommendations are mostly off-target;
      the bottleneck is upstream (retrieval), not metric strictness. Useful
      as a secondary A/B metric going forward.
- [ ] **F10. Q8 A/B/C CF comparison** — RUNNING:
      `PYTHONPATH=. python benchmarks/run_baselines.py --eval-on validation`
      evaluates random/popularity/item_knn/bpr_mf on the same train_core fit
      + held-out targets with seen-exclusion (existing harness, no new code).
      bpr_mf = 20 epochs on core pairs — the decisive "does MF create signal
      ItemKNN can't" test. Output → experiments/ baseline dir.

## DECISION-BLOCKED — your call required (see BOTTLENECK_OPEN_QUESTIONS.md)

- [ ] F3. Phase 1 planner prompt A/B — **UNBLOCKED** (Q1 decided: run BOTH
      variants — always-on leaf-category FilterTool vs current optional-leg —
      same 152 requests, compare stage funnel + task_success + category-hit).
      Remaining sub-decision: prompt wording for variant A (draft for review).
      Also needs F2 (Q18 ordering fix) landed first or the category path
      still returns item_id-ordered noise.
- [ ] F4. Phase 2 scorer work — blocked on **Q5/Q6/Q7** (blend retrieval
      scores live-A/B? popularity weighting? HybridScorer?)
- [ ] F5. Phase 3 retrieval improvements — blocked on **Q2** (uncategorized
      tail: now we know description/features exist unused — enrichment is a
      new option) + **Q19 follow-up** (query-format ablation is cheap and
      unblocked if you want it)
- [ ] F6. CF research track — blocked on **Q8** (MF/two-tower in scope?)
- [ ] F7. Eval protocol work — blocked on **Q9/Q10** (first_seen vs
      Date-First-Available filter; target metric definition) + **Q23**
      (second campaign for A/B trust?)
- [ ] F8. Cross-domain history ablation — new item from Q11 recheck:
      restrict user history to request domain; measure effect on the 21%
      majority-outside requests. Cheap-ish eval variant, needs your go.

## Suggested order if you approve defaults

1. F1 commit → 2. F2 (Q18 fix) → 3. re-run Q4 harness to confirm ceiling
moves → 4. F3 prompt A/B (Phase 1) → 5. F8 ablation (cheap, informative)
→ 6. F4/F5 per your scorer/retrieval decisions.
