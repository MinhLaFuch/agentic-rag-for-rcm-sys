"""Data processing and EDA utilities."""

from .clean import clean_interactions
from .export.filter import kcore_filter
from .leakage._leakage_error import LeakageError
from .leakage.dup_split import duplicate_check
from .leakage.profile_snapshot import check_profile_snapshot
from .leakage.split import check_split_temporal_order
from .train.mapping import apply_id_mapping, build_id_mappings, load_mappings, save_mappings
from .train.temporal_split import compute_temporal_cutoffs, temporal_split

# Backward compatibility alias
check_no_duplicate_across_splits = duplicate_check

__all__ = [
    "apply_id_mapping",
    "build_id_mappings",
    "check_no_duplicate_across_splits",
    "check_profile_snapshot",
    "check_split_temporal_order",
    "clean_interactions",
    "compute_temporal_cutoffs",
    "duplicate_check",
    "kcore_filter",
    "LeakageError",
    "load_mappings",
    "save_mappings",
    "temporal_split",
]
