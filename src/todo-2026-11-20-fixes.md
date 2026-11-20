# Fix-phase TODO — post-investigation (draft, awaiting your decisions)

Created 2026-11-20 after the read-only pass completed
(`todo-2026-11-20.md` + `todo-2026-11-20-q13-recheck.md` — all items done,
all E-Q1–E-Q11 closed). Evidence base: `investigations/INVESTIGATION_REPORT.md`
+ `BOTTLENECK_OPEN_QUESTIONS.md`.

Rules for this phase: pipeline changes ARE allowed now, but each fix gets
GitNexus impact analysis before editing, `detect_changes` before commit,
and A/B on the same campaign_005 exp_5 152-request set for comparability.

## READY — evidence-justified, no decision needed

- [ ] **F1. Commit the FilterTool SQL fix** (working tree, uncommitted)
      - `compile_filters.py` IN-subquery rewrite + `idx_temp_item_categories_category`
      - Verified: 'Enclosures' 38.6s→0.37s; 366 tests pass
      - Steps: `detect_changes(scope=all)` → commit (message: why = correlated
        EXISTS caused 15/15 category-filter timeouts + SearchTool latency)
      - Blocker: none, just your go-ahead (Q21 partially answered by this)

- [ ] **F2. Q18 masking fix — causal popularity ordering** (recommended approach)
      - Evidence: rating_number is best ordering (Q4) AND best popularity
        proxy (Q16, Spearman 0.73) BUT is a scrape-time snapshot = future leak
        under any protocol (Q13d). Train-interaction count is causal,
        pre-cutoff by construction, already in pipeline (scores/user_items).
      - Implementation sketch: under `historical_static_catalog`, order
        FilterTool by train interaction count (log-scaled) instead of
        rating_number; make price/min_rating/min_rating_number filters
        return an explicit "unsupported under historical policy" error
        instead of silent 0 matches.
      - Verify: empty-filter top-10 should approximate true popularity order;
        category recall ceiling should move from item_id-order (0.65% r@200)
        toward rating_number-order (38.7% r@200) — measure on the Q4 harness.
      - **Needs your approval of this approach** (alternatives: snapshot
        ordering = leaks future; report-only = accept degraded eval)

## DECISION-BLOCKED — your call required (see BOTTLENECK_OPEN_QUESTIONS.md)

- [ ] F3. Phase 1 planner prompt A/B — blocked on **Q1** (always-on leaf
      category filter vs optional leg) + **Q21/Q22** (commit/branch strategy)
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
