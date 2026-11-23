# TODO — retrieval/ranking bottleneck investigation (consolidated)

Merged 2026-11-22 from `todo-2026-11-20.md`, `todo-2026-11-20-q13-recheck.md`,
`todo-2026-11-20-fixes.md` (all superseded by this file).
Fixed target set = campaign_005 exp_5, 152 requests / 196 targets,
as_of=1617737606549, `historical_static_catalog` policy.
Evidence base: `investigations/INVESTIGATION_REPORT.md`,
`BOTTLENECK_OPEN_QUESTIONS.md`, `RETRIEVAL_RANKING_BOTTLENECK.md`.
Commits: `dc100d1` (Q18), `ab8811b` (BPR CUDA + Q2 eval), `6fb8743`
(learned scorer wiring + Q2 gated + docs).

## DONE — investigation pass (read-only, all closed)

- [x] Q17/Q20 splits — clean cutoffs, no target leakage; segments exact
- [x] Q11 cross-domain users — histories merged by design; collision
      unprovable, implausible; ~21% requests have majority-outside-domain
      history (q11_collision_proxy.json)
- [x] E-Q10 popularity ceiling — trivial popularity beats whole pipeline
- [x] E-Q11 target predictability — 75.5% share ≥1 surface signal
- [x] Q4 filter orderings — rating_number r@200=38.7% vs eval's item_id 0.65%
- [x] Q6 scorer comparison v1 — baseline 31.75%, pure pop 60.3%, honest
      learned 71.4% rescue@10 (injection metric only)
- [x] Q3 SearchTool timeouts — FTS fast; root cause = FilterTool correlated
      EXISTS (fixed)
- [x] Q12 k-core sweep — co-occurrence ~flat at every K; signal absent
- [x] Q13 first_seen proxy — 18.4% targets hidden; "Date First Available"
      coverage/protocol comparison done (q13b/c/d)
- [x] Q14 dedup — 0 cross-domain ASINs, 0 within-domain dups
- [x] Q15 category coverage — missing cats are a SOURCE-DATA gap, not
      preprocessing loss
- [x] Q16 rating_number semantics — raw meta count, Spearman 0.73/0.65
- [x] Q19 embeddings — doc text = title+store+cats; description/features
      UNUSED; query-format ablation later showed ~0% recall regardless
- [x] E-Q8/E-Q9 leftovers — text-field coverage + temporal density normal
- [x] `INVESTIGATION_REPORT.md` written

## DONE — fix phase

- [x] F1 FilterTool SQL fix committed (correlated EXISTS → IN-subquery)
- [x] F2/Q18 causal popularity ordering committed (`dc100d1`)
- [x] F3 planner A/B — always-on category filter LOST (task_success
      0.589 vs 0.679); baseline prompt kept
- [x] F9 Q10 category-hit metric — exact-item hits 0/196; category-level
      documented as secondary metric
- [x] F10/Q8 CF A/B — popularity 0.0077 > item_knn 0.0055 > bpr_mf 0.0054
      recall@10 (50k users); CF track CLOSED. Also fixed the 6h eval stall
      (dense lexsort → exact top-k, sparse paths, CUDA BPR fit+eval,
      `eval_user_sample`) — run now ~15min
- [x] F4/Q5-7 scorer evidence — replicated on post-F2 pools; `LearnedScorer`
      wired (`mode: learned`, configurable weights, audit-script support,
      tests) — **live A/B NEGATIVE** (cold_text task_success 0.65→0.45,
      target_reachable 0.50→0.143); `scoring.yaml` stays `mode: baseline`
- [x] F5/Q2 inferred categories — built (kNN top-1 vote, 229,975 items) +
      gated variant (53,333); **both live evals NEGATIVE** (guessed cats
      pollute filter pools); DISABLED, artifact at
      `investigations/item_categories_inferred_gated.parquet`
- [x] F6 CF research track — closed by F10
- [x] F8 cross-domain ablation — expected null, eval skipped per analysis
- [x] Q9 causal rating proxy — `min_rating`/`average_rating` work under
      historical policy; price/rating_number correctly fail-loud

## OPEN — remaining work

- [ ] **Embedding/dense retrieval replacement** — user's model evaluation
      pending; highest-leverage remaining lever (dense leg ~0% recall).
      On decision: re-embed catalog → wire dense leg → recall probe first.
- [ ] **Retrieval enrichment** — `description` (58-66%) and `features`
      (71-80%) coverage exist unused in raw meta; candidate FTS/doc-text
      additions (cheap alternative/complement to re-embedding)
- [ ] **F7 eval protocol (partial)** — Q23: larger/second eval set only
      for decision-critical changes (case-by-case); optional
      `snapshot`/`no_filter` temporal sensitivity run to price the
      `first_seen` proxy cost (~7pp ceiling per q13d)
- [ ] **Learned scorer refit (optional)** — only if new evidence motivates;
      any `mode: learned` enable requires a fresh live A/B
- [ ] **Q2 revisit (optional)** — only with precision-first assignment
      (abstain unless top-1 dominates) or non-category enrichment path

## Standing caveats (accepted, documented)

- `first_seen` = interaction-derived proxy, not launch dates; ~7pp ceiling
  cost vs availability-date protocol (q13d); "Date First Available" meta
  field is a candidate causal-safe replacement (coverage caveats per domain)
- price / min_rating_number remain fail-loud under temporal policy (no
  causal proxy exists)
- n=152 requests per eval → few-request swings; treat <~5pp deltas as noise
