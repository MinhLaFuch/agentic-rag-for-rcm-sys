"""Exploratory-data-analysis helpers for interaction metadata and splits."""

from .eda import (
    InteractionStats,
    StreamingInteractionStats,
    compute_interaction_stats,
    compute_interaction_stats_streaming,
    k_core_filter,
    print_streaming_stats_report,
    segment_users,
)
from .leakage_check import (
    LeakageError,
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
)
from .mapping import apply_id_mapping, build_id_mappings, load_mappings, save_mappings
from .metadata_eda import MetadataStats, compute_metadata_stats

__all__ = [
    "InteractionStats",
    "LeakageError",
    "MetadataStats",
    "StreamingInteractionStats",
    "apply_id_mapping",
    "build_id_mappings",
    "check_no_duplicate_across_splits",
    "check_profile_snapshot",
    "check_split_temporal_order",
    "compute_interaction_stats",
    "compute_interaction_stats_streaming",
    "compute_metadata_stats",
    "k_core_filter",
    "load_mappings",
    "print_streaming_stats_report",
    "save_mappings",
    "segment_users",
]
