# exp_004

- timestamp: 2026-10-19T17:33:17.136342+00:00
- seed: 42
- git_commit: 61674c859b2aa0f2fb0a560bf5c3ed544d458453
- runtime_seconds: 1456.53
- dataset: {"splits_dir": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "metadata_coverage": 1.0, "n_requests": 146, "profile_as_of_timestamp": 1617737606549}

Kinds ['constrained', 'cold_text'] take their category/price constraints from held-out items: an ORACLE upper bound, never report them as real-query results. 'similar' and 'personalized' use fit history only. Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting.
