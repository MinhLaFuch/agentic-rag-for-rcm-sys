# Direct Retrieval Benchmark — descriptive vs campaign requests

**Date:** 2026-11-23 · **Targets:** the 196 held-out targets of campaign_005/exp_5 (same users/targets as the agent eval) · **Question:** given a *human-like* descriptive query, can retrieval find the target — and how does that compare to the actual campaign request text?

## Method

- `extract_targets.py` — pulled all 196 targets + corpus metadata (title/store/categories/price) from `experiments/agent_eval/campaigns/campaign_005/exp_5_*/run_1/requests.jsonl` + `corpus_multi_domain.sqlite`.
- `gen_queries.py` — LLM-generated ONE natural Vietnamese descriptive request per target, paraphrasing title/attributes **without copying the English title or model numbers** (same protocol as `vi_retrieval` step2b). Faithful EN keyword translation per query. 196/196 generated.
- Arms = 4 query sources × retrieval paths:
  - `desc_vi` / `desc_en` — descriptive VI query / its EN translation (**human-like**)
  - `req_vi` / `req_en` — the **actual campaign request text** / its faithful EN translation (**current eval**)
- `run_bm25.py` — production FTS5 path (`_tokenize` → OR-match → `bm25()` order) on the **full 2.64M catalog**, top-1500.
- `run_dense.py` — cosine top-1500: MiniLM on **full catalog** (existing `multi_domain_full` build); e5base + bge-m3 on the **restricted 433k universe** (includes all 196 targets + neighbors — *inflated absolute numbers, relative comparison only*).

## Results (n=196 targets per arm)

| arm | universe | r@10 | r@50 | r@200 | r@1000 | MRR |
|---|---|---:|---:|---:|---:|---:|
| **e5base desc_en** | restricted* | **0.367** | 0.658 | 0.827 | 0.959 | 0.223 |
| **bge-m3 desc_en** | restricted* | 0.337 | 0.638 | 0.806 | 0.944 | 0.190 |
| **bm25 desc_en** | **full** | 0.184 | 0.347 | 0.628 | 0.806 | 0.106 |
| minilm desc_en | full | 0.128 | 0.255 | 0.444 | 0.730 | 0.058 |
| bge-m3 desc_vi (raw VI) | restricted* | 0.321 | 0.531 | 0.724 | 0.878 | 0.178 |
| e5base desc_vi (raw VI) | restricted* | 0.245 | 0.423 | 0.612 | 0.801 | 0.136 |
| bm25 desc_vi (raw VI) | full | 0.005 | 0.031 | 0.087 | 0.138 | 0.007 |
| minilm desc_vi | full | 0.000 | 0.000 | 0.026 | 0.066 | 0.000 |
| **all req_* arms** | — | **≤0.005** | ≤0.031 | ≤0.087 | ≤0.138 | ≤0.007 |

*restricted = 433k-item universe; absolute values inflated vs full catalog.

Per-kind (desc_en, r@10): cold_text 0.35–0.55, exclusion 0.23–0.39, personalized 0.18–0.36, similar 0.08–0.34 — descriptive queries help every kind.

## Findings (measured)

1. **Campaign request text retrieves ~nothing.** Every `req_*` arm — best retriever, translated EN, full catalog — sits at r@10 ≈ 0.0–0.5% and r@1000 ≤ 13.8%. This is the quantitative confirmation of the request-content root cause: *no retriever can recover an item the request does not describe.*
2. **With descriptive queries, retrieval is genuinely good.** e5base/bge-m3 reach 34–37% r@10 (restricted); BM25-EN reaches 18.4% r@10 on the **full 2.6M catalog** — and 80.6% r@1000, meaning the target is almost always *somewhere* in a feasible candidate pool.
3. **Raw Vietnamese descriptive queries work with multilingual dense** — bge-m3 desc_vi r@10 = 32.1% vs 33.7% for EN (restricted). Cross-lingual alignment is strong on descriptive text; BM25 cannot do this at all (0.5%).
4. **MiniLM (current production dense) is the weakest dense arm** even on EN (12.8% vs e5base 36.7% restricted — different universes, but the gap is large).

## Caveats

- Restricted-universe dense numbers are **not** comparable to full-catalog BM25/MiniLM absolutes; only within-universe arm ordering is valid. A full-catalog e5base/bge-m3 build would be needed for apples-to-apples dense numbers (~hours of embedding).
- Descriptive queries were LLM-generated from titles — richer than typical short queries but the right shape for "user describes what they want."
- `req_*` r@1000 ≈ 2.6% for BM25-en likely reflects popularity/rating tie-breaks surfacing common items, not real retrieval.

## Implication

The retrieval stack is **not** the bottleneck — the request specification is. If requests carried descriptive content, current components already achieve double-digit recall@10 and ~80% recall@1000. The path to a meaningful retrieval metric is a descriptive request kind (or external query logs); improving the retriever further is secondary until then.
