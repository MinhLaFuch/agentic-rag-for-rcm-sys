"""Exploratory-data-analysis helpers for interaction metadata and splits."""

from .eda import (
    InteractionStats,
    StreamingInteractionStats,
    compute_interaction_stats,
    compute_interaction_stats_streaming,
    print_streaming_stats_report,
)

from .mapping import apply_id_mapping, build_id_mappings, load_mappings, save_mappings
from .metadata_eda import MetadataStats, compute_metadata_stats
from .segment_user import segment_users

__all__ = [
    "InteractionStats",
    "MetadataStats",
    "StreamingInteractionStats",
    "apply_id_mapping",
    "build_id_mappings",
    "compute_interaction_stats",
    "compute_interaction_stats_streaming",
    "compute_metadata_stats",
    "load_mappings",
    "print_streaming_stats_report",
    "save_mappings",
    "segment_user"
]
