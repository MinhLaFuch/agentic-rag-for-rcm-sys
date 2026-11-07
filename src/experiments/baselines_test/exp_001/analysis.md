# Frozen baseline test evaluation — 2026-11-03

The run completed on 4,519,632 target-bearing test users. Audits passed for
recorded split hashes against Stage 3, manifest identity, expected model fit
sources, matching user cohorts, cold-user equality, finite metric ranges,
segment-weighted overall means, and monotonic recall/NDCG/hit-rate cutoffs.
The saved source fingerprint matches the workspace at review time.

Protocol: CF similarity remains frozen on train-core (20 neighbors); user
profiles, exclusions and popularity use train + validation. Hybrid weight 4
was chosen on validation. K=5,10,20 with primary NDCG@10. Item familiarity is
relative to train-core, so outside-core items are not necessarily new to all
pre-test history. The broader-history hybrid popularity source is explicit in
config even though fit_splits_by_model lists train_core for the CF component.

| Metric | Full-history popularity | Hybrid weight 4 | Hybrid relative change |
|---|---:|---:|---:|
| Recall@5 | 0.00027342 | 0.00031168 | +13.99% |
| NDCG@5 | 0.00016657 | 0.00018633 | +11.87% |
| Recall@10 | 0.00314158 | 0.00316033 | +0.60% |
| NDCG@10 | 0.00120477 | 0.00121530 | +0.87% |
| Hit rate@10 | 0.00457670 | 0.00460303 | +0.58% |
| Recall@20 | 0.00654413 | 0.00565093 | -13.65% |
| NDCG@20 | 0.00206577 | 0.00184857 | -10.52% |
| Hit rate@20 | 0.00921093 | 0.00796149 | -13.56% |

Primary NDCG@10 increases only 0.00001053 in absolute units. Aggregate results
alone do not provide paired confidence intervals or significance evidence.
The hybrid is not consistently superior across cutoffs; its Top-20 degradation
must be reported rather than selecting only the favorable Top-5 result.

Cold users: 2,118,115 (46.86%); sparse: 1,709,170 (37.82%); warm: 692,347
(15.32%). Cold-user rankings have identical metrics, as expected for the same
popularity fallback. Sparse Recall@10 rises from 0.00306485 to 0.00312017;
warm Recall@10 falls from 0.00267923 to 0.00266508 despite a small NDCG@10 gain.

Outside-core targets account for 58.95% of unique test target pairs, compared
with 35.43% on validation. Both models have zero outside-core quality metrics
at every reported K. This is a core-familiarity definition, not proof that all
such items are unseen in train + validation or unavailable at the cutoff.

Hybrid test Recall@10 and NDCG@10 are respectively 66.23% and 70.33% below its
validation results. Different cohorts, target periods and history sources mean
this is a descriptive temporal generalization gap, not an isolated causal
estimate of drift. The frozen older CF core and changed target mix are plausible
contributors, not demonstrated root causes.

Recorded model-loop/report runtime: 3945.47 seconds (65m45s), excluding earlier
manifest verification and dataset preparation. Coverage@20 is 259,280 unique
items for hybrid versus 32 for popularity; this broader exposure did not yield
higher Top-20 accuracy.

Decision: retain this as the final test result for the frozen baseline protocol.
Do not adjust weight, K or model choice based on this test and then call a rerun
an untouched final test. Any further improvements are new development work,
requiring an independent future holdout or clearly disclosed exploratory results.
Data preparation and this baseline evaluation are complete; agent/planner,
retrieval and inference evaluation remain separate parts of the system study.
