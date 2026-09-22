"""Data processing and EDA utilities."""

from data.preprocess import assign_idx, clean_interactions, compute_temporal_cutoffs, keep_first_filter, leave_one_out_split, low_rating_filter, write_id_maps, write_jsonl, write_products, write_simulator_jsonl, write_splits

from .eda import (
    InteractionStats,
    LeakageError,
    MetadataStats,
    StreamingInteractionStats,
    apply_id_mapping,
    build_id_mappings,
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
    compute_interaction_stats,
    compute_interaction_stats_streaming,
    compute_metadata_stats,
    k_core_filter,
    load_mappings,
    print_streaming_stats_report,
    save_mappings,
    segment_users,
)
from .preprocess import (
    temporal_split,
)

__all__ = [
    "InteractionStats",
    "LeakageError",
    "MetadataStats",
    "StreamingInteractionStats",
    "apply_id_mapping",
    "assign_idx",
    "build_id_mappings",
    "check_no_duplicate_across_splits",
    "check_profile_snapshot",
    "check_split_temporal_order",
    "clean_interactions",
    "compute_interaction_stats",
    "compute_interaction_stats_streaming",
    "compute_metadata_stats",
    "compute_temporal_cutoffs",
    "k_core_filter",
    "keep_first_filter",
    "leave_one_out_split",
    "load_mappings",
    "low_rating_filter",
    "print_streaming_stats_report",
    "save_mappings",
    "segment_users",
    "temporal_split",
    "write_id_maps",
    "write_jsonl",
    "write_products",
    "write_simulator_jsonl",
    "write_splits",
]
