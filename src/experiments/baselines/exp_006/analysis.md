# Full-history popularity control vs selected hybrid

Evaluated on the same 5,096,026 validation users and exact split/manifest hashes as exp_005. Core-item familiarity buckets are preserved even though popularity learns from all pre-target history. No test quality evaluation was performed.

| Model | Recall@10 | NDCG@10 | Hit rate@10 |
|---|---:|---:|---:|
| popularity | 0.007754 | 0.003148 | 0.010732 |
| item_knn+popularity_fallback | 0.005222 | 0.002328 | 0.006961 |
| hybrid_item_knn_w4 | 0.009359 | 0.004096 | 0.012822 |
| history_popularity | 0.009109 | 0.003985 | 0.012430 |

Hybrid exceeds full-history popularity by 2.75% Recall@10 and 2.77% NDCG@10 (relative). These are descriptive full-validation effects, not significance claims or independent test confirmation. Much of the earlier improvement over exp_004 is explained by broader popularity input; CF adds a smaller measured gain.

Cold-user results are identical between these two models: no CF history means the same full-history popularity order. Both models retain zero cold-item metrics at K=5/10/20; full-history popularity does not resolve outside-core Top-K target recovery.

Runtime recorded for the model loop and result construction: 238.54 seconds; excludes earlier manifest verification and data preparation.

The source fingerprint identifies this run. Subsequent changes to the separate content-probe implementation mean it need not match the latest workspace fingerprint. Raw metrics and config are kept unchanged.

Provenance note: config.popularity_source is full_history, and the model was fitted on the full pre-target fit_matrix. The inherited global fit_splits: train_core field refers to the retained CF-core protocol and is not the popularity model training source. Future runs now record fit_splits_by_model explicitly. The core item-familiarity buckets were retained via item_familiarity_matrix.
