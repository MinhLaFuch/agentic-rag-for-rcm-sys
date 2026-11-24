# bad_reference / tool_error cascade analysis

Date: 2026-11-24 · Arm analyzed: `prompt_fix/exp_2` (152 trajectories, pre-fix prompts)
Script: inline analysis (see commands in git history); data: trajectories.jsonl

## Finding: cascades, not bad refs

`bad_reference` errors are almost never the planner's fault — they are
downstream of an earlier step failing. When step N fails, every step
referencing `$N.*` resolves to nothing → `bad_reference` → `rec=0` →
`answer_status=tool_error`. The planner is single-shot (reflect_rounds=0),
so there is no recovery.

## First-failure root causes (prompt_fix exp_2, n=152)

| first failing step | count | cause | status |
|---|---|---|---|
| MemoryTool `unknown_tool` | 8 | planner calls MemoryTool but `planner` agent toolset lacks it — old unconditional `memory_guidance` prompt | **FIXED** — `plan_executor.py:130` now injects guidance only when `"MemoryTool" in self.tools` (shipped before exp_3/availability runs) |
| SearchTool `tool_error` | 7 | `query exceeded the time budget` — broad FTS queries on 2.6M items | OPEN — small count; options: narrower-query prompt nudge or budget bump |
| FilterTool `tool_error` | 5 | same time-budget class (incl. cascades counted once) | OPEN — same |
| RankTool `candidates is empty` | ~4 | upstream candidate pool empty (over-constrained filters) | OPEN — ties to exclusion coverage problem (BOTTLENECK tier-3) |
| LookupTool `tool_error` | 1 | — | — |

## Residual work (not blocking)

1. SearchTool/FilterTool timeouts: consider a prompt line telling the
   planner to keep `limit` small and prefer `categories_any` over bare
   keyword queries; or raise `sql_time_budget` for eval only. Expected
   gain small (≈12 first-failures/152 ≈ up to ~8pp if all rescued, likely
   less since some requests fail anyway).
2. Empty-candidate cascades: planner has no "relax constraints" fallback.
   Cheapest fix is a prompt example showing FilterTool → if empty, retry
   without the strictest filter. Deferred until spec_* A/Bs land —
   distill_spec may already reduce over-constraining.

## Verification path

exp_3 (distill_spec, post-memory_guidance-fix) + availability exp_2
trajectories will show whether `unknown_tool` MemoryTool errors drop to
~0. Compare per-kind tool_error rates vs prompt_fix exp_2:

- baseline: personalized 7/40, exclusion 5/40, unanswerable 4/6 tool_error
- availability exp_1 (fix active, contaminated by SQL timeouts):
  personalized 23/40, exclusion 33/40 — do NOT use as evidence; the
  timeouts were the availability JOIN bug, now fixed in exp_2.
