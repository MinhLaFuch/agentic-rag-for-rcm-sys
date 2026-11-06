"""Reporting package."""

from ._generator import (
    generate_markdown_report,
    generate_csv_export,
    generate_failure_report,
    generate_comparison_report,
)

from ._visualizations import (
    generate_layer_comparison_chart,
    generate_request_kind_heatmap,
    generate_retrieval_funnel_chart,
    generate_latency_distribution_chart,
    generate_multi_turn_performance_chart,
    generate_all_charts,
)

__all__ = [
    "generate_markdown_report",
    "generate_csv_export",
    "generate_failure_report",
    "generate_comparison_report",
    "generate_layer_comparison_chart",
    "generate_request_kind_heatmap",
    "generate_retrieval_funnel_chart",
    "generate_latency_distribution_chart",
    "generate_multi_turn_performance_chart",
    "generate_all_charts",
]
