# Workstream A — Planner prompt `categories_exclude` fix + baseline re-run

**Date:** 2026-11-23 · **Branch:** `distill-phase05-1` (uncommitted) · **Scope:** A only

## 1. Evidence — the contradiction is real

Valid FilterTool filter keys (`package/tools/_schema.py:8-20`):

```python
FILTER_KEYS = {"domain", "price_min", "price_max", "include_missing_price",
               "min_rating", "min_rating_number", "categories_any",
               "categories_all", "store", "title_contains", "exclude_item_ids"}
```

Enforced at `package/tools/sql/filter_tool.py:73-75` (`unknown = set(filters) - FILTER_KEYS` → `ToolInputError`) and compiled at `package/tools/sql/compile_filters.py:183-358` (no category-exclusion clause exists anywhere; only `exclude_item_ids` at `compile_filters.py:347-358`).

The prompt example at `configs/agent/prompts.yaml:35-36` (pre-fix) taught the planner to emit `"categories_exclude": "$1.hate_categories"` — a key that does not exist and has no compile path. Any plan following the example gets `ToolInputError: unknown filter(s) ['categories_exclude']` → wasted step + reflect/retry.

## 2. Fix applied (diff)

Only the contradictory example changed; nothing else in `prompts.yaml` touched:

```diff
-      Example (exclude hate categories the user dislikes):
-      {{"steps": [..., {{"tool": "FilterTool", "args": {{"filters": {{"categories_any": "$1.love_categories", "categories_exclude": "$1.hate_categories"}, "limit": 30}}}}, ...]}}
+      Example (exclude items rejected in earlier turns via session constraints):
+      {{"steps": [..., {{"tool": "FilterTool", "args": {{"filters": {{"categories_any": "$1.love_categories", "exclude_item_ids": "$S.constraints.exclude_item_ids"}, "limit": 30}}}}, ...]}}
```

Rationale: there is **no** category-exclusion filter key, so the example now demonstrates the real exclusion mechanism (`exclude_item_ids`, a valid `FILTER_KEYS` member) fed from session constraints (`$S.constraints.exclude_item_ids`, populated by `Session.add_exclusions`/`update_constraints`, `package/agents/session.py:81-95`). Verified: `load_config('agent/prompts')` parses, `categories_exclude` no longer appears in the system prompt.

**Residual (open item):** `prompts.yaml:25` still says *"Use `$1.hate_categories` to exclude categories the user dislikes (if needed)"* — outside the example block, left untouched per scope. It can still prime the planner to invent a category-exclusion key; recommend a follow-up edit or a real `categories_exclude`/`exclude_categories` filter key.

GitNexus: `impact SYSTEM_PROMPT --direction upstream` → 2 candidates (planner `plan_executor.py:17`, inference `compose_llm.py`), planner symbol shows 0 resolved callers / risk UNKNOWN; confirmed consumers by text search: `plan_executor.py:17,107` (`.format` at plan time), `build_run_provenance.py:64-76`, `package/agents/planner/__init__.py:2`. Change is prompt-text only — no signature/behavior contract altered.

## 3. Hash / resume impact — verified

Two independent hash paths cover the prompt text:

- **Resume identity / protocol hash:** `scripts/evaluation/run_agent_eval.py:722-731` builds `resume_identity` including `"source_fingerprint": _source_fingerprint()`. `_source_fingerprint` (`package/evaluation/recommender/experiment/save_experiment.py:17-47`) SHA-256s **every `.py/.yaml` file under `package/`, `scripts/`, `configs/`** — `configs/agent/prompts.yaml` is included, so any prompt edit changes `protocol_hash`. Old trajectory records carry the old `evaluation_protocol_hash`; `--resume` against them raises `SystemExit("Resume protocol mismatch…")` at `run_agent_eval.py:767-768`, and `is_resumable` (`:127-148`) returns False on hash mismatch (`:137-138`). → **Old resumes are invalidated; they cannot be silently treated as equivalent.**
- **Provenance artifact:** `build_run_provenance` (`package/evaluation/provenance/build_run_provenance.py:64-68`) hashes the formatted planner system prompt → `planner_prompt_sha256` in metrics.json provenance; it will differ from the exp_2 baseline value.

Affected artifacts/identities: `evaluation_protocol_hash` per trajectory record, `resume_identity_sha256` in `protocol_manifest`, `planner_prompt_sha256`/`planner_memory_prompt_sha256` in metrics.json, and `_source_fingerprint` consumers in recommender experiment stores (`ranking_run_store.py:48` "resume identity mismatch").

## 4. Baseline re-run — BLOCKED (invalid API key)

Overlays created (identical to `experiments/agent_eval/filter_ab_baseline_overlay.yaml` except trajectory_file + experiment_dir; no `descriptive_queries_path`):

- `experiments/agent_eval/prompt_fix_exp_1_overlay.yaml` → `experiments/agent_eval/prompt_fix/exp_1/run_1`
- `experiments/agent_eval/prompt_fix_exp_2_overlay.yaml` → `experiments/agent_eval/prompt_fix/exp_2/run_1` (noise run, ready)

Command attempted (background):

```
CONFIG_OVERLAY_PATH="...multi_domain.overlay.yaml;...prompt_fix_exp_1_overlay.yaml" \
  .venv/Scripts/python scripts/evaluation/run_agent_eval.py
```

with `LLM_BASE_URL=https://api.xah.io/v1`, `LLM_API_KEY=<redacted>`.

**Result:** run died at the LLM health check (`run_agent_eval.py:670`) after corpus load (~17s) — `health_check()` → HTTP 401. Direct verification:

- `POST https://api.xah.io/v1/chat/completions` with the provided key → `{"error":{"code":"authentication_error","message":"The API key is invalid."}}` (also fails with `x-api-key` header; `/v1/models` is public and lists `gpt-5.5`, so the gateway is up — the **key itself is rejected**).
- `llm.health_check()` via `build_llm_provider(load_config('agent/llm'))` → `False`.

No partial artifacts were written (failure precedes trajectory-file creation). **No eval cost incurred.** To proceed, a valid `LLM_API_KEY` for `https://api.xah.io/v1` is required, then re-run the same command — the overlay is ready; run 2 overlay also staged.

## 5. Baseline metrics (exp_2_baseline/run_1, n=152, planner only) — pre-fix reference

From `experiments/agent_eval/filter_ab/exp_2_baseline/run_1/trajectories.jsonl` + `metrics.json`:

| metric | value |
|---|---|
| FilterTool calls | 92 across 152 requests |
| `filters: {}` empty | 31/92 = **33.7%** |
| invented filter keys in recorded steps | **0** (`categories_exclude` appears nowhere in the 152 records — the model did not follow the bad example in this run) |
| FilterTool `tool_error`s | 6, all `category '…' not found` (ToolInputError class) |
| other step errors | `bad_reference` ×67, `tool_error` ×32 (mostly RankTool "candidates is empty") |

`metrics.json` summary (planner, `all` segment):

| kind | n | task_success | target_reachable | tool_selection_ok | cost/req |
|---|---|---|---|---|---|
| ambiguous | 6 | 1.00 | – | 1.00 | $0.0239 |
| cold_text | 20 | 0.65 | 0.50 | 1.00 | $0.0323 |
| exclusion | 40 | 0.475 | 0.00 | 0.525 | $0.0377 |
| personalized | 40 | – | 0.15 | – | $0.0284 |
| similar | 40 | 0.95 | 0.00 | 1.00 | $0.0266 |
| unanswerable | 6 | 0.00 | – | 1.00 | $0.0296 |

Note: the infra-audit claim of planner-invented `categories_exclude` (REPORT.md A.2, citing `RETRIEVAL_RANKING_BOTTLENECK.md:499` / `q3_search_timeouts.json`) does **not** reproduce in this baseline artifact — invented-key rate is already 0 here, so the prompt fix's measurable effect may be limited to removing a latent failure mode. The post-fix run is still needed to confirm no regression and measure run-to-run noise.

## Files changed

- `src/configs/agent/prompts.yaml` — 2 lines (the example only)
- `src/experiments/agent_eval/prompt_fix_exp_1_overlay.yaml` — new
- `src/experiments/agent_eval/prompt_fix_exp_2_overlay.yaml` — new
- `src/docs/investigations/distill_phase05_1/A_REPORT.md` — this file

## Open items

1. **Valid LLM_API_KEY needed** to run exp_1/exp_2 (~$3.6–5.5 each, cap $12). Command + overlays ready.
2. `prompts.yaml:25` residual misleading guidance about `hate_categories` exclusion (see §2).
3. Consider adding a real `categories_exclude`/`exclude_categories` filter key — `Session.constraints` already carries `exclude_categories` (`session.py:89-95`) with no enforcement path.

---

## Addendum — baseline reruns (post key fix + prompts.yaml:25 fix)

Setup: `CONFIG_OVERLAY_PATH = configs/profiles/multi_domain.overlay.yaml;<prompt_fix overlay>` (profile overlay required by `load_audit_profile.py:30-33`), LLM endpoint api.xah.io `gpt-5.5`, seed 42, same 152 requests. First attempt failed on manifest hash mismatch — root cause: `configs/historical/multi_domain/configs/eval/baselines.yaml` snapshot was CRLF while stage_4 manifest expects the LF hash `a2e926fa` (pre-`eval_user_sample` content from before commit `598b286`). Normalized snapshot to LF; verification now passes.

### Run status
- **exp_1** (first same-config run): crashed pre-agent-loop — `_ArrayMemoryError` in `ItemKNNRecommender.fit` (`baseline_item_knn_recommender.py:26`, 297M-nnz cooccurrence, 1.11 GiB alloc) because BOTH runs built ItemKNN concurrently (~3.2 GB corpus each). $0 LLM spent. Relaunched alone after exp_2 finished.
- **exp_2** (`prompt_fix/exp_2/run_1`): COMPLETED, 152/152 requests, full artifacts (scored.jsonl, metrics.json, report.md).

### exp_2 prompt-fix vs exp_2_baseline (paired request set, n=152)

| metric | baseline exp_2 | prompt_fix exp_2 | note |
|---|---|---|---|
| invented filter keys | 0/92 calls | 0/46 calls | bad example wasn't followed before either |
| FilterTool `filters:{}` (call-level) | 31/92 = 33.7% | 28/46 = 60.9% | fewer calls overall |
| FilterTool `filters:{}` (request-level, all calls empty) | 31/74 = 41.9% | 28/46 = 60.9% | |
| FilterTool tool errors | 6 | 11 | |
| task_success cold_text | 0.650 | 0.650 | identical |
| task_success similar | 0.950 | 0.950 | identical |
| task_success ambiguous | 1.000 | 1.000 | identical |
| task_success exclusion | 0.475 | 0.250 | -22.5pp, n=40 — see noise caveat |
| task_success unanswerable | 0.000 | 0.333 | n=6 |
| target_reachable cold_text | 0.500 | 0.118 | |
| target_reachable personalized | 0.150 | 0.071 | |

Caveats: single run per config so far — exclusion/unanswerable swings are consistent with LLM run-to-run noise (provider has no seed; temp=0). exp_1 rerun will provide the second sample for noise estimation. Do NOT read the exclusion delta as a prompt effect until exp_1 lands.

### exp_1 status: BLOCKED — key died mid-session
Relaunched alone after exp_2 finished; passed manifest verification + corpus/ItemKNN/dense setup, then failed `llm.health_check()` (`run_agent_eval.py:669`) with **HTTP 401**. Direct provider test confirms 401 persists ~15 min later. The same key completed the full exp_2 run minutes earlier → quota exhausted or key revoked/rotated server-side. **Needs a fresh LLM_API_KEY to run the noise-estimation replicate.** Spend so far: 1 run = **$3.19 actual** (440,320 prompt + 33,039 completion tokens, summed `planner_cost_usd` over scored.jsonl). Well under the $12 cap. NOTE: a second same-config run costs ~$3.2 — user's remaining balance (~$2) is insufficient; replicate deferred unless topped up.

### Addendum 2 — exp_1 replicate COMPLETED (new key sk-d666…)
exp_1 (`prompt_fix/exp_1/run_1`) ran to completion 152/152 with the rotated key — this is a same-config replicate of exp_2, giving the first run-to-run noise estimate:

| kind | exp_1 task_success | exp_2 task_success | |Δ| |
|---|---|---|---|---|
| similar | 0.950 | 0.950 | 0.000 |
| cold_text | 0.500 | 0.650 | 0.150 |
| exclusion | 0.150 | 0.250 | 0.100 |
| unanswerable | 0.167 | 0.333 | 0.167 |
| ambiguous | 1.000 | 1.000 | 0.000 |

Noise floor on this provider/config: ~10–15pp on n=20–40 kinds, ~17pp on n=6. Consequences:
- The prompt-fix exclusion delta vs baseline (0.475→0.250) is **inside the noise band** — cannot be attributed to the prompt change.
- cold_text 0.500–0.650 across identical runs → the F3-vs-baseline spec_* comparison (Phase 2) matters more than raw task_success deltas at this n.
- answer_status_ok personalized: 0.55 vs 0.70 — same noise story.
