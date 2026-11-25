# Vietnamese runtime validation

Run `scripts.evaluation.run_vi_runtime_ab` in the semantic environment. It
evaluates the validation split only, with the audit profile and pinned artifact
paths. Three arms isolate the dense retrieval contribution (lexical baseline
versus hybrid baseline), then the scorer contribution (hybrid baseline versus
HybridScorer weight 4). All arms use planner_memory, Vietnamese requests,
LLM answer composition and zero reflection rounds. Strict artifact failures
prevent accidental comparison against a fallback backend.
The launcher includes the profile's immutable audit overlay first in the
overlay chain, followed by each experiment overlay. Preparation validates
the actual audit contract and recorded split cutoffs before loading models
or calling the LLM; `--prepare-only` performs that check without running arms.

Default scope is realistic: requests are simulated from pre-target history.
These are Vietnamese templates, not independently collected natural user queries.
Recall/NDCG measure held-out item recovery, not general shopping relevance.
`--scope all` additionally exercises target-informed oracle requests; inspect
those request kinds separately and do not interpret their success as natural
query relevance. No test split is used to tune configurations.

Each arm exports requests, scored trajectories, metrics, diagnostics and reports.
After all runs finish, the launcher checks full request and target identity,
then exports two paired comparisons with bootstrap confidence intervals by kind.
Inspect `metrics.json` for wall_seconds_p50/p95 (includes planner and answer
composition), ranking metrics, tool failures, grounded answers, and diagnostic
retrieval/ranking losses. A/B deltas also include stochastic LLM planning;
small gains need replication. No variant is automatically promoted.

SearchTool now expands dense retrieval after metadata filtering until enough
candidates survive, the index is exhausted, or the fetch budget is reached.
`dense_fetch_k` and `dense_fetch_limited` expose the final budget and possible
underfill. This repairs lost candidates under restrictive filters but can add
latency, which must be measured on the real catalog.

Use a fresh output directory for changed configuration. `--resume` reuses
completed trajectories only if the existing evaluation protocol still matches.
Do not edit source or configuration during a running experiment.
