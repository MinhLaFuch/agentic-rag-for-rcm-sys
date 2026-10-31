"""Resolve the cohort policy recorded for a data tag."""

from __future__ import annotations

import json

from ...config import get_data_paths


def cohort_policy_for_tag(tag):
    """Return cohort semantics recorded by Stage 3; legacy remains explicit."""
    manifest = get_data_paths(tag).splits_dir / "stage_3.manifest.json"
    if manifest.is_file():
        protocol = json.loads(manifest.read_text(encoding="utf-8")).get("flags", {}).get("data_protocol")
        if protocol == "temporal_train_core":
            return "all target-bearing users; segment by unique pre-cutoff train history; fit-core does not filter cohort"
    return "existing pre-split filtered cohort; future-informed selection"
