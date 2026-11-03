# Outside-core content retrieval pilot

Decision: do not enable content fusion in the final baseline on this evidence.

The fixed diagnostic cohort contains 300 validation users with outside-core
targets: 100 cold, 100 sparse, 100 warm. Query input is limited to the latest
three train interaction titles. No target title/category enters a query.
The TEMP FTS index contains 1,516,453 outside-core catalog items with
first_seen <= validation start. Document statistics are computed on that
visible subset. All history items are excluded. This remains a static-metadata
historical proxy, not a verified launch-date snapshot.

| Arm | Outside-core recall@20 | Outside-core recall@100 | All-target recall@20 on this diagnostic cohort |
|---|---:|---:|---:|
| Full-history popularity | 0 | 0 | 0.002648 |
| Outside-core BM25 | 0 | 0 | 0 |
| RRF60 popularity + content | 0 | 0 | 0.002648 |

This sample is label-derived and equally segmented. Do not compare its pooled
metrics directly with full-population baselines. Every target remains in the
metric denominator; failures/no-query have empty content output. The candidate
budget is 100 per source (up to 200 source candidates for RRF before Top-K).

Of 300 requests, 135 succeeded, 65 timed out at the configured 2-second budget,
and 100 cold requests had no history query. The 200 history-bearing users thus
have a 32.5% query timeout rate. A zero result under these conditions does not
prove that content retrieval generally cannot help. It establishes that this
particular history-title BM25 setup has no measured benefit and is not qualified
for adoption. Pure content returned zero outside-core hits even at 100.
RRF also reduced diagnostic all-target recall@100 from 0.005497 to 0.004870.

The 300 users have 434 outside-core targets, of which 255 were not observed in
full train and 179 were observed in train. No sampled outside-core target was a
same-user train repeat. Cold users lack an observed query despite some targets
being globally available; inventing a target-derived query would be an oracle
experiment and is not a fix for that missing signal.

Engineering rerun: exp_002 used SQL ORDER BY bm25(),item_id, forcing a temporary
sort, and had 144 timeouts among 200 history-bearing requests. exp_003 uses
FTS5's streamed rank shortlist and then a score/item_id sort within that shortlist.
The exact same users and query strings were replayed. Timeouts fell to 65; this
is a runtime improvement, not independent quality confirmation. Equal-score
cutoff membership follows the SQLite rank shortlist. Runtime including catalog
setup and summary was 449.13 seconds.

Audit checks passed: same cohorts and queries across exp_002/003, all 13,147
unique returned candidates outside core, and all with non-null first_seen <=
cutoff. Candidate/label metrics are recorded per user in records.jsonl; its
checksum and input hashes are in summary/config.yaml. No test rows were read.
