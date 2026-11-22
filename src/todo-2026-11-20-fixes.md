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
- [~] **F10. Q8 A/B/C CF comparison** — ROOT-CAUSED + FIX IMPLEMENTED
      2026-11-22, rerun in progress (shell 1e962b, log
      `investigations/f10_baselines_cuda.log`).
      - Root cause: NOT data prep (53s) and NOT BPR fit — it was
        `evaluate_recommender`'s dense path: batch_elements=20M ÷ 2.6M items
        = ~7 users/batch × millions of target-bearing users × per-row
        `np.lexsort` over the full catalog = ~1M O(n log n) sorts. Random and
        BPR-MF have no sparse path so they hit it directly.
      - Fixes (device-flexible, CUDA→CPU fallback per user requirement):
        * `recommenders/shared/device.py` — get_device() (cached CUDA detect).
        * `recommender.py` — `_topk_indices()`: exact O(n) top-k
          (argpartition + exact recompute only on boundary ties), replaces
          per-row lexsort; new `_recommend_topk()` fused hook.
        * `random_recommender.py` — `_recommend_sparse`: uniform sample of
          non-excluded items (top-k of iid scores IS a uniform subset).
        * `bpr_mf_recommender.py` — `_recommend_topk`: torch tiled top-k
          (256 users × 131k-item tiles ≈134MB blocks; item factors ~0.7GB on
          GPU, user factors gathered per chunk — full 5.9GB user matrix never
          leaves CPU). Verified bit-identical to dense path on CUDA toy.
        * `run_baselines.py` + `baselines.yaml` + `_schemas.py` —
          `eval_user_sample: 50000` (seeded, identical population for all
          models → fair comparison) + batch_elements=200M.
      - BPR-MF `_fit` remains numpy (torch CUDA port deferred — eval was the
        hog; revisit only if fit itself proves slow).
      - 118/118 recommender+evaluator tests pass; top-k equivalence verified
        vs lexsort on 300 randomized trials incl. ties/-inf.

## DECISION-BLOCKED — your call required (see BOTTLENECK_OPEN_QUESTIONS.md)

- [x] **F3. Phase 1 planner prompt A/B — DONE 2026-11-21, baseline wins**:
      Q1 decided: run BOTH variants — always-on leaf-category FilterTool vs
      current optional-leg — same 152 requests, compare stage funnel +
      task_success + category-hit.
      - F2 (Q18 ordering fix) committed as dc100d1 — category path now returns
        causal popularity ordering (~33.6% r@200 ceiling vs 0.65% item_id).
      - Overlays: `experiments/agent_eval/filter_ab_always_category_overlay.yaml`
        (variant A: prompt override via CONFIG_OVERLAY_PATH deep-merge — adds
        "ALWAYS run one FilterTool…" rule, drops price_max from example since
        masked filters now error) and `filter_ab_baseline_overlay.yaml`
        (variant B: current prompts.yaml unchanged).
      - Both replicated campaign_005 exp_5 settings (planner, template,
        reflect_rounds=0, seed 42, per_segment 20, request_scope all,
        multi_turn/jev off, item_knn reuse cache).
      - RESULTS (`scored.jsonl` per run):
        * Planner compliance: A used FilterTool in 126/152 reqs (58 w/ cat
          filter) vs B 74/152 (16 w/ cat) — prompt worked.
        * task_success: A 0.589 vs B **0.679** — A is WORSE.
        * task_success_relevant / hit_rate@10 / precision@10 / ndcg@10:
          identical (0.026 / 0.026 / 0.0026 / 0.0108).
        * target_in_any_path_pool identical 0.897; target_reachable A 0.110
          vs B 0.129.
      - VERDICT: always-on category filtering does NOT help — pool coverage
        was already saturated, extra FilterTool calls added noise/latency
        without target gains. Keep baseline prompt (Q1 resolved: optional leg).
      - Follow-up queued: rerun ranktool_injection_probe + q6 scorer
        comparison on BOTH new runs (post-F2 pools) for Q5/6/7 evidence.
- [~] F4. Phase 2 scorer work — UNBLOCKED 2026-11-21 (user: keep both
      scorers, gather more evidence). Plan: rerun ranktool_injection_probe
      + q6_scorer_comparison_v2 on the two new post-F2 filter_ab runs
      (fresh candidate pools) → compare v1a/v1b/v5_honest again before
      any production wiring decision.
- [~] F5. Phase 3 retrieval improvements — Q2 DECIDED 2026-11-21: build a
      categorization layer for the uncategorized tail (~24% of targets),
      likely embedding-relation based. Design needed. Q19 dense-format
      ablation DONE: all query formats ~0% recall — format is not the
      issue; user is evaluating multilingual embedding/BM25 replacement
      themselves. Descriptions/features remain unused enrichment material.
- [ ] F6. CF research track — still blocked on F10 (which model is fast
      enough to even produce a result).
- [ ] F7. Eval protocol work — Q9 REOPENED 2026-11-21 (user: masking fixed,
      take another look — field-level temporal audit needed); Q10 flexible
      metric stands; Q23 case-by-case.
- [x] F8. Cross-domain history ablation — DONE as offline exposure analysis
      (`investigations/f8_domain_ablation.json`, script f8_domain_ablation.py):
      domain-restricting MemoryTool history costs ~23% of interactions,
      changes top_categories moderately (Jaccard 0.71), but target-category
      coverage is FLAT (53.3%→54.2%) while 22.6% of recent-item seeds ARE
      cross-domain. Expected eval effect ≈ null → recommend skipping the
      eval run unless you want the causal answer anyway (needs MemoryTool
      domain arg + ~35min run).

## Suggested order if you approve defaults

1. F1 commit → 2. F2 (Q18 fix) → 3. re-run Q4 harness to confirm ceiling
moves → 4. F3 prompt A/B (Phase 1) → 5. F8 ablation (cheap, informative)
→ 6. F4/F5 per your scorer/retrieval decisions.
