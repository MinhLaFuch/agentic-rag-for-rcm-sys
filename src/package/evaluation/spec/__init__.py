"""Spec v1 package: distilled-query contract + gold converter (workstream D).

New module — intentionally NOT re-exported from ``package.evaluation`` yet so existing
imports stay untouched; consumers use ``package.evaluation.spec`` directly.

Metric conventions for Phase 2 spec_* metrics (agreed with user, phase05_1):
- ``spec_precision@k`` = 0 for an EMPTY recommendation list; the request stays in
  the denominator (40/152 trajectories have ``recommended == []`` due to tool
  errors, ~half of them ``exclusion`` — dropping them would inflate scores).
- Violation/exclusion rates MUST be reported together with result coverage
  (fraction of requests with a non-empty list), since an empty list trivially
  has zero violations.
- Every spec_* metric value in scored rows MUST be a scalar (float/int); dicts
  or lists crash ``summarize``.
"""

from package.evaluation.spec._extract_metrics import (
    category_match_level,
    score_extraction,
    score_exclusion_slot,
)
from package.evaluation.spec._gold import spec_from_request
from package.evaluation.spec._metrics import (
    ItemSpecView,
    aggregate_spec_metrics,
    category_spec_metrics,
    exclusion_spec_metrics,
    paired_bootstrap_diff,
)
from package.evaluation.spec._schema import (
    COARSE_DEPTH,
    COARSE_MIN_ITEMS,
    CategorySlot,
    Exclusions,
    Spec,
    SpecKind,
    coarse_label,
    coarse_of,
    validate_spec,
)

__all__ = [
    "COARSE_DEPTH",
    "COARSE_MIN_ITEMS",
    "CategorySlot",
    "Exclusions",
    "ItemSpecView",
    "Spec",
    "SpecKind",
    "aggregate_spec_metrics",
    "category_match_level",
    "category_spec_metrics",
    "coarse_label",
    "coarse_of",
    "exclusion_spec_metrics",
    "paired_bootstrap_diff",
    "score_extraction",
    "score_exclusion_slot",
    "spec_from_request",
    "validate_spec",
]
