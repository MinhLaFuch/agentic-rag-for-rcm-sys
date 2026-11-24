"""Pure spec_* metric functions for Phase-2 offline backfill (no I/O, no LLM).

Conventions (agreed with user, documented in ``__init__.py``):
- Empty ``recommended`` -> precision metrics = 0.0 and the request STAYS in the
  denominator (40/152 trajectories have empty lists; dropping them inflates).
- Every returned value is a scalar float — ``summarize`` crashes on dict/list.
- Precision denominator is fixed ``k`` (10): "give me 10 products" is scored as
  coverage of the requested list, so a 3-item all-hit list scores 0.3.

Relevant-set semantics per kind (see docs/investigations/distill_phase2/REPORT.md):
- ``cold_text`` / ``similar``: graded precision — fraction of top-k recommended
  items whose resolved ``coarse`` label equals the gold coarse label.
  Strict: uncategorized items NEVER satisfy. Lenient variant
  (``*_lenient``): uncategorized items count as satisfying
  (``uncategorized_ok=True`` semantics).
  Depth sensitivity: ``spec_precision_ancestor@10`` re-matches one level ABOVE
  the coarse label (parent in the rowid label sequence) — measures how much of
  the signal is just "right department".
- ``exclusion``: ``spec_violation_rate`` = 1.0 if ANY recommended item is an
  excluded item_id or carries an excluded category label, else 0.0 (per-request
  binary; the mean over requests is the violation rate). Always report together
  with ``spec_result_coverage`` (1.0 = non-empty list) — an empty list is
  trivially violation-free.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

K = 10


@dataclass(frozen=True)
class ItemSpecView:
    """Per-item taxonomy view for spec matching (built by the caller)."""

    coarse: str | None  # resolved coarse label (leaf-up >=1000, else main_category)
    ancestor: str | None  # label one level above coarse in the rowid sequence
    has_categories: bool  # False = no item_categories rows at all
    categories: frozenset[str] | None = None  # full label set (exclusion checks)


# lookup: item_id -> ItemSpecView | None (None = item not in corpus)
ItemLookup = Callable[[str], "ItemSpecView | None"]


def _view(lookup: ItemLookup, item_id: str) -> ItemSpecView | None:
    try:
        return lookup(item_id)
    except Exception:
        return None


def category_spec_metrics(
    recommended: Sequence[str],
    lookup: ItemLookup,
    gold_coarse: str | None,
    gold_ancestor: str | None = None,
    *,
    k: int = K,
) -> dict[str, float]:
    """Graded spec metrics for category-constrained kinds (cold_text, similar).

    ``gold_coarse``/``gold_ancestor`` come from the gold Spec side (request
    fields + held-out/seed taxonomy — see _gold.py). ``None`` gold -> all
    metrics 0.0 (nothing to satisfy against; request still counted).
    """
    top = list(recommended)[:k]
    strict = lenient = ancestor_hit = 0
    for iid in top:
        view = _view(lookup, iid)
        if gold_coarse is not None and view is not None:
            is_hit = view.has_categories and view.coarse == gold_coarse
            strict += int(is_hit)
            lenient += int(is_hit or not view.has_categories)
            if gold_ancestor is not None:
                ancestor_hit += int(
                    view.has_categories and view.ancestor == gold_ancestor
                )
    return {
        "spec_precision@10": strict / k,
        "spec_precision@10_lenient": lenient / k,
        "spec_hit@10": float(strict > 0),
        "spec_precision_ancestor@10": ancestor_hit / k,
        "spec_result_coverage": float(len(recommended) > 0),
        "spec_n_recommended": float(len(top)),
    }


def exclusion_spec_metrics(
    recommended: Sequence[str],
    lookup: ItemLookup,
    excluded_item_ids: Sequence[str],
    excluded_categories: Sequence[str],
    *,
    k: int = K,
) -> dict[str, float]:
    """Violation metrics for the exclusion kind.

    A recommended item violates if it is literally an excluded item_id OR its
    ``item_categories`` label set intersects ``excluded_categories``
    (``build_requests.py:117-126`` — gold is ORACLE/held-out-derived).
    """
    excluded_ids = set(excluded_item_ids)
    excluded_cats = set(excluded_categories)
    violation = False
    for iid in list(recommended)[:k]:
        if iid in excluded_ids:
            violation = True
            break
        view = _view(lookup, iid)
        if view is not None and view.categories is not None:
            if view.categories & excluded_cats:
                violation = True
                break
    return {
        "spec_violation_rate": float(violation),
        "spec_result_coverage": float(len(recommended) > 0),
        "spec_n_recommended": float(len(list(recommended)[:k])),
    }


def aggregate_spec_metrics(rows: Sequence[dict[str, float]]) -> dict[str, float]:
    """Mean of every scalar metric column; empty input -> {} (caller reports n=0)."""
    if not rows:
        return {}
    keys = rows[0].keys()
    return {key: sum(r[key] for r in rows) / len(rows) for key in keys}


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 42,
) -> dict[str, float]:
    """Paired bootstrap CI for mean(a) - mean(b) over aligned requests.

    Returns point estimate + 2.5/97.5 percentiles. Deterministic via ``seed``.
    """
    import random

    if len(a) != len(b) or not a:
        raise ValueError("paired_bootstrap_diff needs equal-length non-empty inputs")
    diffs = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    n = len(diffs)
    stats = []
    for _ in range(n_boot):
        stats.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    stats.sort()
    return {
        "diff": sum(diffs) / n,
        "ci_low": stats[int(0.025 * n_boot)],
        "ci_high": stats[int(0.975 * n_boot) - 1],
        "n": float(n),
    }
