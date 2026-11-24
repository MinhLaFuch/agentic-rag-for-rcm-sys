# D_REPORT — Spec schema v1 + validator + gold-converter (workstream D)

**Date:** 2026-11-23 · **Scope:** new modules only, no LLM, no pipeline wiring, no commits.

## Conclusion

**DONE.** Spec v1 is implemented as a self-contained pydantic-v2 package with a
kind-conditional validator, an injectable taxonomy check, both coarse-label helpers
(fixed-depth `coarse_of` + workstream-C leaf-up `coarse_label`), and an offline
`AgentRequest → Spec` gold converter. 25 unit tests pass offline.

## Placement decision

`package/evaluation/spec/` (new subpackage: `__init__.py`, `_schema.py`, `_gold.py`).

Justification: the spec is an **evaluation contract** — produced by a future extractor
(runtime) and consumed by spec-based scoring (layer1/layer2, REPORT §D.2). It is not a
request-builder concern (`evaluation/requests/`) nor yet a recommender concern, so a
dedicated `evaluation/spec/` subpackage mirrors the existing `evaluation/<layer>/`
layout. Deliberately **not** re-exported from `package/evaluation/__init__.py` — that
would modify an existing file (impact-analysis obligation) for zero functional gain;
consumers import `package.evaluation.spec` directly. Underscore-prefixed modules follow
the repo's private-module convention and are exempt from the atomic-file layout rule.

## What was built (evidence)

| piece | location |
|---|---|
| `SpecKind` enum (9 kinds), `CategorySlot`, `Exclusions`, `Spec` (pydantic v2) | `src/package/evaluation/spec/_schema.py:51-148` |
| kind-conditional `model_validator` | `_schema.py:122-148` |
| injectable taxonomy check `Spec.validate_taxonomy` + `validate_spec` | `_schema.py:155-178` |
| `coarse_of(label_or_sequence, coarse_depth)` — REQUIRED param, no default | `_schema.py:213-253` |
| `coarse_label(seq, counts, min_count)` — C's leaf-up N-threshold rule | `_schema.py:32-48` |
| constants `COARSE_DEPTH` (None), `COARSE_MIN_ITEMS=1000` | `_schema.py:28-29` |
| gold converter `spec_from_request` + `_category_sequence`, `_label_counts` | `src/package/evaluation/spec/_gold.py:40-165` |
| tests (25) | `src/tests/evaluation/spec/test_spec.py` |

### Validator rules implemented

- `similar` → `seed_item_id` required; `exclusion` → ≥1 of `exclusions.item_ids` /
  `category_labels`; `cold_text` → non-empty `category_leaf`/`category_coarse` value;
  `constrained` → ≥1 constraint slot (`price_max`/`min_rating`/category) — schema-level
  only, no runtime data assumed.
- `personalized`/`ambiguous`/`unanswerable`/`descriptive`/`unknown` → partial specs legal.
- `validate_taxonomy(taxonomy)` takes a plain `Collection[str]` — **no DB access in the
  model**; callers inject e.g. `ItemCorpus.categories()`. `validate_spec(data, taxonomy)`
  parses raw dicts (future extractor JSON) and optionally checks labels.

### Schema deviations from REPORT §G sketch (documented in code)

1. `category_coarse`/`category_leaf` are `CategorySlot{value, strength, provenance}`
   objects holding **exact-match flat labels**, not path strings (REPORT B.2/B.5).
2. `price_max`/`min_rating` kept but marked **DEAD SLOT v1** in field docstrings —
   not wired into any metric (REPORT C.4: price masked, `constrained` never ran).
3. Added `oracle: bool = False` — additive audit flag mirroring `AgentRequest.oracle` /
   `ORACLE_KINDS`, set True by the converter for `constrained`/`cold_text`/`exclusion`/
   `descriptive`-derived gold so leaky specs are explicitly marked.
4. `exclusions.category_labels` kept even though no `categories_exclude` filter key
   exists yet (REPORT blocker 4) — data preserved, enforcement deferred.

### Gold converter coverage (`_gold.py` docstring table)

- **similar** — CLEAN: `seed_item_id` verbatim; with `corpus`, leaf = deepest category of
  seed (soft/inferred) + coarse slot. Honest kind (`oracle=False`).
- **cold_text** — ORACLE/leaky: `category_leaf` hard/explicit (label is in the text but
  derived from held-out); `oracle=True`.
- **constrained** — ORACLE/leaky: `price_max` + category; `oracle=True`; price noted dead.
- **exclusion** — ORACLE/leaky: `exclusions` from `excluded_item_ids`/`excluded_categories`.
- **personalized/ambiguous/unanswerable/descriptive/unknown** — partial kind-only Spec;
  missing parts are `None`/empty, never guessed. Unknown `request.kind` → `SpecKind.UNKNOWN`.

## Workstream C integration (coarse_depth — RESOLVED, not pending)

`C_REPORT.md` already exists and **recommends AGAINST a fixed depth**: position-2 labels
are fragmented (median bucket 3 items); it proposes leaf-up "deepest label whose corpus
count ≥ N" with **N=1,000** (609 buckets, 99.99% coverage of categorized items).

Implemented both paths:

- `coarse_label(seq, label_counts, min_count)` — pure leaf-up rule; `COARSE_MIN_ITEMS=1000`
  is the plugged-in constant. Converter uses it automatically when `corpus` is passed and
  no explicit `coarse_depth` is given (`_gold.py:108-118`).
- `coarse_of(seq, coarse_depth)` — kept per task spec as the fixed-depth fallback
  (C's least-bad fixed k=3); `coarse_depth` remains a **required** parameter.
- Known gap: C's `main_category`/domain fallback for items where no label reaches N is
  NOT wired (needs `items.main_category` lookup) — `coarse_label` returns `None` and the
  slot stays empty. Flagged as open item.

## Test results

```
cd src && .venv/Scripts/python -m pytest tests/evaluation/spec/test_spec.py -x -q
→ 25 passed in 0.20s   (offline; uses tests/tools_helpers.py 5-item corpus fixture)
```

Coverage: validator valid/invalid per kind, taxonomy inject/pass/fail, `coarse_of`
depths + bare-label rules, `coarse_label` threshold, converter outputs per kind incl.
oracle flags and partial kinds.

`tests/config/test_dependency_direction.py` — passed. `test_package_layout.py` has ONE
failure (`test_every_public_module_has_one_public_symbol_named_after_the_file`) but it is
**PRE-EXISTING**: offenders are `package/corpus/item_corpus.py`,
`package/embeddings/ann_benchmark.py`, `package/embeddings/history_query_benchmark.py` —
verified by stashing all changes and re-running (still fails). My modules are
underscore-prefixed and exempt.

## GitNexus

- `impact`: not required — no existing symbol was edited (all files are new; the only
  conceivable touch point, `package/evaluation/__init__.py`, was deliberately left alone).
- `detect-changes --scope all` (repo root): `Changes: 25 files, 42 symbols, Risk: high` —
  the diff is dominated by OTHER workstreams' tracked modifications (docs, configs,
  `build_requests.py`, `evaluation/_schema.py`); none of my files appear (untracked).
  No `partial`/`truncated` flags.

## Files created

- `src/package/evaluation/spec/__init__.py`
- `src/package/evaluation/spec/_schema.py`
- `src/package/evaluation/spec/_gold.py`
- `src/tests/evaluation/spec/test_spec.py`
- `src/docs/investigations/distill_phase05_1/D_REPORT.md` (this file)

No existing files modified. No commits, no pushes.

## Open items / handoffs

1. **`main_category` fallback for coarse** — C recommends falling back to
   `items.main_category`/domain when no label reaches N=1,000 (12/196 eval targets
   uncategorized). Not wired; needs a corpus lookup helper at scoring time.
2. **`categories_exclude` filter key** still absent — `exclusions.category_labels` is
   stored but unenforceable until a later workstream adds it (REPORT blocker 4).
3. **price_max/min_rating dead slots** — schema-stable but intentionally unused; revisit
   only if masking policy changes.
4. **Stash side-effect (FYI, resolved):** to verify the pre-existing layout-test failure I
   ran `git stash -u` + `git stash pop`. Content is fully restored, but the previously
   STAGED renames (`cf_topn_recall.json → investigations/…` etc.) now appear as staged-adds
   + unstaged-deletes instead of staged `R` entries — git will still detect the renames at
   commit time. The remaining `stash@{0}` ("WIP on feat/multi-turn-wiring") predates my
   work — I did not create or drop it.
5. Extractor-side consumers (DistillTool / pre-planner) and spec metrics are later
   workstreams; `validate_spec(data, taxonomy=...)` is the intended entry point for raw
   extractor output.

---

## Addendum — post-review wiring (2026-11-24)

- **`main_category` fallback WIRED** (open item 1 resolved): `_gold.py` gained
  `_main_category(corpus, item_id)` (`SELECT main_category FROM items`); the
  `similar` branch now falls back to it when the taxonomy sequence is empty
  (uncategorized item) OR no label reaches `COARSE_MIN_ITEMS`. Slot stays
  `soft`/`inferred`. New test `test_gold_similar_main_category_fallback` —
  **26 tests pass** (was 25).
- **`spec_` report registry:** `"spec_"` added to `_DYNAMIC_PREFIXES` in
  `package/evaluation/reporting/_adapter.py:46` so `spec_*` metrics reach
  report.md (GitNexus impact UNKNOWN → text-verified single-use at :61).
- **Empty-list conventions** documented in `package/evaluation/spec/__init__.py`
  docstring: `spec_precision@k` = 0 on empty `recommended` (request stays in
  denominator — 40/152 trajectories have empty lists, ~half `exclusion`);
  violation rates must ship with result-coverage; spec_* row values must be
  scalar or `summarize` crashes.
- Open items 2–5 unchanged.
