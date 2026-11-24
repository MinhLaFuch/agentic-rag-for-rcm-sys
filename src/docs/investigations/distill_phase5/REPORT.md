# Phase 5 — Distill spec injection: live A/B vs prompt_fix baseline

**Date:** 2026-11-24 · **Branch:** `distill-phase05-1`
**Arm:** `experiments/agent_eval/distill_spec/exp_1/run_1` (152 requests, seed 42, planner only, template answers, reflect_rounds=0)
**Baseline:** `experiments/agent_eval/prompt_fix/exp_2/run_1` — identical config minus `distill_spec` (also the exp_1 replicate's config; noise floor ~10–15pp on n=20–40 kinds, ~17pp on n=6)

## What was built (flag-off by default)

Pre-planner injection — **not** DistillTool. Rationale: identical scientific
question (does spec guidance help?), far smaller blast radius: no new tool, no
plan-format change, no extra plan step, spec visible in `traj["distilled_spec"]`.

- `package/agents/distill.py` — `extract_spec()`: one LLM call, strict JSON →
  `Spec` validation → flatten slots → corpus label normalization
  (`normalize_category_case` only; fuzzy left to FilterTool's own errors).
- `PlanExecutor(spec_extractor=...)` — optional callable; `plan()` runs it once,
  appends `distilled_spec_block` (prompts.yaml) to the system prompt, keeps
  `last_distill` (spec + usage, tokens NOT folded into planner `usage`).
  Extractor failure is contained — planning proceeds without spec.
- `agent_eval.distill_spec` config flag (schema + yaml, default false);
  `protocol_manifest["distill_spec"]` recorded; flag is inside
  `_resume_agent_config` hash → resume-safe.
- Overlay: `experiments/agent_eval/distill_spec_overlay.yaml`.
- Tests: `tests/agents/test_distill.py` — 8 pass.

## Headline results (task_success)

| kind | n | baseline exp_2 | exp_1 replicate | **distill** | Δ vs baseline |
|---|---|---|---|---|---|
| cold_text | 20 | 0.650 | 0.500 | **1.000** | **+0.350** |
| exclusion | 40 | 0.250 | 0.150 | **0.450** | +0.200 |
| similar | 40 | 0.950 | 0.950 | 0.950 | 0.000 |
| personalized* | 40 | — | — | answer_ok 0.975 | +0.275 vs 0.70 |
| ambiguous | 6 | 1.000 | 1.000 | 1.000 | 0 |
| unanswerable | 6 | 0.333 | 0.167 | **0.000** | −0.333 ⚠ |

*personalized has no task_success; `answer_status_ok` 0.70→0.975, asked_clarification 0.10→0.00, n_steps 2.85→3.43 (fuller plans).

## spec_* backfill (`investigations/distill_phase5/spec_backfill_*.jsonl`)

| kind | metric | promptfix | distill | paired bootstrap |
|---|---|---|---|---|
| cold_text | spec_precision@10 | 0.735 | **0.935** | **+0.200, CI [0.06, 0.37] excl. 0** |
| cold_text | spec_result_coverage | 0.85 | 1.00 | |
| exclusion | spec_violation_rate | 0.075 | 0.025 | −0.05, CI [−0.15, 0.05] ns |
| exclusion | spec_result_coverage | 0.35 | 0.475 | |
| similar | spec_precision@10 | 0.075 | 0.075 | 0.000 |

**distill cold_text spec_precision@10 = 0.935 — identical to F3's always-category-filter score**, achieved *without* F3's similar-kind collapse (F3 similar task_success was 0.525). The spec injection gets the category precision where it belongs and leaves other kinds alone.

## Reading the deltas against the noise floor

- **cold_text +35pp task_success / +20pp spec_precision (CI excludes 0): real effect.** n=20 is small but the paired CI on spec_precision excludes zero, and the mechanism is visible (planner now emits `categories_any` filters it previously skipped — `filters:{}` should drop; verify in trajectories).
- **exclusion +20pp task_success:** direction consistent with spec help (violation rate down, coverage up, clarifications down 0.525→0.175) but inside the ~10–15pp noise band — treat as suggestive, not proven.
- **personalized answer_ok +27.5pp:** large, but personalized has no task_success and n=40; worth a replicate before claiming.
- **unanswerable −33pp (0.333→0.000, n=6): likely real regression.** asked_clarification 0.167→0.000 — the spec tells the planner "constrained" (extractor can't detect NonExistentCategory999), so it stops asking and attempts retrieval that fails. n=6 → wide CI, but mechanism is coherent. **This is the cost of oracle-blind extraction.**

## Cost

+152 extractor calls (~0.5k tokens each ≈ +75k prompt tokens total, <$0.5) on top of the normal planner spend. Extractor usage is in `traj["distilled_spec"].usage`, separate from planner `usage`.

## Verdict

Spec injection is a **clear win on cold_text (the original bottleneck kind), neutral-to-positive elsewhere, with one identified regression on unanswerable** (clarification-seeking suppressed by over-confident spec). Recommendation: keep flag-off default; before enabling anywhere, either (a) add a clarify-path hint for low-confidence specs, or (b) accept the n=6 regression consciously. A replicate run would firm up exclusion/personalized/unanswerable — ~$3.

## Files changed

- New: `package/agents/distill.py`, `tests/agents/test_distill.py`,
  `experiments/agent_eval/distill_spec_overlay.yaml`,
  `investigations/distill_phase5/{spec_backfill_rows.jsonl,spec_backfill_summary.json,item_spec_view.parquet}`
- Edited: `package/agents/planner/plan_executor.py` (spec_extractor param,
  injection, last_distill), `package/config/_schemas.py` (distill_spec +
  distilled_spec_block fields), `configs/agent/agent_eval.yaml`,
  `configs/agent/prompts.yaml` (distilled_spec_block),
  `scripts/evaluation/run_agent_eval.py` (wiring + traj field + manifest)

---

## Addendum 2026-11-24 — exp_2 replicate + clarify-hint + MemoryTool prompt fix

**exp_2** (`experiments/agent_eval/distill_spec/exp_2/run_1`, clarify-hint
prompt, same 152 requests): cold_text 0.90, exclusion 0.50, similar 0.95,
unanswerable **0.333 (recovered to baseline)** — the clarify-hint fixed the
exp_1 unanswerable regression. personalized answer_ok crashed to 0.125.

**Root cause (not spec, not hint):** planner `system_prompt` statically
instructs MemoryTool + shows 3 MemoryTool few-shot examples, but the
`planner` agent toolkit excludes MemoryTool → 35/40 personalized plans
emitted "unknown tool" → cascade failure. promptfix baseline had the same
latent bug at 7/40. Fix: MemoryTool guidance moved to `memory_guidance`
injected only when the toolkit has MemoryTool (`plan_executor.py`,
`build_run_provenance.py`, `_schemas.py`, `prompts.yaml`; 338 tests pass).
**exp_3** (`distill_spec/exp_3/run_1`) validates the combined prompt.
