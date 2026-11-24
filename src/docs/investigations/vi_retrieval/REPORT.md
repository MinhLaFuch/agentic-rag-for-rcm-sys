# Vietnamese-request retrieval audit

Date: 2026-11-23. Scope: 152 fixed campaign requests / 196 held-out targets
(campaign_005 exp_5). Catalog 2,637,776 items, English-only. No pipeline
code/config/prompt changes — scripts + outputs only in this directory.

## Step 1 — what the tools actually receive (MEASURED)

Source: `step1_queries.json` (trajectory audit of exp_5 template, exp_11/exp_12 llm).

| run | requests | request text lang | SearchTool calls | query lang | FilterTool calls |
|---|---|---|---|---|---|
| exp_5 template | 152 | 152 VI (100%) | 24 | 23 EN (95.8%), 1 category-only | 41 |
| exp_11 llm r0 | 152 | 152 VI | 15 | 15 EN (100%) | 32 |
| exp_12 llm r1 | 152 | 152 VI | 15 | 12 EN (80%), 3 category-only | 26 |

- The planner already emits **English** queries — mostly short category
  phrases ("baby floats", "external hard drives", "TV antennas"). The VI→EN
  mismatch hypothesis is dead *at the query level*.
- Requests themselves are template-style: "I am user <id> ... find 10 products
  in the '<Category>' category" — little item-descriptive content (see Step 3).
- Stopwords/diacritics: irrelevant in practice — queries are ASCII English
  already; 20-token cap never binds (queries are 2–5 tokens).
- Confidence: high (direct trajectory extraction). Could be wrong if other
  campaigns/templates produce VI queries — this covers the evaluated set only.

## Step 2 — cross-lingual probe (MEASURED)

Probe: 510 items (170/domain × popularity bands), one faithful VI description
each (`vi_queries.jsonl`, LLM-generated, style-matched to real requests).
Restricted universe: 433,555 items (probe + 196 targets + ~300k random +
150k same-category neighbors) in `restricted_corpus.sqlite`.
Restricted recall is inflated in absolute terms — valid for RELATIVE comparison
only. Full-catalog numbers reported for arms a–d.

Doc format: "title. Store. Main. Categories." (+ model prefixes for e5).

### Dense arms (restricted universe, `dense_metrics.json`)

| arm | model | query | recall@10 | recall@50 | recall@200 | recall@1000 | MRR |
|---|---|---|---:|---:|---:|---:|---:|
| b | MiniLM | raw VI | 0.000 | 0.006 | 0.018 | 0.051 | 0.0004 |
| d | MiniLM | translated EN | 0.320 | 0.500 | 0.675 | 0.816 | 0.194 |
| e | bge-m3 | raw VI | 0.222 | 0.369 | 0.553 | 0.749 | 0.129 |
| e | e5base | raw VI | 0.200 | 0.349 | 0.524 | 0.692 | 0.100 |
| e | bge-m3 | translated EN | 0.380 | 0.582 | 0.737 | 0.882 | 0.225 |
| e | e5base | translated EN | **0.422** | **0.592** | **0.759** | **0.896** | **0.259** |

MiniLM full catalog (`dense_metrics.json`): EN r@10=0.161, r@50=0.306,
r@200=0.449, r@1000=0.651, MRR=0.092; raw VI ≈ 0 everywhere.

### BM25 arms (`bm25_ranks_summary.json`)

| arm | universe | query | found@10 | @50 | @200 | @1000 | MRR |
|---|---|---|---:|---:|---:|---:|---:|
| a | restricted | raw VI | 13 | 23 | 39 | 104 | 0.012 |
| a | full | raw VI | 3 | 10 | 20 | 37 | 0.005 |
| c | restricted | translated EN | 184 | 271 | 349 | 415 | 0.211 |
| c | full | translated EN | 98 | 163 | 249 | 337 | 0.104 |

### Hybrid arm (f) — RRF(k=60) BM25(EN) + multilingual-dense(raw VI) (`hybrid_ranks.parquet`)

| fusion | recall@10 | recall@50 | recall@200 | recall@1000 | MRR |
|---|---:|---:|---:|---:|---:|
| BM25-en + bge-m3-vi | 0.375 | 0.586 | 0.739 | 0.875 | 0.202 |
| BM25-en + e5base-vi | 0.347 | 0.561 | 0.735 | 0.875 | 0.189 |

## Step 3 — target predictability, language-fair (MEASURED)

Source: `step3_predictability.json/.parquet` (BM25 peer rank, translated
requests vs full catalog FTS, exact rank among category peers censored at
1500) + `step3_dense_peers.parquet` (multilingual dense rank among universe
peers — restricted approximation).

| signal | old (E-Q11) | new |
|---|---:|---:|
| token overlap request∩target title | 11.7% | VI raw 7.1%, **EN translated 13.3%** |
| BM25 rank among category peers | — | only 6/196 targets in top-1500 hits at all; of those, recall@200=1.0% |
| multilingual dense rank among peers | — | e5base recall@10=1.0%, bge-m3=0.5% (n=184) |

By kind (EN token overlap): cold_text 50%, exclusion 15%, personalized 0%,
similar 16%.

**Conclusion**: translation does NOT unlock target predictability — the
campaign requests simply contain almost no item-descriptive tokens (they are
category-template + user-id boilerplate). The bottleneck is request CONTENT,
not language. Old ceilings 24.5%/62% effectively stand; language-fair text
signal moves overlap 11.7%→13.3% only.

## Final table — measured vs inferred

| # | item | key number | confidence | implication | measured? |
|---|---|---|---|---|---|
| 1 | Planner query language | 95.8–100% of SearchTool queries already EN | high | VI→EN query translation is NOT the retrieval bottleneck for this campaign | measured |
| 2 | Raw VI → BM25 | r@10 0.6–2.5% | high | lexical retrieval dies on untranslated VI | measured |
| 3 | VI→EN translate → BM25 | r@10 19.2% full / 36.1% restricted | high | translation is the single biggest lever IF queries were VI | measured |
| 4 | Raw VI → MiniLM dense | r@10 = 0.0% (full & restricted) | high | current dense leg is dead on VI input | measured |
| 5 | Translated → MiniLM dense | r@10 16.1% full / 32.0% restricted | high | dense works once language matches | measured |
| 6 | Raw VI → bge-m3 / e5base | r@10 22.2% / 20.0% restricted | high | multilingual encoders rescue raw VI partially — still below translated BM25 | measured |
| 7 | Best single arm | e5base+EN r@10 42.2% restricted | medium-high | multilingual encoder + translation > either alone | measured |
| 8 | Hybrid RRF (spec arm f) | r@10 37.5% (bge-m3) — does NOT beat c or e5-en | medium | fusion adds nothing over best single arm here | measured |
| 9 | Target token overlap after translation | 13.3% (was 11.7%) | high | request content, not language, caps predictability | measured |
| 10 | Dense rank among category peers | ~0.5–1% r@10, median rank ~58–87k | medium | even perfect language won't save category-templated requests | measured (restricted approx) |
| 11 | Friend's phrase-map translator vs multilingual embed | probe can't test phrase map directly; translated-BM25 ≈ what it approximates | medium | translator is competitive IF coverage is good; neural multilingual is the semantic fallback | inferred |
| 12 | Production impact today | agent eval queries already EN → VI stack is demo-path only | high | "big" commit's VI translator won't move campaign metrics | inferred from #1 |

## Caveats / what could make this wrong

- Restricted-universe recall is inflated; only relative arm comparisons valid.
- Probe queries are LLM-generated descriptions (rich text) — richer than the
  actual campaign requests; arm gaps may be larger in production.
- Translations are LLM-faithful (may preserve more content words than a
  production translator would emit).
- step3 dense peer ranks use the restricted universe (partial peer coverage)
  and raw campaign VI requests — approximates, not exact.
- BM25 peer rank censored at top-1500 hits; 190/196 targets fell outside.
- e5base/bge-m3 encoded in fp16 on RTX 3050 Ti — small numeric drift possible.
- The 40-query Track-B result in the "big" commit (NDCG@10 0.80) is a different
  task (labeled relevance, curated VI queries) — not comparable to these
  source-item retrieval numbers.
