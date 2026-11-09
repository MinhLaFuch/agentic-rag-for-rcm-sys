# Phase 3 Report — Repository Hygiene

Date: 2026-11-09 · Branch: `tools-building` · Base: `0ce2ea8`

## 3.1 Documentation consolidation (D2)

- Renamed `Project repository reading 29.10.md` → **`repo reading.md`** (`git mv`).
- Updated for reality: branch `tools-building`, HEAD `0ce2ea8`, test baseline
  1359 passed / 0 skipped / 2 xfailed; added "Week 46 Audit Remediation Status"
  table; corrected component-benchmark table (memory=real oracle, planner=real
  LLM, executor=`not_implemented`, grounding=real Jev + synthetic answers,
  integration=dict-contract only); multi-turn marked **not implemented** (D3);
  `statistical_settings` marked dead config.
- Merged still-valid content of 12 deleted docs into new **§18 Evaluation
  Framework Reference** (package layout, request kinds, L1–L5 metrics, component
  framework, campaign framework, execution/export, scripts/tests layout,
  carried-forward limitations). Corrections applied: `run_all.py`→`_run_all.py`,
  multi-turn not-implemented, executor status.

### Deleted files — 14 total (corrected count; `git show --name-status` verified)

Reference check: grep across `*.py`, `*.yaml`, `*.sh` found zero code references;
only `docs/audit_week46_report.md` (historical record, intentionally unchanged)
and intra-doc cross-links among the deleted set.

| Deleted file | Content merged into `repo reading.md` |
|---|---|
| `package/evaluation/ARCHITECTURE.md` | §18.1 package layout, §18.4 key classes, §18.6 provenance |
| `package/evaluation/CAMPAIGN.md` | §18.5 campaign framework |
| `package/evaluation/EXECUTION.md` | §18.6 execution/resume/compare/export |
| `package/evaluation/FINAL_SUMMARY.md` | Condensed: phase narrative → §1 remediation status + §18.8 limitations (per-phase "what was done" detail intentionally dropped as historical build log) |
| `package/evaluation/METRICS.md` | §18.3 metrics + formulas (restored in full after review) |
| `package/evaluation/MULTI_TURN.md` | §6.6 status + §18.3 multi-turn metrics (schema field details condensed) |
| `package/evaluation/REQUEST_KINDS.md` | §18.2 request kinds |
| `package/evaluation/campaign/README.md` | §18.5 (parameter grid, overlay, result format) |
| `package/evaluation/component/README.md` | §18.4 (dataset format, CLI, regression) |
| `package/evaluation/component/benchmarks/planner_README.md` | §18.4 planner notes (metrics, limitations) |
| `benchmarks/README.md` | §18.7 scripts layout |
| `scripts/README.md` | §18.7 scripts layout |
| `tests/README.md` | §18.7 tests layout |
| `tests/tools/README.md` | §18.7 tests layout (tiny-world fixture note) |

`AGENTS.md` kept.

## 3.2 Stale docstrings

- `scripts/evaluation/run_campaign.py:10` — was "hardcoded to
  package/evaluation/campaign/example_campaign.yaml"; actual default is
  `configs/evaluation/campaign.yaml`. Fixed.
- `package/api/openai_compatible_provider.py:9-15` — removed stale "BLOCKED"
  block; now states implementation is complete and missing credentials are an
  environment state, not a code defect.

## 3.3 Broken import fixed

- `scripts/evaluation/evaluate_product_reply.py:18` —
  `package.evaluation.evaluate_product_reply` →
  `package.evaluation.product_reply` (per `product_reply/__init__.py`).
- `PYTHONPATH=. python scripts/evaluation/evaluate_product_reply.py --help`
  now prints usage correctly (verified). Script retained — it is a working CLI
  for the non-Jev product-reply evaluator.

## 3.4 Hygiene

- Deleted orphan `__pycache__` entries `mock_backend.cpython-312.pyc` and
  `offline_backend.cpython-312.pyc` — sources no longer exist (only
  `__init__.py` + `live_backend.py` remain).
- `.gitignore` (repo root) already covers `__pycache__/` and `*.pyc`;
  `git ls-files "*.pyc"` = 0 — nothing tracked.
- No `nul` artifact found (`find` clean).

## 3.5 Placeholder labeling (no logic changes)

- `reporting/_visualizations.py` — module docstring now states all 5 chart
  functions are PLACEHOLDER markdown stubs; output headers changed to
  "(PLACEHOLDER — chart not implemented)".
- `component/create_traceback_tool.py` — docstring + output JSON now carry
  `method: keyword_heuristic_placeholder`, `status: placeholder_not_real_attribution`.
- `component/link_component_to_e2e.py` — docstring + output JSON carry
  `status: placeholder_not_computed` for correlation.
- `scripts/evaluation/generate_example_report.py` — docstring: SYNTHETIC DEMO
  ONLY, hardcoded numbers, not wired into any pipeline.
- `scripts/evaluation/opik_poc.py` — docstring: DRY-RUN ONLY; `RCMMetricWrapper`
  0.95 stub explicitly labeled `PLACEHOLDER — not computed`.

## 3.6 dummy dataset + dummy symbols

- `benchmarks/dummy_memory_dataset.jsonl` (3 lines): **deleted** — user
  approved; no code loaded it (only the deleted component/README + audit
  referenced it). Post-delete check: `pytest tests/evaluation/component
  tests/config/test_package_layout.py` → 67 passed.
- 3 "Dummy public symbol" files (`memory_oracle.py`,
  `build_memory_correctness_dataset.py`, `memory_correctness_setup.py`): they
  are compatibility re-export modules; the dummy function exists only to
  satisfy `tests/config/test_package_layout.py` (file-name = public-symbol
  convention). **Keep** — layout test requires them.

## 3.7 Config-key audit (report only)

Full table: `docs/phase3_config_audit.md` (221 leaf keys traced).
Headline verified findings:

- **Dead keys**: `domains[].role`; `judge.yaml evaluation.faithfulness.claim_extraction`;
  `campaign.yaml statistical_settings.*` + `metadata.*`; `component_benchmarks.yaml configs.executor.*`;
  `agent/memory.yaml memory.session.*` (schema-validated but `Session()` always uses built-in defaults).
- **Used (suspicions cleared)**: `eval/tuning.yaml tuning.*` (read by
  `benchmarks/tune_baselines.py:36`); `ablation.groups.*` (dict keys consumed
  by ablation `_limits.py`).
- **Dormant/demo-only**: `outputs.multi_turn` (multi_turn not implemented),
  `outputs.example_report` (demo script only).
- **campaign.yaml bypasses `load_config`**: no `extra="forbid"`, no env
  expansion, no overlay support — recommendation documented in audit file.

## Test results

`PYTHONPATH=. python -m pytest tests/ -q` → **1359 passed, 2 xfailed, 13 warnings in 50.44s**
(identical to Phase 2.1 baseline; log: `experiments/test_logs/test_results_20261109_012338.md`)

## Files changed

- Renamed + rewritten: `repo reading.md` (was `Project repository reading 29.10.md`)
- Deleted: 14 `.md` files listed in §3.1 + `dummy_memory_dataset.jsonl` (approved post-review)
- Modified: `run_campaign.py`, `openai_compatible_provider.py`,
  `evaluate_product_reply.py`, `_visualizations.py`, `create_traceback_tool.py`,
  `link_component_to_e2e.py`, `generate_example_report.py`, `opik_poc.py`
- New: `docs/phase3_config_audit.md`, `docs/phase3_report.md`
- Deleted artifacts: 2 orphan `.pyc`

## Verification addendum (post-review, 2026-11-09)

### A. FAIL-on-old-code evidence (3 Phase-1 regression tests)

Method: `git checkout 7d50750~1 -- <3 fixed source files>` (pre-Phase-1 code),
ran tests, restored with `git checkout HEAD --`. Output:

```
FAILED tests/evaluation/campaign/test_campaign.py::test_auto_comparison_pairs_are_actually_used
FAILED tests/evaluation/test_judge_error_handling.py::test_judge_batch_error_marks_judge_error_not_unsupported
FAILED tests/evaluation/component/benchmarks/test_grounding_phase1.py::test_provider_error_fails_case_not_fake_score
3 failed in 0.45s
```

After restore: `3 passed in 0.18s`. Log:
`experiments/test_logs/test_results_20261109_013016.md` (fail) /
`test_results_20261109_013023.md` (pass).

### B. Manual independent check of memory dataset correctness_024/025

Computed by hand from `fixtures/create_test_interactions.py` +
`create_test_mappings.py` + `create_test_meta.py` — NOT via oracle/render:

- `item2id` is built from `interactions["item_id"].unique()` order, so
  `item_idx` is a positional index. Unique-string order resolves:
  idx 0–9 → vg_a..vg_j; 10 → vg_null_a; 11 → vg_null_b; 12 → vg_outlier;
  13 → vg_k; 14 → vg_l. (The `item_id` strings written in
  u_large_recent/u_many_categories rows for i≥10 — e.g. "vg_m" — are cosmetic
  and do NOT match the resolved id; both MemoryTool and oracle use `item_idx`,
  so they agree. Fixture cosmetic inconsistency noted, not a correctness bug.)
- **024 u_large_recent**: 15 rows, all rating=5 → loved = all 15 distinct
  item_idx; top-10 by (−rating, item_id) with rating tie → vg_a..vg_j.
  Expected `loved_items` = vg_a..vg_j ✓. `hated_items` = [] ✓.
  `recent_items` = item_idx 14..5 → vg_l, vg_k, vg_outlier, vg_null_b,
  vg_null_a, vg_j, vg_i, vg_h, vg_g, vg_f — matches expected exactly ✓.
- **025 u_many_categories**: identical interaction pattern → identical
  loved/hated/recent ✓ (top_n_categories=10 but only 5 categories exist in meta).

**Verdict: expected values in the regenerated dataset are CORRECT** — the
oracle/regeneration did not bake in a wrong answer.

### C. Is loved_items/hated_items order a contract?

Yes — "highest/lowest-rated items" implies ranking order, and the tool now
sorts deterministically (rating, then item_id tie-break). The sync test
`test_committed_dataset_matches_oracle` uses strict string equality
(`committed == builder.render()`) and does **not** sort before comparing —
order violations would be caught. ✓

## Not done / awaiting decision

- ~~`dummy_memory_dataset.jsonl` deletion~~ — done (user approved).
- Dead config keys — report only per instructions; removal is a Phase 4
  (config) or Phase 5 (`role`) decision per user.
- `campaign.yaml` via `load_config` — deferred to Phase 4 per user.
- Executor benchmark — D1 decided: **option 1** (real benchmark for
  reproducible cases + fault-injection cases → unit tests). Awaiting Phase 4
  scheduling approval.
