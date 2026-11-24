# Phase 3 — Extractor benchmark: request text → Spec

**Date:** 2026-11-24 · **Branch:** `distill-phase05-1` · **Model:** gpt-5.5 via api.xah.io, temperature 0
**Question:** can an LLM extractor turn raw request text into a valid `Spec` (kind + category + price/rating + exclusions + seed + language) accurately enough to feed a future DistillTool?

## Method

- **Gold:** `gold_specs.jsonl` — 152 agent_eval requests converted by `spec_from_request` (`build_gold.py`), incl. `gold_coarse`/`gold_ancestor` leaf-up labels.
- **Inputs:** originals + 4 paraphrase variants per request (`paraphrases.jsonl`, 608 rows: `en`, `vi_paraphrase`, `code_mix`, `underspecified`). `underspecified` intentionally strips specifics — it is a stress test, not a faithful variant.
- **Leakcheck:** `leakcheck.jsonl` — LLM judge flags text that names a unique specific product. **199/608 flagged** — see "Leak protocol caveat" below; leaked rows were still extracted and scored as a secondary analysis.
- **Extractor:** `EXTRACT_SYSTEM` prompt in `run_llm.py`, one JSON object per call → `extractor_outputs.jsonl` (760 rows = 152 originals + 608 paraphrases).
- **Scoring:** `score_extraction` (`package/evaluation/spec/_extract_metrics.py`) → `extract_scores.jsonl` + `extract_summary.json`. Category credit is level-aware via `label_ancestors.json` (label → ancestor set rebuilt from item rowid sequences): exact=1.0, ancestor/descendant/sibling=0.5, unrelated=0. `struct_strict` = payload validates against the `Spec` pydantic model.

## Headline results (all 152 requests per variant)

| variant | struct_ok | struct_strict | kind_acc | cat_f1 | cat_exact | excl_f1 | seed_f1 | lang_acc |
|---|---|---|---|---|---|---|---|---|
| original | 1.000 | 1.000 | 0.954 | 0.303 | 0.145 | 1.000 | 0.263 | 1.000 |
| en | 1.000 | 1.000 | 0.947 | 0.316 | 0.138 | 1.000 | 0.263 | 1.000 |
| vi_paraphrase | 1.000 | 1.000 | 0.908 | 0.290 | 0.138 | 0.997 | 0.263 | 1.000 |
| code_mix | 1.000 | 1.000 | 0.954 | 0.322 | 0.138 | 1.000 | 0.263 | **0.066** |
| underspecified | 1.000 | **0.796** | 0.507 | 0.000 | 0.000 | 0.737 | 0.000 | 1.000 |

(`seed_f1`/`cat_f1` denominators include all 152 rows; kinds without that slot score 0 by convention. `price_max_f1`/`min_rating_f1` = 0 everywhere — dead slots in v1, both sides always null → treated as N/A, not a failure.)

## Findings

1. **Structuring is solved.** 100% of 760 calls returned parseable JSON; 100% validate as `Spec` on all faithful variants. The extractor never invents keys or breaks schema. Only `underspecified|similar` drops strict validity (22.5%) — model says `kind=similar` but cannot fill `seed_item_id` (validator requires it). That is honest behavior, correctly surfaced.

2. **kind accuracy is high where information exists.** Faithful variants: 90.8–95.4%. All residual errors are the same two patterns:
   - `unanswerable` → predicted `constrained` (6/6, every variant). Gold "unanswerable" is oracle knowledge — the request asks for category `NonExistentCategory999` + price < $1, which *looks* like a constrained request. **Extractor cannot detect this without catalog access; kind_acc ceiling on this kind is 0 by design.**
   - `exclusion` → occasionally `personalized` (1–3 per variant), but the exclusions slot itself is still extracted perfectly (see 4).

3. **cold_text category extraction is perfect on every faithful variant** — cat_f1 = 1.000, cat_exact = 1.000, n=20 per variant. Category names survive translation/paraphrase/code-mix verbatim enough for exact label match.

4. **exclusions extraction is perfect** — excl_f1 ≈ 1.000 on all faithful variants (item_ids AND category_labels). Even the row misclassified as `personalized` got both exclusion fields exactly right.

5. **similar is the weak slot — granularity, not presence.** Originals: cat_f1 0.65 but cat_exact only 0.05 — the extractor answers at department level (`"Electronics"`, `"Toys & Games"`) while gold leaf is the seed's deepest label (`"DSLR Cameras"`). Related-credit carries the F1. On leaked faithful paraphrases (which retain the ASIN), seed_item_id_f1 = 0.58–0.66 pooled; per-similar-row it is ~1.0 — ASIN extraction is reliable when present.

6. **code_mix language detection fails.** lang_acc = 0.066 — extractor labels code-mixed VI/EN text as `vi` (occasionally `en`). Every other variant is at 1.000. If `language` matters downstream, the prompt needs a code-mix hint or the slot should be dropped.

7. **underspecified behaves exactly as designed.** kind_acc 0.507 — cold_text/exclusion collapse to generic kinds (info genuinely gone), personalized/ambiguous stay correct, similar keeps `kind=similar` but can't fill seed (strict-invalid). cat_f1 = 0 correctly. This validates that the extractor does not hallucinate specs from nothing.

## Leak protocol caveat (important for Phase 4)

Leakcheck flagged **199/608** paraphrases — but the flags are dominated by *input* item identifiers, not answer leakage:

- `similar`: **40/40 leaked in every faithful variant** — the seed ASIN `Domain::ASIN` is part of the request spec (like gold's `seed_item_id`), not the held-out target. Excluding them removes ALL faithful similar paraphrase coverage.
- `exclusion`: 21–29/40 leaked — texts contain the *excluded* item ID, again an input constraint.
- `underspecified`: 0 leaks everywhere (by construction).

The LLM judge applied "names a unique product" literally. For Phase 4 the criterion should be refined to **held-out-target leakage** (paraphrase revealing which item was purchased next), not any item mention. We mitigated by extracting leaked rows anyway (`--include-leaked`); pooled metrics above include them. Clean-only subsets are in `extract_summary.json` (`<variant>|clean|ALL` vs `<variant>|leaked|ALL`) — leaked groups score *higher* on cat_f1/seed_f1 only because they concentrate the similar+exclusion kinds.

## Files

- New: `investigations/spec_benchmark/{build_gold.py, run_llm.py, score.py, gold_specs.jsonl, paraphrases.jsonl, leakcheck.jsonl, extractor_outputs.jsonl, extract_scores.jsonl, extract_summary.json, label_ancestors.json}`
- New: `package/evaluation/spec/_extract_metrics.py` + `tests/evaluation/spec/test_extract_metrics.py` (7 tests; 43 spec tests total pass)
- Edited: `package/evaluation/spec/__init__.py` (exports)

## Cost

~2,100 LLM calls total this phase (608 paraphrase + 608 leakcheck + 760 extract + 152 originals overlap + exp_1 eval 152 planner calls). All extraction/leakcheck prompts are tiny; est. well under $1 on top of eval spend.

## Verdict for Phase 4

Extractor is **good enough to proceed**: schema-perfect, kind/category/exclusion slots reliable on faithful text, honest degradation on underspecified input. Known weaknesses to carry forward: (a) `similar` category granularity — consider mapping predicted labels through `label_ancestors` to nearest catalog label before use; (b) code_mix `language` slot unreliable; (c) `unanswerable` needs catalog-aware detection or stays oracle-bound; (d) leak criterion needs the target-vs-input refinement above.
