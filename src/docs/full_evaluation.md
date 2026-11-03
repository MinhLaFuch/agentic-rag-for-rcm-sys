# Full evaluation on the temporal train-core dataset

The default tag is `multi_domain_v2_audit_20261030`. Always record an explicit
`--tag` in reproducible commands. Run the commands below from `src` in PowerShell.

## Training and evaluation protocol

- Stage 3 declares `temporal_train_core`. CF similarity and popularity are learned
  from `train_core.parquet`, with its own `mapped/<tag>/fit_core` mappings.
- Ranking and agent evaluation validate the prebuilt ItemKNN checksum, mapping
  hashes, event-pair hash, fit split, tag and neighbor count before reuse. An
  incompatible cache stops the run. Missing caches are fitted on train-core.
- Local CF indices are translated through canonical IDs into global evaluation
  indices. Full pre-target history supplies scoring profiles, exclusion and
  cold/sparse/warm segments; the fit core never filters the evaluation cohort.
- Validation uses train history and validation targets. Test uses train plus
  validation history and test targets, while CF training remains the frozen
  train-core, matching Stage 4. This is not a refit-on-train-plus-validation test.
- Historical catalog policy gates by first observed interaction and masks mutable
  price/rating fields. Static metadata remains a proxy, not a historical snapshot.
- Baseline evaluation includes all target-bearing users. Ranking includes all
  target-bearing users with `--all-users`. Agent `--all-users` includes every
  eligible user per request kind; oracle/metadata requirements and request scope
  still determine eligibility. It does not promise one request for every user.

## Validation commands

```powershell
$env:PYTHONPATH = "."
.venv-baseline/Scripts/python.exe scripts/data_pipeline/verify_tag.py --tag multi_domain_v2_audit_20261030
.venv-baseline/Scripts/python.exe -u scripts/evaluation/run_baselines.py --tag multi_domain_v2_audit_20261030 --eval-on validation --models popularity,item_knn --ks 5,10,20 --experiments-dir experiments/baselines --progress-every 10000
.venv-baseline/Scripts/python.exe scripts/evaluation/ranking_eval.py --tag multi_domain_v2_audit_20261030 --eval-on validation --all-users --work-dir experiments/checkpoints/full_validation --ks 5,10,20
```

Resume ranking with the identical command plus `--resume`. Keep code, configs,
data and environment fixed during a resumable run. Sampled pilots can use
`--per-segment 10` instead of `--all-users`; these options are mutually exclusive.
Existing legacy checkpoints cannot be resumed under the new source fingerprint.

Baseline evaluation uses exact sparse Top-K for popularity and ItemKNN, including
the popularity-fallback wrapper. Popularity sorts once; ItemKNN ranks only scored
neighbors. Both preserve score-descending/index-ascending ties, seen exclusion,
zero-signal popularity fallback and `-1` padding. Ground truth is looked up only
at the recommended items, without a dense user-by-catalog matrix.

Baseline prints startup/model preparation stages and evaluation user count,
percentage, users/second, elapsed time and ETA. Evaluation updates after the first
batch, then every `--progress-every` users or 10 seconds at batch boundaries.
ETA covers the current model's evaluation loop only; input hashing, model setup,
final metric aggregation and other models are separate. Baseline has no resume;
its result is saved after both requested models finish. Stop an older running
baseline with Ctrl+C before restarting with the optimized code.

For agent evaluation, start with a sampled validation run. The full form is:

```powershell
.venv-baseline/Scripts/python.exe scripts/evaluation/run_agent_eval.py --tag multi_domain_v2_audit_20261030 --eval-on validation --all-users --request-scope realistic --trajectory-file full_validation_agents.jsonl
```

Agent evaluation can make millions of LLM calls at this population size. It still
materializes requests and trajectories in memory, while ranking persists its
work in batches. `--all-users` removes sampling; it does not make either runner
fully bounded in memory. Ranking also loads global history and target tables.
Use an appropriately provisioned machine and establish a pilot first.

Keep test quality evaluation until the validation protocol and parameters are
frozen. Building the Stage 4 test cache does not itself evaluate test targets.

The older `data_pipeline_v2_report.md` is a dated preflight report. Its statement
that v2 artifacts are absent is superseded by the October 31 artifacts; it is not
an assessment of the current dataset readiness.

## Improving ItemKNN after exp_004

Keep `exp_004` as the original baseline. Its ItemKNN uses core-only popularity
and fills zero-score tails by global item index. The opt-in
`HybridItemKNNRecommender` normalizes each user's CF scores by their maximum,
adds a weighted popularity score, and uses popularity to complete the list.
Popularity counts come from all unique pre-validation train pairs, including
items omitted from the CF core. CF similarity still comes only from train-core.
This is a changed model with an explicitly broader popularity source, not a
change to labels, cohort, or the old experiment's metrics.

```powershell
$env:PYTHONPATH = "."
.venv-baseline/Scripts/python.exe -u scripts/evaluation/tune_item_knn_hybrid.py --tag multi_domain_v2_audit_20261030 --per-segment 3000
```

The runner compares original CF, core-only popularity, full-history popularity
and weights 0, 0.25, 0.5, 1, 2, 4, 8. Each segment contributes up to 3000 tuning
users and 3000 different confirmation users. The selection objective weights
segment NDCG@10 by the validation population, not by the equal-size sample.
Only the fixed winning hybrid and the three controls are evaluated on
confirmation. Both cohorts are validation development data; they are not a new
untouched test because the entire validation split was already evaluated.
Outputs include exact cohort IDs, input hashes and the selected configuration
under `experiments/item_knn_hybrid/exp_NNN`.

After checking confirmation, run full validation with exactly the selected
weight, for example `--all-users --weights 1` if weight 1 was selected. The full
runner does not tune weights. Item-familiarity metrics retain the train-core
definition for comparability, so items outside core but observed in full train
can now receive popularity scores. Items with no pre-cutoff interactions still
need a separate content-based retrieval experiment; this blend cannot guarantee
nonzero metrics for them. These hybrid experiments do not change agent or
fixed-candidate ranking defaults automatically.

The first pilot (`item_knn_hybrid/exp_001`) selected weight **4**. On its disjoint
confirmation cohort the hybrid improved on the original ItemKNN and core-only
popularity, but full-history popularity remained slightly stronger. See its
`analysis.md` for population-weighted estimates and the unresolved zero metrics
on items outside train-core. Full baseline evaluation with this opt-in model:

```powershell
.venv-baseline/Scripts/python.exe -u scripts/evaluation/run_baselines.py --tag multi_domain_v2_audit_20261030 --eval-on validation --models popularity,item_knn --ks 5,10,20 --item-knn-hybrid-weight 4 --experiments-dir experiments/baselines --progress-every 10000
```

Omitting `--item-knn-hybrid-weight` keeps the original baseline behavior. The
hybrid weight and broader popularity source are recorded in the new experiment.

## Full-history popularity control and outside-core content diagnostic

The full-popularity control uses every pre-target training pair for popularity,
while retaining train-core item-familiarity buckets for comparison with exp_005:

```powershell
.venv-baseline/Scripts/python.exe -u scripts/evaluation/run_baselines.py --tag multi_domain_v2_audit_20261030 --eval-on validation --models popularity --popularity-source full_history --ks 5,10,20 --experiments-dir experiments/baselines --progress-every 100000
```

This control was run as `baselines/exp_006`. For future runs, the config records
per-model fit splits; the older exp_006 config's global `fit_splits: train_core`
refers to the retained core protocol. Its explicit `popularity_source:
full_history` and training code identify the actual popularity source as train.
The raw historical config is preserved; see exp_006/analysis.md.

The content diagnostic selects 100 users per history segment who have
outside-core validation targets. This is an explicitly label-derived diagnostic
cohort; queries use only titles of the latest three train interactions. The
catalog, including BM25 document statistics, contains only outside-core items
whose first_seen proxy is at or before validation start. All seen items are
excluded; static metadata remains a historical proxy.

```powershell
.venv-baseline/Scripts/python.exe -u scripts/evaluation/outside_core_content_probe.py --tag multi_domain_v2_audit_20261030 --per-segment 100 --candidate-budget 100 --timeout-seconds 2
```

The three arms are full-history popularity, outside-core BM25, and fixed RRF60
fusion. Each retrieval source has budget 100; fusion can use up to 200 unique
source candidates before taking its Top-K. No-query and timed-out requests stay
in the denominators with empty content output. Per-user records and hashes are
saved progressively in `outside_core_content/exp_NNN/records.jsonl`; a successful
run writes `summary/config.yaml` and `summary/metrics.json`. This runner has no
resume. An interrupted run must not be presented as a completed quality result.

Data preparation status and the criteria for finishing validation are tracked
in [data_readiness_status.md](data_readiness_status.md).
