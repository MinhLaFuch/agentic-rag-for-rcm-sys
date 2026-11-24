# Workstream E — Close three "chưa xác minh" items from distill_infra_audit

**Date:** 2026-11-23 · **Branch:** distill-phase05-1 · **Scope:** read-only verification; no code edited.

---

## E.1 filter_ab/exp_2_baseline trajectories — VERIFIED, usable for offline spec-metric backfill

**Files present** in `experiments/agent_eval/filter_ab/exp_2_baseline/run_1/`:
`trajectories.jsonl` (152 rows), `requests.jsonl` (152), `scored.jsonl` (152), plus a duplicate
`filter_ab_exp_2_baseline_run1_trajectories.jsonl` (152, same content). The audit's "chưa xác minh" is resolved: **trajectories.jsonl exists.**

**Join + fields (verified by parsing, not dumping):**
- Top-level trajectory keys include `request_id`, `agent`, `text`, `steps`, `recommended`, `usage`,
  `evaluation_protocol_hash`, `answer_status`, `error` (full list inspected).
- `recommended` = **list of item_id strings** (e.g. `"Toys_and_Games::B005XP6II0"`), n=10 typical —
  same shape as other runs; joins to `requests.jsonl` via `request_id` (all 152 ids match exactly).
- `agent` is always `"planner"` (single-agent run; 152 rows = 152 requests).
- `requests.jsonl` rows carry the full AgentRequest field set: `kind, segment, text, user_id,
  user_idx, seed_item_id, targets, price_max, category, excluded_item_ids, excluded_categories,
  oracle`.

**Caveat — 40/152 rows have `recommended == []`:** `similar-sparse-14`, `similar-warm-8`,
`cold_text-cold-3/5/7`, … By kind: exclusion 20, cold_text 6, ambiguous 6, unanswerable 6, similar 2.
All have `error: null`, `answer_status: "tool_error"` — i.e. the plan failed at runtime (tool error),
not a serialization gap. These rows still have `steps[].data` and join fine; spec metrics computed
over `recommended` will simply score them as empty-recommendation (consistent with hit@10=0), which
is the honest behavior. No row lacks the `recommended` key entirely.

**Verdict:** usable for offline spec-metric backfill exactly like the other 7 verified runs —
join on `request_id`, read `recommended` item_ids + request structured fields, resolve categories
via corpus SQL. The exp_2 baseline run is now confirmed at parity with campaign_005/learned_scorer/
hybrid_scorer/filter_ab exp_1,3,4 and union_ab artifacts listed in audit D.3.

---

## E.2 Summarize / reporting registry — precise answer

### (a) Does `summarize` auto-average a new NUMERIC metric key? — **YES**

`package/evaluation/trajectory/summarize.py:86-106`:
- Line 95: iterates `sorted({key for row in group for key in row} - _ID_KEYS)` — **every key present
  in scored rows** is considered; there is no allowlist of metric names.
- Lines 96-97: skips only keys in `_NON_NUMERIC_KEYS` (lines 25-83) and `_ID_KEYS` (line 10).
- Lines 98-100: `float(row[key])` → `np.mean` → stored as `entry[key]`. Bool→0.0/1.0.

So a numeric `spec_recall@10` in scored rows is averaged automatically into the
agent→kind→segment buckets written to `metrics.json` via
`scripts/evaluation/run_agent_eval.py:847` (`summary = summarize(rows)`) and `:934`
(`metrics={"k": k, "summary": summary, ...}` → `save_experiment`).

**Two sharp edges:**
1. If a spec metric ships a **dict/list detail value** under any key, `float(row[key])` at
   `summarize.py:98` raises `TypeError` — the whole summarize crashes (not caught). Detail keys must
   either be flattened to scalar-per-row or added to `_NON_NUMERIC_KEYS` (summarize.py:25-83).
2. `spec_recall@10` is numeric and not in `_NON_NUMERIC_KEYS` → safe; `None` values are filtered at
   line 98 (`row.get(key) is not None`).

### (b) Does it appear in report.md? — **NO, without a registry update**

`package/evaluation/reporting/_adapter.py`:
- `_HEADLINE_METRICS` (lines 28-41): fixed 12-name allowlist (`task_success`,
  `constraint_satisfaction`, `exclusion_compliance`, `tool_selection_ok`, …).
- `_DYNAMIC_PREFIXES` (line 44): `("precision@", "recall@", "hit_rate@", "ndcg@", "mrr@", "map@")`.
- `_headline_keys` (lines 55-61) unions the two: a row key is report-eligible iff it is in
  `_HEADLINE_METRICS` **or startswith one of `_DYNAMIC_PREFIXES`**.

`"spec_recall@10".startswith("recall@")` is **False** (prefix is `spec_`), and it is not in
`_HEADLINE_METRICS` → it will **not** reach `metric_values` (adapter.py:133), the Request Kind
Analysis table (`_generator.py:69-80`), the Confidence Intervals table (`_generator.py:105-117`),
the CSV export (`_generator.py:175-188`), or charts. It **will** still be in metrics.json (see a).

**Registry updates needed for report.md visibility (pick one):**
- Add `"spec_recall@10"` (and siblings) to `_HEADLINE_METRICS` at `_adapter.py:28-41`, or
- Add `"spec_"` to `_DYNAMIC_PREFIXES` at `_adapter.py:44` (catches all `spec_*@k` metrics), or
- Name the metric `recall@10`-style so it matches existing prefixes — but that collides with the
  existing retrieval `recall@{k}` semantics, so not recommended.

Also note `SUMMARY_COLUMNS` (`run_agent_eval.py:97-101`) only affects the **console print**
(lines 848-853), not metrics.json or report.md — updating it is cosmetic only.

---

## E.3 Extractor prompt size estimate

Schema under estimation (`package/evaluation/spec/_schema.py:75-104`): `kind` (9-value enum),
`category_coarse`/`category_leaf` (`CategorySlot{value,strength,provenance}`), `price_max`,
`min_rating`, `exclusions{item_ids,category_labels}`, `seed_item_id`, `attributes` (free dict),
`language` (4-value enum), `uncategorized_ok`, `oracle`; plus kind-conditional rules
(`_schema.py:106-131`) and optional taxonomy validation (`validate_taxonomy`, :142-152).

### Token budget (reasoned, not exact)

| component | est. tokens | basis |
|---|---|---|
| System prompt: schema description + strength/provenance semantics + kind rules + output format | ~150-250 | task's own range; ~600-1000 chars of English rules ≈ 150-250 tok |
| Output-format example (one small JSON Spec) | ~40-80 | a minimal spec JSON is ~150-300 chars |
| Per-request user payload: VI request text | ~30-60 | VI template strings ~100-250 chars; ~1 tok per 3-4 chars VI |
| Catalog category examples / taxonomy candidates | ~20-200 | a handful of labels ~20-60 tok; a `suggest_categories`-style candidate list of ~20-50 labels ~150-400 tok |
| **Total (no taxonomy injection)** | **~250-450** | sum above |
| **Total (with modest category-candidate injection)** | **~450-900** | upper case |

### Comparison with observed planner prompt_tokens

Measured on this very run (`exp_2_baseline/run_1/scored.jsonl`, `prompt_tokens` per row):
n=152, **mean ≈ 4,699**, min 2,543, max 9,367 (matches audit E "~4.5-4.7k"). The planner system
prompt alone (`configs/agent/prompts.yaml:7-43`) is ~1,100 words ≈ **~1,400-1,600 tokens** before
tool schemas + session state + request text are appended — that is why it lands at ~4.7k.

**Estimate:** extractor prompt ≈ **0.3-0.9k tokens** (central ~0.4-0.5k), i.e. **~5-10× smaller**
than the planner call; roughly **10-20% of planner prompt cost**. If the extractor is given a large
flat taxonomy dump (2,260 labels — absolutely should not be; `suggest_categories` difflib top-N or
root labels only), it could balloon to several k — keep candidates ≤ ~50 labels.

Cost implication (audit E): extractor ≈ 1 extra small call per request; on the 152-request set,
~152 × ~0.5k prompt tokens ≈ ~76k prompt tokens total — trivial vs. the ~715k planner prompt tokens
already spent (152 × 4,699). Budget-wise the extractor is noise; the binding constraint is call
count/latency, not tokens.

---

## Summary of evidence

| item | verdict | key evidence |
|---|---|---|
| exp_2_baseline trajectories | **exists, joinable, backfill-ready** | `experiments/agent_eval/filter_ab/exp_2_baseline/run_1/trajectories.jsonl` (152 rows, `recommended` = item_id strings, request_id 1:1 with requests.jsonl); 40 empty-`recommended` rows are tool_error runs, not missing data |
| summarize auto-average | **yes for metrics.json; no for report.md** | `summarize.py:95-100` iterates all row keys minus `_NON_NUMERIC_KEYS`/`_ID_KEYS`; `_adapter.py:28-44,55-61` gates report metrics via `_HEADLINE_METRICS`+`_DYNAMIC_PREFIXES` — `spec_recall@10` fails the `startswith("recall@")` check; registry edit needed at `_adapter.py:28-44` |
| extractor prompt size | **~0.3-0.9k tokens est.** | schema at `spec/_schema.py:75-131`; planner observed mean 4,699 prompt tokens (`scored.jsonl`) driven by ~1.5k-token system prompt `prompts.yaml:7-43` + tool schemas |

---

## Addendum — registry item resolved (2026-11-24)

The `report.md` gap flagged above is fixed: `"spec_"` added to
`_DYNAMIC_PREFIXES` (`package/evaluation/reporting/_adapter.py:46`), so any
`spec_*` numeric column (e.g. `spec_recall@10`, `spec_precision@10`) is picked
up by the dynamic-prefix branch at `_adapter.py:61`. GitNexus impact on the
constant returned UNKNOWN (index 9 commits stale) — confirmed via text search
that `_DYNAMIC_PREFIXES` is referenced only inside `_adapter.py`. The scalar-only
caveat is now documented in `package/evaluation/spec/__init__.py`.
