# Bottleneck investigation — consolidated context

**Updated:** 2026-11-24 · **Branch:** `distill-phase05-1` (all work uncommitted, no push/merge)
**Supersedes:** the former root files `RETRIEVAL_RANKING_BOTTLENECK.md`,
`BOTTLENECK_OPEN_QUESTIONS.md`, `TODO.md`, `context.md`, `idea.md` — merged here.
**Evidence:** per-experiment JSONs/MDs under `investigations/`; reports under
`docs/investigations/`. Fixed eval set: campaign_005 exp_5, 152 requests /
196 held-out targets, seed 42, `historical_static_catalog` policy,
as_of=1617737606549.

---

## 1. The question and the verdict

**Why do recommendation targets disappear in the agent pipeline** — retrieval,
ranking, temporal masking, preprocessing, request generation, or eval design?

**Verdict: the bottleneck is request/task specification, not retrieval
mechanics.** Campaign requests are category-level ("find 10 products in group
'Baby Floats'" — category holds 547–18,873 items, exactly 1 is the target);
targets are item-level. The request literally does not contain enough
information to identify the target. Direct benchmark on the same 196 targets:
campaign request text retrieves r@10 ≈ 0.000–0.005 under EVERY arm incl. full
catalog; LLM-written *descriptive* queries for the same targets reach
r@10 ≈ 0.18 (BM25 full catalog) / 0.37 (e5base restricted). Retrieval works
when the query is informative.

Caveat (product framing): descriptive queries measure SEARCH quality. For
recommendation kinds the information gap is intrinsic — F10 popularity
r@10 = 0.0077 on 50k validation users; low exact-target recall there may be
*correct*, not a bug. Do not mix the two metrics.

## 2. Measured bottleneck stack (ranked)

| rank | layer | loss | status |
|---|---|---|---|
| 1 | Request specification | category-level request vs item-level target; token overlap 13.3% even after faithful VI→EN; peer-rank ~1% under best arm | **the bottleneck** — no retrieval fix exists |
| 2 | Intrinsic next-item unpredictability | popularity r@10 = 0.0077 (F10 baselines) | research-level, no quick fix |
| 3 | Catalog eligibility | `first_seen` proxy hides ~17–24% of targets at pool stage | data ceiling; ~7pp vs availability-date protocol (q13d) |
| 4 | Retrieval mechanics | given weak queries, EN-BM25+dense near achievable; VI stack is demo-path only | mostly exhausted |
| 5 | Ranking/scoring | all 3 learned variants fail live A/B; baseline best measured | closed pending new evidence |

Stage funnel (campaign_005 exp_5): 72.5% of targets die at `retrieve`,
17% at `pool` (temporal-hidden), **zero reach `rank_input`**.

## 3. Experiment ledger — everything live-tested

| arm / intervention | vs baseline | verdict |
|---|---|---|
| F3 always-category FilterTool prompt | exp_2_baseline | task_success 0.589 vs 0.679 — **negative**; but spec_precision@10 0.935 vs 0.600 (**+0.335, CI excl. 0**) — filter works where it applies, hurts `similar` |
| F5 inferred categories (embedding kNN labels) | exp_2_baseline | **negative both variants** — guessed cats pollute filter pools; disabled |
| Learned scorer (`mode: learned`) | exp_2_baseline | **negative** — offline rescue didn't capture whole-list quality cost; reverted to `baseline` |
| HybridScorer w=4.0 (`mode: hybrid`) | exp_2_baseline | **mixed** — task_success up, target_reachable down; baseline stays |
| Union candidate pools ($union.candidates) | exp_5 | works as designed, **zero recall gain** — pooling can't create recall |
| ItemKNN / BPR-MF / popularity (F10 baselines, 50k users) | — | popularity r@10 0.0077 > item_knn 0.0055 > bpr_mf 0.0054 — **CF track closed** |
| Planner query replay, budget 500 | recorded limits | not the bottleneck — 5/464 request-runs gain targets |
| VI retrieval audit + translation | — | planner queries already ~96% English; VI problem is demo-path only |
| FilterTool SQL fix (correlated EXISTS → IN-subquery) | — | **fixed** — category filters 38.6s timeout → 0.37s |
| Q18 causal popularity (`rating_number`→train-count proxy) | — | **fixed** (`dc100d1`) — was NULL-masking the best ordering signal |
| Q9 causal `average_rating` proxy | — | implemented; price/rating_number correctly stay fail-loud |
| Prompt fix (`categories_exclude` bogus example → `exclude_item_ids`) | exp_2_baseline | preventative — invented-key rate was already 0; exp_2 rerun complete |
| **distill_spec (Phase 5, this branch)** | prompt_fix exp_2 | **net positive** — see §5 |

## 4. Investigation Q&A digest (Q1–Q23 + E-Q1–E-Q11)

All questions answered with measured evidence; full detail in
`docs/investigations/INVESTIGATION_REPORT.md` + per-item JSONs in
`investigations/`. Condensed:

- **Q1** FilterTool always-on: negative (see ledger). Baseline prompt kept.
- **Q2** Uncategorized tail (~24% of targets, 230k items): inferred-category
  enrichment negative → disabled; remains a retrieval dead-end.
- **Q3** SearchTool timeouts: root cause = same FilterTool EXISTS bug (fixed);
  FTS itself ≤2.9s.
- **Q4** Filter ordering: `rating_number` r@200=38.7% ≫ price 16.8% ≫ recency
  7.7% ≫ item_id 0.65% (eval's masked order) — popularity ordering correct,
  masking was the bug.
- **Q5–Q7** Scorers: popularity is the dominant usable signal (pure pop 60.3%
  vs baseline 31.75% injection rescue); learned pop+cat_match 71.4% offline —
  but live A/B negative. `scoring.yaml` stays `mode: baseline`;
  `LearnedScorer`/`mode: learned`/`hybrid` remain wired for future refits —
  **any enable requires a fresh live A/B**.
- **Q8** CF models: closed by F10 — nothing beats popularity.
- **Q9** Temporal masking: field audit done; rating proxy implemented;
  `first_seen` stays a proxy (~7pp ceiling cost); `snapshot`/`no_filter`
  sensitivity run still optional.
- **Q10** Metric: exact-item hits = 0/196; category-hit adopted as secondary.
  Realistic exact-recall ceiling ≈ 62%.
- **Q11** Cross-domain users: merge deliberate; ~21–39% of requests have
  majority-outside-domain history — measurable pollution, ablation untested.
- **Q12** k-core K: exonerated — co-occurrence flat at every K; signal absent.
- **Q13** `first_seen` proxy: 36/196 targets hidden (18.4%); "Date First
  Available" meta exists (causal-safe) but Toys coverage only 18.4% + junk
  dates — candidate replacement, not wired.
- **Q14** Catalog integrity: clean — 0 cross-domain ASIN dupes.
- **Q15** Missing categories: source-data gap, preprocessing loss = 0.
- **Q16** `rating_number` = Amazon rating count, Spearman 0.73 vs interactions.
- **Q17** Dedup/leakage: clean; 2,669 train∩val pairs are repeat purchases.
- **Q18** Masking bug: CONFIRMED + FIXED (see ledger).
- **Q19** Embeddings: doc text = title+store+main_category+categories;
  description/features unused; query/doc format mismatch real.
- **Q20** Split boundaries: clean, 0 violations.
- **Q21/Q22** Commit/PR scope: still open — git tree has pre-existing WIP +
  `stash@{0}`; stage carefully.
- **Q23** Sample size: n=152 → <~5pp deltas are noise (measured noise
  ~10–15pp on n=20–40 kinds, ~17pp on n=6 — see A_REPORT addendum).

## 5. Spec-satisfaction arc (idea.md → Phase 5)

**Idea:** score requests by whether output satisfies the *stated spec*
(category/price/exclusion membership) instead of hidden-item identity —
deterministic, no judge. Conventions locked: empty `recommended` →
`spec_precision@k` = 0 and stays in denominator; violation rates ship with
result-coverage; scalar-only metrics.

| phase | deliverable | result |
|---|---|---|
| 0.5/1 infra audit + Spec v1 | `package/evaluation/spec/` (pydantic Spec, kind-conditional validator, `spec_from_request` gold converter, `coarse_label` leaf-up ≥1000 + `main_category` fallback); 26 tests | done — reports `docs/investigations/distill_infra_audit/`, `distill_phase05_1/` |
| 2 backfill | `spec_*` on 7 existing arms | **F3 only significant spec gain** (cold_text +0.335 CI excl. 0) but loses via `similar`; learned scorer exclusion violations +0.10 sig. Report `docs/investigations/distill_phase2/` |
| 3 extractor benchmark | gold specs × 5 variants (760 LLM calls) | struct 100%, kind_acc 91–95% faithful, cold_text cat_f1=1.0; weaknesses: similar granularity, code_mix language slot, unanswerable oracle-bound. Report `docs/investigations/spec_benchmark/` |
| 4 ablation | variance + oracle-vs-predicted spec filtering | variance negligible; **predicted ≈ oracle** (cold_text 0.64 vs 0.60); taxonomy is a DAG → label→coarse via `label_coarse_map.json`. `docs/investigations/spec_benchmark/PHASE4.md` |
| **5 live A/B** | `distill_spec` flag → pre-planner spec injection (`package/agents/distill.py`, `PlanExecutor(spec_extractor=)`, `distilled_spec_block` prompt) | **net positive** — see below |

### Phase 5 result (`distill_spec/exp_1` vs `prompt_fix/exp_2`, same 152 requests)

| kind | baseline | distill | verdict |
|---|---|---|---|
| cold_text task_success | 0.65 | **1.00** | +35pp; spec_precision@10 +0.20 CI [0.06,0.37] excl. 0 — **real** |
| exclusion task_success | 0.25 | 0.45 | +20pp inside noise band — suggestive |
| personalized answer_ok | 0.70 | 0.975 | +27.5pp, no task_success metric |
| similar | 0.95 | 0.95 | unchanged — no F3-style collateral |
| unanswerable | 0.33 | **0.00** | −33pp n=6, likely real: spec suppresses clarification-seeking |

Distill cold_text spec_precision@10 = **0.935 — identical to F3's
always-filter score**, without F3's `similar` collapse. Cost: +152 extractor
calls (<$0.5). Flag stays **off** by default; overlay
`experiments/agent_eval/distill_spec_overlay.yaml`.

**Mitigation applied 2026-11-24:** `distilled_spec_block` now warns the spec
may be wrong/over-confident — trust the user, ask clarification when the spec
can't express the request. Not yet re-evaluated.

## 6. Open decisions (priority order)

1. **Request-content gap** — the root decision: which product is being built?
   (a) `descriptive` kind implemented (`descriptive_kind_overlay.yaml`, 196
   queries ready, eval pending — needs LLM key); (b) category-level scoring;
   (c) accept ceiling, optimize `task_success`. Supersedes embedding urgency
   for the *eval* question (still relevant for demo VI queries).
2. **distill_spec replicate + unanswerable fix validation** — rerun the arm
   (~$3, ~45min) to confirm the clarify-hint recovers unanswerable and firm up
   exclusion/personalized. Then decide flag default.
3. **Commit/PR scope (Q21/Q22)** — large uncommitted WIP across the whole arc;
   `configs/historical/.../baselines.yaml` LF fix must be included;
   `stash@{0}` must not be touched. Run GitNexus `detect_changes` first.
4. Standing: embedding-model decision (demo/VI only), F7/Q23 protocol
   (snapshot/no_filter sensitivity, larger eval set for decision-critical
   changes), optional scorer refit, embedding-based category completion
   (parked — prior A/B negative, F3 check shows uncategorized items reach
   recommendations at baseline rate).

## 7. Conventions & constraints

- Work on separate branches; **NO push, NO merge**. Code under `src/`.
- GitNexus `impact` before editing existing symbols; `detect_changes` before
  committing; `risk: UNKNOWN` = unresolved → confirm by text search.
- Every claim needs `file:line`/command evidence; uncertain → "chưa xác
  minh". No secrets in reports/artifacts.
- `summarize` crashes on non-scalar metric values; new `spec_`-prefixed
  metrics are registered in `evaluation/reporting/_adapter.py`
  `_DYNAMIC_PREFIXES`.
- Metric noise floor: n=152 requests → treat <~5pp as noise; measured
  run-to-run ~10–15pp on n=20–40 kinds.
- Overlay chains: `CONFIG_OVERLAY_PATH` = profile overlay FIRST, then
  experiment overlay (experiment wins).

## 8. Evidence index

| what | path |
|---|---|
| Consolidated investigation report | `docs/investigations/INVESTIGATION_REPORT.md` |
| Per-question JSONs + probe scripts | `investigations/q*.json`, `investigations/q*.py`, `investigations/eq*.json` |
| Bottleneck analysis (detailed, code-verified) | `docs/investigations/RETRIEVAL_RANKING_BOTTLENECK.md` |
| Open-questions log (Q1–Q23 detail) | `docs/investigations/BOTTLENECK_OPEN_QUESTIONS.md` |
| VI retrieval audit | `docs/investigations/vi_retrieval/REPORT.md` |
| Direct retrieval benchmark | `docs/investigations/retrieval_benchmark/REPORT.md` |
| Request-content analysis | `docs/investigations/request_content_analysis.md` |
| Distill infra audit | `docs/investigations/distill_infra_audit/REPORT.md` |
| Distill phases 0.5/1 (A–E + summary) | `docs/investigations/distill_phase05_1/` |
| Distill phase 2 (spec_* backfill, 7 arms) | `docs/investigations/distill_phase2/REPORT.md` |
| Spec benchmark phases 3+4 | `docs/investigations/spec_benchmark/{REPORT,PHASE4}.md` |
| Distill phase 5 (live A/B) | `docs/investigations/distill_phase5/REPORT.md` |
| Spec package | `package/evaluation/spec/` (26+ tests) |
| Extractor + injection | `package/agents/distill.py`, `PlanExecutor(spec_extractor=)` |
| Eval artifacts | `experiments/agent_eval/{prompt_fix,distill_spec,filter_ab,learned_scorer,hybrid_scorer,union_ab,descriptive_kind}/` |
