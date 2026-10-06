# exp_001

- timestamp: 2026-10-06T04:29:02.204133+00:00
- seed: 42
- git_commit: 86263ddeb1dd1a58d26dcad391744ca5ff55e0d7
- runtime_seconds: 546.49
- dataset: {"splits_dir": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "metadata_coverage": 1.0, "n_requests": 20, "profile_as_of_timestamp": 1617737606549}

Kinds ['constrained', 'cold_text'] take their category/price constraints from held-out items: an ORACLE upper bound, never report them as real-query results. 'similar' and 'personalized' use fit history only. Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting.
