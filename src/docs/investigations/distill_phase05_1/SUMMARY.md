# Phase 0.5/1 merged summary — distill infra workstreams

Branch `distill-phase05-1` · Reports: `A_REPORT.md` `B_REPORT.md` `C_REPORT.md` `D_REPORT.md` `E_REPORT.md` (same dir)

## Per-workstream results

- **A (prompt fix):** `prompts.yaml:35-36` bogus `categories_exclude` example replaced with real `exclude_item_ids` + `$S.constraints` ref (2-line diff, nothing else touched). Hash/resume impact verified — old trajectories genuinely invalidated via `_source_fingerprint` + `is_resumable`. Baseline invented-key rate was already **0** in exp_2 (the bad example wasn't followed); empty `filters:{}` = 33.7%. **Eval re-run BLOCKED: LLM_API_KEY invalid (HTTP 401)** — overlays ready at `experiments/agent_eval/prompt_fix_exp_{1,2}_overlay.yaml`, $0 spent.
- **B (masking audit):** masking = `apply_metadata_policy.py:9,109,156-158` on price/avg_rating/rating_number, only under `historical_static_catalog`. Interactions DO carry rating+timestamp → rating is causally recomputable and code already exists (`run_agent_eval.py:519-532`, ~76-88% coverage). **Price is a single snapshot — no temporal source exists anywhere**; that's the real blocker for `constrained`. Pre-mask: price non-null only 38.5% corpus-wide. Snapshot-price-only → 40 valid constrained requests generatable; rating-only → 0 (constrained needs price). Other leaks found: ~7.3k titles contain `$` (gift-card denominations), Best Sellers Rank/Date First Available in raw meta but not loaded.
- **C (taxonomy):** label-sequence reconstruction is essentially perfect (0 conflicts, 0 dup labels; only 2,769 distinct multisets). Fixed-depth coarse is bad (pos-2 median 3 items, 68% <10). **Proposal: `category_coarse` = deepest label with corpus frequency ≥1,000** (609 buckets, median ~2k, 0 buckets <10, 99.99% coverage); fallback `main_category`. Real target count = **196** (the "155" was a different artifact, candidate_recall exp_003). 12/196 targets uncategorized (6.1%).
- **D (Spec schema v1):** new `package/evaluation/spec/` — pydantic `Spec` + kind-conditional validator + injectable taxonomy validation + `spec_from_request` gold-converter (similar=clean, cold_text/exclusion/constrained=oracle-marked, others=partial). Implements BOTH coarse rules: `coarse_label(seq, counts, min_count)` with `COARSE_MIN_ITEMS=1000` (C's winner, auto-used) and `coarse_of(seq, coarse_depth)` kept as required-param fallback. **26 tests pass.** `main_category` fallback wired post-review (see follow-up).
- **E (unverified items):** exp_2_baseline trajectories verified backfill-ready (152 rows, joins on request_id; 40 empty-recommended = honest tool_errors). metrics.json auto-averages new numeric metrics; **report.md needs `_adapter.py:28-44` registry update** (`spec_` prefix not in `_DYNAMIC_PREFIXES`). Extractor prompt ≈ **0.4-0.5k tokens** — ~10-20% of planner cost.

## Decisions needed from user

1. **`coarse_depth`:** C proposes leaf-up N=1,000 (implemented as `COARSE_MIN_ITEMS`); confirm or pick N=10,000 (140 buckets) / fixed-k fallback.
2. **Masking direction:** unmask snapshot-price only (enables `constrained`, 40 requests, but price is post-cutoff snapshot = mild leak already flagged oracle) vs keep masked vs recompute-rating-only (unlocks nothing today — no kind uses rating). B lays out options+risks; no fix applied.
3. **Valid `LLM_API_KEY`** needed to run workstream A's two baseline evals (~$7-11 total, cap $12).

## Files changed

- `configs/agent/prompts.yaml` (A: 2-line example fix)
- `experiments/agent_eval/prompt_fix_exp_{1,2}_overlay.yaml` (A: new)
- `package/evaluation/spec/{__init__,_schema,_gold}.py` + `tests/evaluation/spec/test_spec.py` (D: new)
- `investigations/distill_phase05_1/*` (all reports + C's helper scripts/JSON dumps)

## Still unverified

- Whether gateway honors `response_format` json_object / temp=0 determinism (audit E).
- `reporting/_adapter.py` full metric registry beyond headline/dynamic prefixes.
- Whether layer-4/5 scorers tolerate unknown tool names in trajectories (DistillTool future).
- Run-to-run eval noise (needs the blocked second baseline run).

---

## Follow-up round (user review items — resolved)

- **`filters:{}` discrepancy resolved:** exp_2_baseline = 92 FilterTool calls, 31 empty (**33.7% call-level**); request-level = 74 requests invoked FilterTool, 31 had ALL calls empty (**41.9% of requests**). The older "~70%" figure came from **exp_5** (41 calls / 30 empty = 73.2%); exp_6 hybrid = 30.9%. Different runs/denominators — do not conflate.
- **155 vs 196:** confirmed — 155 belongs to `candidate_recall/exp_003`; agent_eval set = **196 targets**, 12 uncategorized (6.1%).
- **F3 uncategorized check (offline, done):** recommended-item uncategorized rate is ~identical — baseline exp_2: 327/1101 = **29.7%**, always-category F3: 360/1233 = **29.2%**. F3's deficit is NOT explained by uncategorized items in final recommendations (pool-level effect not ruled out — "chưa xác minh").
- **`prompts.yaml:25` fixed:** hate_categories line now states there is NO category-exclusion filter (avoid when picking categories_any). Applied BEFORE the baseline reruns so both runs share the final prompt.
- **`main_category` fallback wired:** `_gold.py` `_main_category()` + similar-branch fallback when taxonomy seq empty or coarse unresolved. New test `test_gold_similar_main_category_fallback`; **26 tests pass**.
- **`spec_` registry:** added `"spec_"` to `_DYNAMIC_PREFIXES` in `reporting/_adapter.py:46` so `spec_*` metrics reach report.md. Impact analysis: UNKNOWN → text search confirmed constant used only at `_adapter.py:61`.
- **Empty-list convention documented** in `package/evaluation/spec/__init__.py` docstring: `spec_precision@k`=0 on empty list, request stays in denominator; violation rates must ship with result-coverage; spec_* values must be scalar.
- **Manifest blocker fixed:** stage_4 manifest pins `baselines.yaml` hash `a2e926fa` (pre-`eval_user_sample`, LF). Historical snapshot was CRLF → normalized to LF, hash now matches. Root cause: commit `598b286` added `eval_user_sample: 50000` after manifest creation; snapshot preserved old content but with Windows line endings.
- **Baseline reruns:** exp_2 prompt-fix COMPLETED (`experiments/agent_eval/prompt_fix/exp_2/run_1`, 152/152). exp_1 crashed pre-loop on concurrent ItemKNN OOM, then on relaunch failed LLM health check — **key now returns 401 again** (worked for the whole exp_2 run; likely quota/revocation). Noise replicate still needs a fresh key. Spend ≈ one run (~$4-5.5), under cap.
- **Git hygiene:** working tree has pre-existing WIP (`build_requests.py`, `evaluation/_schema.py`, `run_agent_eval.py`, staged rename presentation from earlier stash/pop). Nothing committed; do not sweep unrelated changes into a commit.
