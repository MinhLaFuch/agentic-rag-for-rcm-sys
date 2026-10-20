# exp_004

- timestamp: 2026-10-19T17:22:25.111462+00:00
- seed: 42
- git_commit: None
- runtime_seconds: 77.92
- dataset: {"tag": "multi_domain", "splits_dir": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "metadata_coverage": 1.0, "n_requests": 14, "profile_as_of_timestamp": 1617737606549, "mapping_hash": "13e3e5b362225fcb912db2c1d6bb5d6ef7a728c193547f9688296c4cd3ebc848", "split_files": {"train": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\train.parquet", "size_bytes": 2132738419, "mtime_ns": 1790441165783867400}, "validation": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\validation.parquet", "size_bytes": 298978513, "mtime_ns": 1790441169496644100}, "test": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\test.parquet", "size_bytes": 296357912, "mtime_ns": 1790441173153835700}}}

Kinds ['constrained', 'cold_text'] take their category/price constraints from held-out items: an ORACLE upper bound, never report them as real-query results. 'similar' and 'personalized' use fit history only. Ambiguous requests have no ground truth; their success = the agent asked a question instead of acting.
