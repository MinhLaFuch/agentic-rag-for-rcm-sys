# Data pipeline v2: leakage comparison preflight

**Status: blocked before validation evaluation.** No validation baseline or test evaluation was run. The requested tag manifests are not valid, and the new multi-domain tag artifacts are not present in this workspace. The test split was not opened for evaluation or model selection; `verify_tag.py` only hashed listed artifact bytes.

## Tag and artifact verification

`src/scripts/data_pipeline/verify_tag.py` was run for both requested tags on 2026-10-30.

| Tag | Verification | Verified evidence | Decision |
|---|---|---|---|
| `multi_domain` | `MISMATCH` | Missing Stage 1 manifests for `Toys_and_Games` and `Electronics`, plus Stage 2, 3, and 4 manifests. Existing artifacts include filtered data, mappings, train/validation/test splits, corpus, and ItemKNN files. | Do not publish new metrics as manifest-traceable. Existing artifacts are legacy and have no complete provenance chain. |
| `multi_domain_v2` | `MISMATCH` | Missing the same two Stage 1 manifests and Stage 2, 3, and 4 manifests. No `multi_domain_v2` filtered, mapping, split, corpus, or ItemKNN directory was found. | Cannot run evaluation; the new tag's data artifacts are absent. |

The legacy `multi_domain` split files were last modified 2026-09-26; the corpus and ItemKNN files were last modified 2026-10-19. The current shared `resource/cleaned/Video_Games/interactions.parquet` and its Stage 1 manifest were written 2026-10-30 for `video_games_traincore5_v1_cleanfix`. The original cleaned input used to make the legacy tag is therefore not represented by the current Stage 1 manifest. Do not create a manifest retroactively and treat it as original provenance.

The legacy corpus sidecar is `format_version: 1` and records mapping hash `13e3e5b3…`; the legacy ItemKNN sidecars are also format version 1 and do not record `fit_splits` or a mapping/split provenance protocol. Existing experiment records mention other mapping hashes and train file sizes, but these discrepancies do not identify their cause. No old manifest chain is available to resolve them.

The available `video_games_traincore5_v1_cleanfix` tag is a single-domain Video_Games build. It is not a substitute for `multi_domain_v2`.

## Evaluation readiness findings

- `run_baselines.py` supports `popularity,item_knn` and `--ks`, and evaluates the full validation target set. It does not currently verify the tag manifest or save its manifest SHA in experiment config. Its recorded split metadata uses paths, sizes, and modification times rather than input SHA256 values.
- `run_baselines.py` does not query the corpus/catalog. It can compare ranking on each split, but cannot estimate the catalog-time-gating effect by itself; that requires a separate paired catalog-policy arm in the retrieval/ranking evaluation.
- `ranking_eval.py` verifies a tag manifest and can record the manifest SHA. It writes hashed candidate/scored artifacts, but its current summary segments by user history only (`cold`, `sparse`, `warm`). It does not report metrics by domain, warm/cold target item, or same/cross-domain target, and does not calculate bootstrap confidence intervals.
- `package/evaluation/ablation` contains bootstrap utilities. They can be reused once per-user metric rows and a defensible comparison cohort are defined.
- Because the legacy and temporal protocols have different candidate populations and potentially different validation targets, same seed alone does not create the same users or ground truth. The report must include native-cohort results and separately label any common-user analysis; targets should be matched by canonical user/item IDs only where the protocol gives a meaningful match.

## What cannot yet be concluded

No user/target loss counts between the legacy and v2 pipeline can be reported: v2 splits are absent. No estimate of optimism from pre-split k-core or an unrestricted catalog can be calculated from these artifacts. No baseline ordering change can be claimed. We have not run validation models, and the test split remains unused.

## Required next steps

1. Recover the immutable legacy Stage 1 inputs/outputs and their provenance, or explicitly label a reconstructed legacy run as a new experiment. The current shared cleaned Video_Games artifact cannot serve as evidence for the September legacy build.
2. Build all domains into a new immutable v2 tag using the intended no-k-core-before-split protocol, then run `verify_tag.py --tag <tag>` and require `status=match` before evaluation.
3. Extend the evaluation outputs to record per-user metrics for cold/sparse/warm user history, domain, warm/cold target item, and same/cross-domain targets; add bootstrap CIs and user/target denominators. Add manifest SHA and input hashes to `run_baselines.py` experiment outputs.
4. Freeze the validation protocol and run popularity and ItemKNN with K=5,10,20 on both validated tags. Keep test unevaluated until the configuration is explicitly confirmed.
5. Compare both native cohorts and clearly identified common-user subsets where ground truth is comparable. Report cohort/target attrition at each pipeline stage and discuss the combined old-vs-new change as an association unless the catalog and cohort effects are isolated in separate controls.
