"""Validate prior experiment samples before excluding their users."""
from pathlib import Path

import yaml


def confirmation_cohort(paths, *, tag, split, user_hash, item_hash):
    excluded = set()
    for path in paths:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        dataset = doc["run"]["dataset"]
        expected = {"tag": tag, "eval_on": split,
                    "user_mapping_hash": user_hash, "mapping_hash": item_hash}
        for key, value in expected.items():
            if not value or dataset.get(key) != value:
                raise ValueError(f"exclusion manifest {path}: incompatible {key}")
        groups = doc["config"]["sampled_user_ids"]
        if not isinstance(groups, dict) or not groups:
            raise ValueError(f"exclusion manifest {path}: missing sample")
        manifest_users = set()
        for users in groups.values():
            if not isinstance(users, list) or any(type(u) is not int or u < 0 for u in users):
                raise ValueError(f"exclusion manifest {path}: invalid user indices")
            manifest_users.update(users)
        if not manifest_users:
            raise ValueError(f"exclusion manifest {path}: empty sample")
        excluded.update(manifest_users)
    return excluded
