# Data readiness and evaluation gates

Current tag: `multi_domain_v2_audit_20261030`.

## Data engineering: complete for the current experiment

Stage 1 cleaning, Stage 2 domain merge, Stage 3 temporal splits and train-only
fit-core/mappings/cohort, and Stage 4 corpus/ItemKNN artifacts exist. The user
verified the full manifest chain with MATCH. Subsequent baseline experiments
record matching manifests and split hashes. Exp_004 and exp_005 evaluated all
5,096,026 validation users. No new data rebuild is required because one model
has weak recommendation metrics.

Keep this tag immutable. A changed cutoff, cleaning rule, core definition, domain
set or catalog build requires a new tag and verification, not edits to this tag.

## Requested validation follow-up: complete; final test configuration not frozen

The full-history popularity control is recorded in
`experiments/baselines/exp_006`. On the same full population, exp_005's hybrid
exceeds it by 2.75% Recall@10 and 2.77% NDCG@10 (relative, descriptive effects).
The retained cold-user results are identical; sparse/warm NDCG@10 gains are
5.46%/5.07%. These results isolate a smaller CF gain beyond broader popularity.

The outside-core content diagnostic is recorded in
`experiments/outside_core_content/exp_003`, with raw rows and a summary. On 300
diagnostic users the fixed BM25/history-title setup found zero outside-core
targets at Top-100, with 135 successful queries, 65 timeouts and 100 no-query
cold users. The rank-streaming rerun improved runtime reliability over exp_002
but did not establish quality benefit. Content fusion is not adopted.

These requested checks are finished. Their limitations are recorded; they do
not reopen data cleaning or splitting. The selected hybrid weight 4 remains a
baseline candidate with full-validation evidence, not an automatically deployed
agent/ranking policy. Model/protocol freeze and test quality evaluation are still
separate steps. See [validation_baseline_decision.md](validation_baseline_decision.md).

Before freezing the final evaluation configuration:

1. Compare core popularity, full-train popularity and the selected CF hybrid on
   the same full validation population, labels, exclusions and item-familiarity
   buckets. This isolates the broader popularity source from the CF contribution.
2. Run a content diagnostic with queries derived only from pre-cutoff history.
   Restrict the catalog and lexical index statistics to items visible by the
   cutoff. Report candidate recall, ranking recall, no-query cases and errors.
3. Separate outside-core targets already observed in full train from targets
   never observed in full train, and report repeated user-item targets excluded
   by the recommendation policy. Keep all denominators explicit.
4. Select the final model, weight, K, retrieval budget, history query rule,
   catalog policy and fit/refit protocol using validation only. Record a frozen
   configuration and the unresolved limitations before any test quality run.

A zero cold-item metric is a result to explain, not a reason to remove those
targets or use future interactions. The current first-seen proxy cannot establish
real product launch dates or recover historical price/title snapshots. Genuine
new users have no history-title query; an intent-driven cold-user evaluation is
a separate request-based protocol.

The content diagnostic is an exploratory validation pilot. A negative result is
still a completed experiment; it does not by itself justify deploying content
fusion or running it over every validation user. If a variant improves on a
pilot, confirm it on a disjoint validation cohort with fixed settings before
scaling. Validation has already been inspected, so it is not a new untouched test.

## What “finished” means

The data preparation work is finished for this immutable tag. The remaining
validation work is finished when the comparisons above have recorded results
and the final protocol is frozen, even if documented cold-start limitations
remain. Runtime, retrieval quality and agent/tool/inference evaluation belong
to the recommendation system evaluation, not unfinished cleaning or splitting.
No calendar completion date can be promised before these results are available.
The final test evaluation remains a separate last step after configuration freeze.
