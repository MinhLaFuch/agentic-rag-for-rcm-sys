"""Query-distillation spec v1: the contract between the (future) extractor and spec-based scoring.

Implements the schema proposed in ``docs/investigations/distill_infra_audit/REPORT.md`` section G,
with two deliberate deviations documented inline:

- ``category_*`` slots hold **exact-match flat labels** (never "a > b > c" path strings) —
  the corpus stores categories as flat labels, one row per (item, level), root -> leaf by rowid.
- ``price_max`` / ``min_rating`` are kept in the schema but are **dead slots under the current
  masking policy** (``metadata_policy: historical_static_catalog`` NULLs price/rating and
  ``constrained`` never ran — REPORT C.4). They are intentionally NOT wired into any metric
  or benchmark in v1.
"""

from __future__ import annotations

import enum
from collections.abc import Collection, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# Workstream C (taxonomy audit, docs/investigations/distill_phase05_1/C_REPORT.md §3) landed:
# it REJECTED a single fixed depth — position-2 labels are extremely fragmented
# (median bucket 3 items) — and recommends a leaf-up frequency threshold instead:
# coarse = deepest label in the item's root->leaf sequence whose corpus item-count
# >= N, with N=1,000 at the granularity/stability knee (609 buckets, 99.99% coverage).
# Fixed-depth ``coarse_of`` is kept as the documented fallback (least-bad k=3 per C).
COARSE_DEPTH: int | None = None  # fixed-depth fallback; unused while COARSE_MIN_ITEMS is set
COARSE_MIN_ITEMS: int | None = 1000  # C_REPORT recommendation; set to None to disable


def coarse_label(
    label_sequence: Sequence[str],
    label_counts: dict[str, int],
    min_count: int = 1000,
) -> str | None:
    """Leaf-up coarse label (workstream C's recommended semantics).

    ``label_sequence``: item's labels in root->leaf order. ``label_counts``: label ->
    number of items carrying it (from ``item_categories``). Returns the DEEPEST label
    whose count >= ``min_count`` — i.e. each item gets its most specific *well-populated*
    ancestor. Returns ``None`` when no label qualifies (caller should fall back to
    ``main_category``/domain — that fallback needs corpus access and lives in _gold).
    """
    for label in reversed([s for s in label_sequence if s]):
        if label_counts.get(label, 0) >= min_count:
            return label
    return None


class SpecKind(str, enum.Enum):
    """Request kinds the spec can describe (mirrors evaluation._schema.KINDS + "unknown")."""

    SIMILAR = "similar"
    PERSONALIZED = "personalized"
    CONSTRAINED = "constrained"
    COLD_TEXT = "cold_text"
    EXCLUSION = "exclusion"
    AMBIGUOUS = "ambiguous"
    UNANSWERABLE = "unanswerable"
    DESCRIPTIVE = "descriptive"
    UNKNOWN = "unknown"


Strength = Literal["hard", "soft"]
Provenance = Literal["explicit", "inferred"]
Language = Literal["vi", "en", "mixed", "unknown"]


class CategorySlot(BaseModel):
    """One category constraint.

    ``value`` is an EXACT-MATCH flat label as stored in ``item_categories.category``
    (e.g. ``"Building Toys"``), NOT a path string — the taxonomy has no path representation
    (REPORT B.2/B.5). Because every item carries all of its ancestor labels as rows,
    a coarse-grained constraint can still be expressed as a single flat label via
    :func:`coarse_of`.
    """

    value: str | None = None
    strength: Strength = "soft"
    provenance: Provenance = "explicit"


class Exclusions(BaseModel):
    """Things the user asked NOT to see.

    ``category_labels`` has no enforcing filter key yet (``categories_exclude`` does not
    exist — REPORT blocker 4); keep the data, enforcement is a later workstream.
    """

    item_ids: list[str] = Field(default_factory=list)
    category_labels: list[str] = Field(default_factory=list)


class Spec(BaseModel):
    """Distilled query spec v1.

    Slot semantics:
    - ``category_leaf``: finest-grained category constraint (exact-match label).
    - ``category_coarse``: coarser ancestor label (see :func:`coarse_of`); used when the
      extractor only commits to a parent level, or for ``uncategorized_ok`` reasoning.
    - ``price_max`` / ``min_rating``: DEAD SLOTS in v1 — retained for schema stability but
      deliberately unused by any metric/benchmark while price/rating are masked
      (REPORT C.4). Do not wire them into scoring yet.
    - ``attributes``: free-form dict, only ever ``provenance="inferred"`` material —
      never treat its contents as user-stated facts.
    - ``uncategorized_ok``: when True (~9% of items have no category rows, REPORT B.4),
      category constraints are soft enough that uncategorized items remain eligible.
    - ``oracle``: additive audit flag (not in the REPORT G sketch) — True when the spec was
      built from held-out targets (mirrors ``AgentRequest.oracle`` / ``ORACLE_KINDS``), i.e.
      the gold is leaky by construction and must not be presented as a realistic query.
    """

    kind: SpecKind
    category_coarse: CategorySlot | None = None
    category_leaf: CategorySlot | None = None
    price_max: float | None = None  # DEAD SLOT v1 — see class docstring
    min_rating: float | None = None  # DEAD SLOT v1 — see class docstring
    exclusions: Exclusions = Field(default_factory=Exclusions)
    seed_item_id: str | None = None
    attributes: dict[str, Any] | None = None
    language: Language = "unknown"
    uncategorized_ok: bool = True
    oracle: bool = False

    @model_validator(mode="after")
    def _kind_rules(self) -> "Spec":
        k = self.kind
        if k is SpecKind.SIMILAR and not self.seed_item_id:
            raise ValueError("kind='similar' requires seed_item_id")
        if k is SpecKind.EXCLUSION and not (
            self.exclusions.item_ids or self.exclusions.category_labels
        ):
            raise ValueError("kind='exclusion' requires at least one excluded item_id or category_label")
        if k is SpecKind.COLD_TEXT and not (
            (self.category_leaf and self.category_leaf.value)
            or (self.category_coarse and self.category_coarse.value)
        ):
            raise ValueError("kind='cold_text' requires a category_leaf or category_coarse value")
        if k is SpecKind.CONSTRAINED and not (
            self.price_max is not None
            or self.min_rating is not None
            or (self.category_leaf and self.category_leaf.value)
            or (self.category_coarse and self.category_coarse.value)
        ):
            # Schema-level rule only: constrained requests carry price_max+category today,
            # but price is masked at runtime so a category-only constrained spec is legal.
            raise ValueError("kind='constrained' requires at least one constraint slot (price_max/min_rating/category_*)")
        # personalized / ambiguous / unanswerable / descriptive / unknown: partial specs
        # are expected — missing parts are expressed as None/empty slots, not errors.
        return self

    def category_labels(self) -> list[str]:
        """All non-None exact-match labels this spec constrains or excludes."""
        out: list[str] = []
        for slot in (self.category_coarse, self.category_leaf):
            if slot and slot.value:
                out.append(slot.value)
        out.extend(self.exclusions.category_labels)
        return out

    def validate_taxonomy(self, taxonomy: Collection[str]) -> None:
        """Check every category label against an injected taxonomy label set.

        ``taxonomy`` is deliberately a plain collection of flat labels (e.g.
        ``ItemCorpus.categories()``) — the model never touches the DB itself, so tests
        and offline callers can pass any set. Raises ``ValueError`` listing unknown labels.
        """
        known = set(taxonomy)
        unknown = sorted({lbl for lbl in self.category_labels() if lbl not in known})
        if unknown:
            raise ValueError(f"spec {self.kind.value!r} references labels absent from taxonomy: {unknown}")


def validate_spec(data: "Spec | dict[str, Any]", taxonomy: Collection[str] | None = None) -> Spec:
    """Parse + validate a spec (e.g. raw extractor JSON) and optionally check the taxonomy.

    ``taxonomy=None`` skips the label-existence check entirely — the check only runs
    when a caller explicitly injects a label set.
    """
    spec = data if isinstance(data, Spec) else Spec.model_validate(data)
    if taxonomy is not None:
        spec.validate_taxonomy(taxonomy)
    return spec


def coarse_of(label_or_sequence: str | Sequence[str], coarse_depth: int) -> str:
    """Map a label (or full root->leaf label sequence) to its coarse ancestor label.

    ``label_or_sequence``:
    - ``Sequence[str]``: the item's category labels in root->leaf order (rowid order of
      ``item_categories``, see ``_gold._category_sequence``).
    - ``str``: a single bare label. Only resolvable when ``coarse_depth == 1`` — a leaf
      label carries no depth information, so truncating it would be a guess.

    ``coarse_depth`` (REQUIRED — no default; pending workstream C): target depth counted
    from the root, 1-indexed. ``coarse_depth=1`` -> root label, ``2`` -> its child, etc.
    If the sequence is shallower than ``coarse_depth`` the deepest available label is
    returned (documented, not silent: callers wanting strictness should compare lengths).

    Returns a single flat label that exact-matches ``item_categories.category`` — items
    carry every ancestor as its own row, so the coarse label needs no path machinery.
    """
    if isinstance(label_or_sequence, str):
        seq = [label_or_sequence]
        bare = True
    else:
        seq = [s for s in label_or_sequence if s]
        bare = False
    if not seq:
        raise ValueError("coarse_of needs at least one non-empty label")
    if coarse_depth < 1:
        raise ValueError(f"coarse_depth must be >= 1, got {coarse_depth}")
    if bare and coarse_depth > 1:
        raise ValueError(
            "a bare label has no depth; pass the item's full label sequence (root->leaf) "
            "or use coarse_depth=1"
        )
    return seq[min(coarse_depth, len(seq)) - 1]
