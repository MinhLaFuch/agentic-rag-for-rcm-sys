# Request-content investigation — why target_reachable is structurally low

Date: 2026-11-23. Question: is the ~90% target loss at `retrieve` stage a
system failure or an eval-design artifact? **Answer: predominantly the latter.**

## How requests are generated (code path)

`package/evaluation/requests/build_requests.py` + templates in
`package/agents/_schema.py`. Requests are **simulated** (docstring: "no real
query log exists offline, so they are simulated") — built from held-out
split data, not from real user queries.

### What each kind's `text` actually contains

| kind | template signal | targets/req | oracle? |
|---|---|---:|---|
| `cold_text` | user_id + k + **category name only** | 1.00 | yes |
| `personalized` | user_id + k only (history implicit) | 1.82 | no |
| `similar` | user_id + k + **raw namespaced ASIN** seed | 1.93 | no |
| `constrained` | user_id + k + category + price_max (price derived from held-out item × slack) | — | yes |
| `exclusion` | user_id + k + excluded category + excluded item ASIN | 0.65 | — |
| `ambiguous`/`unanswerable` | fixed phrases | 0 | — |

**The held-out item's title/description is NEVER included in any template.**
`build_requests` looks up the target only to derive `category`/`price_max`
constraints — the text a real user would write ("I'm looking for a noise-
cancelling headset for commuting under $80") is never generated.

## Measured consequence (campaign_005 exp_6 requests.jsonl)

- `cold_text`: 20 requests, **exactly 1 target each**, categories contain
  **547–18,873 items** (median ~4,700). The task is literally "pick 1 specific
  item out of hundreds-to-thousands given only the category name".
  Random top-10 hit rate ≈ 10/N = 0.05%–1.8%. Observed recall@10 = 10% —
  already ~5–50× above random via popularity/CF bias, but the ceiling is
  structurally low.
- `similar`: seed is an opaque ASIN (`Toys_and_Games::B07C9SS2BR`), not a
  title — resolvable only through SimilarTool/itemcf. task_success 0.95 yet
  target_reachable = 0: the agent gives plausible similar items, just not
  the held-out ones.
- `personalized`: zero item-level signal in text; only user history can
  predict targets (and F10 showed even ideal CF ≈ 0.77% recall@10).

## Cross-check with vi_retrieval Step 3

Faithful EN translation of the 196 target requests lifts target-token
overlap only 11.7%→13.3%; BM25 rank among category peers ~1% r@200; dense
peer rank ~0.5–1%. Under the BEST measured retrieval arm (e5base+translated,
42% r@10 on rich probe descriptions) the real requests still fail — because
the requests don't describe items.

## Verdict

The request generator measures **agent behavior under category-level
requests** (tool use, constraints, clarification) — which is a legitimate
eval — but `target_reachable`/`recall@10` against item-level held-out
targets measures an **information gap the input cannot specify**. This
explains the universal pattern: every retrieval/ranking intervention
(CF, learned scorers, inferred cats, union pools, translations, multilingual
embeddings) fails to move target metrics — they were never the bottleneck.

## Fix options (if item-level retrieval eval is wanted)

1. **Add a descriptive kind**: template that paraphrases the held-out item's
   title into the request (e.g., "Tôi cần tai nghe chống ồn cho đi làm" for a
   noise-cancelling headphone target). Requires LLM paraphrase at build time
   or a curated phrase bank — moderate effort, directly measures retrieval.
2. **Score at category level for cold_text**: accept that "products in
   category X" can only be judged on category-hit + diversity/quality, not
   exact-item recall (Q9/F9 already documented category-hit as secondary).
3. **Keep as-is + reweight**: treat target_reachable as a lower-bound sanity
   metric, optimize task_success as primary.

Option 1 is the only one that produces a meaningful retrieval metric.
Estimated work: new template + paraphrase generation for 152 requests
(~1-2h LLM calls) + rerun eval (~35min).
