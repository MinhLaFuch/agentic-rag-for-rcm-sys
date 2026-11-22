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
- [x] **F10. Q8 A/B/C CF comparison — DONE 2026-11-22** (~15min total vs
      6h+ killed). Root cause of the 6h: `evaluate_recommender` dense path —
      ~7 users/batch × millions of users × per-row lexsort over 2.6M items.
      NOT BPR fit, NOT data prep (53s).
      - Fixes (device-flexible, CUDA→CPU fallback):
        * `recommenders/shared/get_device.py` — get_device() (renamed from
          device.py to satisfy the atomic-file layout rule).
        * `recommender.py` — `_topk_indices()` exact O(n) top-k (argpartition
          + exact recompute only on boundary ties); `_recommend_topk()` hook.
        * `random_recommender.py` — `_recommend_sparse` uniform sampler.
        * `bpr_mf_recommender.py` — `_recommend_topk` torch tiled top-k
          (256×131k blocks; verified identical to dense on CUDA) AND
          `_fit_torch` CUDA training: Q/bias on GPU, 5.9GB user-factor table
          streamed from CPU (~0.5MB/batch); deterministic mode preserves
          same-seed bitwise contract; numpy `_fit_numpy` kept as no-torch
          fallback. Fit: 743.5s for 20 epochs on the 4GB GPU.
        * `run_baselines.py`/`baselines.yaml`/`_schemas.py` —
          `eval_user_sample: 50000` (same seeded population all models) +
          batch_elements=200M.
      - RESULTS (`experiments/baselines/exp_001`, validation, 50k users):
        popularity recall@10=0.0077 > item_knn 0.0055 > bpr_mf 0.0054 >
        random 0. Popularity wins every metric incl. warm segment.
      - VERDICT: CF track (F6) closed — learned CF does not beat popularity
        for held-out targets; consistent with ItemKNN co-occurrence finding.
      - 114/114 recommender tests + 25/25 policy tests pass.

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
- [x] F4. Phase 2 scorer work — DONE 2026-11-22, live A/B NEGATIVE:
      injection evidence replicated on post-F2 pools (v5_honest 35.6%/47.1%
      vs baseline 8.2%/8.0% rescue@10; `q6_scorer_comparison_v4.json`),
      `LearnedScorer` wired (`mode: learned`, `learned_weights` config,
      ranktool_score_audit + run_agent_eval provenance, 5 unit tests).
      Live A/B `learned_scorer/exp_5` vs `filter_ab/exp_2_baseline`
      (identical 152 reqs): NET-NEGATIVE everywhere — cold_text
      task_success 0.65→0.45, target_reachable 0.50→0.143; personalized
      recall@10 0.025→0. Negative CF weight demotes personalization;
      injection rescue can't see whole-list quality costs.
      `scoring.yaml` reverted to `mode: baseline`; learned mode kept for
      future refits (needs new live A/B).
- [x] F5. Phase 3 retrieval improvements — Q2 DONE 2026-11-22, NEGATIVE:
      categorization layer built + live-tested twice. Full artifact
      (229,975 items, `exp_3`) collapsed target_reachable (0.50→0.071);
      gated vote_share≥0.30 (53,333 items, `exp_4`) recovered task_success
      but target_reachable stayed 0.118 vs 0.50 baseline — guessed
      categories pollute popularity-ordered filter pools. DISABLED; parquet
      kept at `investigations/item_categories_inferred_gated.parquet`.
      Q19 dense-format
      ablation DONE: all query formats ~0% recall — format is not the
      issue; user is evaluating multilingual embedding/BM25 replacement
      themselves. Descriptions/features remain unused enrichment material.
- [x] F6. CF research track — CLOSED by F10 (2026-11-22): bpr_mf
      recall@10=0.0054 < popularity 0.0077 on identical 50k eval population.
      Learned CF adds nothing over popularity for held-out targets.
- [ ] F7. Eval protocol work — Q9 DONE 2026-11-22 (causal mean-rating proxy
      wired for min_rating/average_rating; price+rating_number stay
      fail-loud); Q10 flexible metric stands; Q23 case-by-case.
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
