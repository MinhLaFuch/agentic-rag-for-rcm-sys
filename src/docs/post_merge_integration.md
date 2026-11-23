# Post-merge runtime integration (2026-11-23)

Demo and agent evaluation now assemble SearchTool dependencies through
`package.embeddings.build_runtime_retrieval`. Explicit demo embedding paths
take precedence over the optional semantic-artifact configuration. Paths in
the demo configuration are relative to the repository root; semantic artifact
paths retain their documented `src/` base. Absolute paths are supported.

The default semantic loader is disabled because its configured artifacts are
absent. The audit runtime overlay can still activate the existing full-catalog
embedding, persisted ANN and sparse BM25 artifacts. The demo may fall back
with logged provenance; evaluation forces strict failure for requested invalid
artifacts. Both consumers now pass the Vietnamese query bridge configuration.

The demo uses the same train-core model loader as evaluation when the bundle
manifest declares that protocol. Its interactive metadata policy remains a
current snapshot (`as_of=None`); it is not a temporal evaluation run.

Campaign caches support absolute paths on another Windows drive. Synthetic
evaluation fixtures bind their bundle resolver without disabling production
domain validation.

This integration does not enable the experimental LearnedScorer or LTR by
default, and does not establish new full-catalog quality or latency results.
The five-source benchmark fusion and agent candidate union remain distinct.
