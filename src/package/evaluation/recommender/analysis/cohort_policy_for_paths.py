"""Resolve the cohort policy recorded for a dataset bundle."""

from __future__ import annotations

import json
from pathlib import Path


def cohort_policy_for_paths(paths) -> str:
    """Return cohort semantics recorded by Stage 3; legacy remains explicit.

    Takes an already-resolved ``DataPaths`` so callers share the same dataset
    resolution (and tests can substitute paths) — ``--domain`` selection and
    unknown-domain rejection happen in ``get_data_paths``/``resolve_dataset_tag``.
    """
    manifest = Path(paths.splits_dir) / "stage_3.manifest.json"
    if manifest.is_file():
        protocol = json.loads(manifest.read_text(encoding="utf-8")).get("flags", {}).get("data_protocol")
        if protocol == "temporal_train_core":
            return "all target-bearing users; segment by unique pre-cutoff train history; fit-core does not filter cohort"
    return "existing pre-split filtered cohort; future-informed selection"
