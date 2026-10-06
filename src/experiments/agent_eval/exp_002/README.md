# exp_002

- timestamp: 2026-10-06T08:36:20.825891+00:00
- seed: 42
- git_commit: 05002408b525977136910439349a65d2649edec6
- runtime_seconds: 700.8
- dataset: {"splits_dir": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "metadata_coverage": 1.0, "n_requests": 20, "profile_as_of_timestamp": 1617737606549}

Kinds ['constrained', 'cold_text'] take their category/price constraints from held-out items: an ORACLE upper bound, never report them as real-query results. 'similar' and 'personalized' use fit history only. Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting.
