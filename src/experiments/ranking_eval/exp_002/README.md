# exp_002

- timestamp: 2026-10-20T02:32:45.718765+00:00
- seed: 42
- git_commit: None
- runtime_seconds: 1854.32
- dataset: {"tag": "multi_domain", "splits_dir": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "mapping_hash": "13e3e5b362225fcb912db2c1d6bb5d6ef7a728c193547f9688296c4cd3ebc848", "split_files": {"train": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\train.parquet", "size_bytes": 2132738419, "mtime_ns": 1790441165783867400}, "validation": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\validation.parquet", "size_bytes": 298978513, "mtime_ns": 1790441169496644100}, "test": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\test.parquet", "size_bytes": 296357912, "mtime_ns": 1790441173153835700}}}

All scorer variants receive identical persisted candidates per user and merge. Candidate generation uses popularity, ItemCF, and titles from fit history (realistic offline proxy). Ranking metrics use validation targets not seen in fit; target items already in fit are reported separately. This deterministic chain does not invoke the LLM planner.
