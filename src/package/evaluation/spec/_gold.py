"""Gold-spec converter: AgentRequest -> Spec (offline ground truth, no LLM).

Coverage is deliberately limited to request kinds that carry structured fields.
Which gold fields are CLEAN vs HELD-OUT-DERIVED (leaky) — see docs/investigations/distill_phase05_1/D_REPORT.md C.1/C.4:

| kind        | spec fields filled                          | held-out-derived? |
|-------------|---------------------------------------------|-------------------|
| similar     | seed_item_id (+ inferred category of seed)  | NO — seed is last fit item (honest) |
| cold_text   | category_leaf/coarse                        | YES (ORACLE) — category = deepest cat of held-out |
| constrained | price_max, category_*                       | YES (ORACLE) — both built from held-out item; NOTE: price masked at runtime, dead slot |
| exclusion   | exclusions.item_ids/category_labels         | YES (ORACLE) — exclude_item = held_out[0] |
| personalized| kind only (partial)                         | n/a — no spec fields exist by design |
| ambiguous / unanswerable / descriptive / unknown | kind only (partial)   | descriptive text itself is held-out-derived, but no structured spec slots |

Kinds without structured fields return a PARTIAL Spec: ``kind`` is set, every other slot
stays None/empty — the missing parts are explicit, not guessed. ``language`` stays
``"unknown"`` (request templates are VI but detection is the extractor's job, not gold's).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from package.evaluation.requests._dataclass import AgentRequest
from package.evaluation.spec._schema import (
    COARSE_DEPTH,
    COARSE_MIN_ITEMS,
    CategorySlot,
    Exclusions,
    Spec,
    SpecKind,
    coarse_label,
    coarse_of,
)

if TYPE_CHECKING:  # avoid a hard corpus import cycle at module load; ItemCorpus is only used via .select
    from package.corpus import ItemCorpus


def _category_sequence(corpus: "ItemCorpus", item_id: str) -> list[str]:
    """All category labels of ``item_id`` in root->leaf order (rowid order).

    Mirrors ``evaluation.requests._helper._deepest_category`` (which returns only the
    last row); here we keep the full sequence so ``coarse_of`` can pick ancestors.
    """
    rows, _ = corpus.select(
        "SELECT category FROM item_categories WHERE item_id = ? ORDER BY rowid",
        (item_id,),
        max_rows=64,
    )
    return [r["category"] for r in rows]


def _label_counts(corpus: "ItemCorpus", labels: list[str]) -> dict[str, int]:
    """label -> number of items carrying it (for the leaf-up coarse rule, workstream C)."""
    if not labels:
        return {}
    marks = ",".join("?" * len(labels))
    rows, _ = corpus.select(
        f"SELECT category, COUNT(*) AS n FROM item_categories WHERE category IN ({marks}) GROUP BY category",
        list(labels),
        max_rows=len(labels),
    )
    return {r["category"]: int(r["n"]) for r in rows}


def _main_category(corpus: "ItemCorpus", item_id: str) -> str | None:
    """``items.main_category`` fallback for items with no ``item_categories`` rows.

    ~8.7% of the catalog is uncategorized (C_REPORT); ``main_category`` covers
    92-97.5% of items and is the agreed coarse fallback (user decision, phase05_1).
    """
    rows, _ = corpus.select(
        "SELECT main_category FROM items WHERE item_id = ?", (item_id,), max_rows=1
    )
    return rows[0]["main_category"] if rows else None


def spec_from_request(
    request: AgentRequest,
    *,
    corpus: "ItemCorpus | None" = None,
    taxonomy: Collection[str] | None = None,
    coarse_depth: int | None = None,
) -> Spec:
    """Build the gold Spec for an AgentRequest.

    Args:
        request: eval request (structured fields are the gold source).
        corpus: optional ItemCorpus — only used for ``similar`` to attach the seed item's
            inferred category slots. Without it the spec is still valid but leaner.
        taxonomy: optional injectable label set; when given, the result is checked via
            ``Spec.validate_taxonomy`` (unknown labels raise — surfaces gold-data bugs).
        coarse_depth: REQUIRED-by-``coarse_of`` semantics; defaults to the module-level
            ``COARSE_DEPTH`` constant which is ``None`` until workstream C finalizes it.
            When both are None the coarse slot is simply left unfilled.

    Returns:
        Spec — partial (kind-only) for kinds without structured fields.
    """
    try:
        kind = SpecKind(request.kind)
    except ValueError:
        kind = SpecKind.UNKNOWN

    depth = coarse_depth if coarse_depth is not None else COARSE_DEPTH
    # NOTE: Spec's kind-conditional validator runs at construction, so all slots are
    # collected first and the model is built exactly once at the end.
    fields: dict = {"kind": kind}

    if kind is SpecKind.SIMILAR:
        fields["seed_item_id"] = request.seed_item_id
        if corpus is not None and request.seed_item_id:
            seq = _category_sequence(corpus, request.seed_item_id)
            if seq:
                # "Similar to X" implies same-category is a SOFT, INFERRED hint —
                # the user never states a category.
                fields["category_leaf"] = CategorySlot(value=seq[-1], strength="soft", provenance="inferred")
            coarse_value: str | None = None
            if seq:
                if depth is not None:
                    # explicit fixed-depth request wins (fallback semantics per C_REPORT)
                    coarse_value = coarse_of(seq, depth)
                elif COARSE_MIN_ITEMS is not None:
                    # workstream C's recommended leaf-up frequency threshold (N=1,000)
                    coarse_value = coarse_label(seq, _label_counts(corpus, seq), COARSE_MIN_ITEMS)
            if not coarse_value:
                # uncategorized item (~8.7% of catalog) or all labels below the
                # threshold -> agreed fallback: items.main_category (C_REPORT §5).
                coarse_value = _main_category(corpus, request.seed_item_id)
            if coarse_value:
                fields["category_coarse"] = CategorySlot(
                    value=coarse_value, strength="soft", provenance="inferred"
                )

    elif kind is SpecKind.COLD_TEXT:
        # ORACLE/leaky: request.category is the deepest category of a held-out item,
        # but it IS stated verbatim in the request text -> provenance="explicit".
        fields["oracle"] = True
        if request.category:
            fields["category_leaf"] = CategorySlot(value=request.category, strength="hard", provenance="explicit")

    elif kind is SpecKind.CONSTRAINED:
        # ORACLE/leaky: price_max and category were both derived from a held-out item.
        # price_max is a DEAD SLOT under current masking (REPORT C.4) — kept for schema
        # completeness, not for any v1 metric.
        fields["oracle"] = True
        fields["price_max"] = request.price_max
        if request.category:
            fields["category_leaf"] = CategorySlot(value=request.category, strength="hard", provenance="explicit")

    elif kind is SpecKind.EXCLUSION:
        # ORACLE/leaky: excluded_item_ids[0] is held_out[0] and excluded_categories its
        # deepest category (build_requests.py:117-126).
        fields["oracle"] = True
        fields["exclusions"] = Exclusions(
            item_ids=list(request.excluded_item_ids),
            category_labels=list(request.excluded_categories),
        )

    # personalized / ambiguous / unanswerable / descriptive / unknown:
    # no structured spec fields exist on AgentRequest -> return the partial kind-only Spec.

    spec = Spec(**fields)
    if taxonomy is not None:
        spec.validate_taxonomy(taxonomy)
    return spec
