# ItemKNN hybrid validation pilot

Selected weight: **4**, selected using population-weighted segment NDCG@10 on 9,000 tuning users. Evaluated once on 9,000 different confirmation users (3,000 per segment). Both are validation development cohorts, previously covered by full-validation exp_004.

The table reweights segment means by the actual validation population. These are stratified sample estimates, not full-validation results or significance claims.

| Model | Recall@10 | NDCG@10 | Hit rate@10 |
|---|---:|---:|---:|
| original_item_knn | 0.005269 | 0.002337 | 0.006982 |
| core_popularity | 0.007801 | 0.003152 | 0.010165 |
| history_popularity | 0.008980 | 0.003921 | 0.012063 |
| hybrid_item_knn_w4 | 0.008829 | 0.003876 | 0.011766 |

Hybrid relative to original ItemKNN: Recall@10 +67.58%, NDCG@10 +65.87%.
Hybrid relative to core popularity: Recall@10 +13.18%, NDCG@10 +22.98%.

Full-history popularity slightly outperforms the hybrid on confirmation. The experiment supports improving the old ItemKNN with stronger popularity, but does not establish CF adds value over the stronger popularity control. No production default or agent policy was switched.

## Why cold-item metrics remain zero

All four confirmation models have zero Recall@10 for items outside train-core. Across all validation unique pairs, 2,756,500 targets are outside core: 1,100,517 were observed in full train and 1,655,983 were never observed in full train. Full-history popularity can score the first group, but it did not place their targets in Top-20 on this pilot. Truly unobserved items have neither CF similarity nor popularity; they need a separate content experiment with catalog availability defined at cutoff. Do not drop these targets or use future interactions to inflate metrics.

## Reproduction

From src:

```powershell
.venv-baseline/Scripts/python.exe -u scripts/evaluation/tune_item_knn_hybrid.py --tag multi_domain_v2_audit_20261030 --per-segment 3000
```

Full baseline evaluation with the selected hybrid:

```powershell
.venv-baseline/Scripts/python.exe -u scripts/evaluation/run_baselines.py --tag multi_domain_v2_audit_20261030 --eval-on validation --models popularity,item_knn --ks 5,10,20 --item-knn-hybrid-weight 4 --experiments-dir experiments/baselines --progress-every 10000
```

The initial pilot evaluator recorded target_item_seen_ratio over the entire validation population, even when evaluating a cohort. Its ranking and per-item quality metrics used the selected cohort. The evaluator now scopes that ratio to the selected cohort for future runs.
