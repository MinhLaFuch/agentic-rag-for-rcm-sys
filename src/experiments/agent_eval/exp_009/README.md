# exp_009

- timestamp: 2026-10-26T09:35:41.479981+00:00
- seed: 42
- git_commit: ec14e6ddb818fb9459eec858b9a10550105b4cbe
- runtime_seconds: 850.92
- dataset: {"tag": "multi_domain", "splits_dir": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "metadata_coverage": 1.0, "n_requests": 66, "profile_as_of_timestamp": 1617737606549, "mapping_hash": "13e3e5b362225fcb912db2c1d6bb5d6ef7a728c193547f9688296c4cd3ebc848", "split_files": {"train": {"path": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\train.parquet", "size_bytes": 2129059868, "mtime_ns": 1791097998458712300}, "validation": {"path": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\validation.parquet", "size_bytes": 298584636, "mtime_ns": 1791098002860050100}, "test": {"path": "C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\test.parquet", "size_bytes": 296088629, "mtime_ns": 1791098007175561600}}}

Kinds ['constrained', 'cold_text'] take their category/price constraints from held-out items: an ORACLE upper bound, never report them as real-query results. 'similar' and 'personalized' use fit history only. Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting.
