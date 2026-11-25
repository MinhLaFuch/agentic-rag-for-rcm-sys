"""Unit tests for spec v1 schema/validator, coarse_of, and the gold converter.

Offline only: uses the shared 5-item ``corpus`` fixture (tests/tools_helpers.py via
tests/evaluation/conftest.py) and hand-built AgentRequest objects — no LLM, no DB.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from package.evaluation.requests._dataclass import AgentRequest
from package.evaluation.spec import (
    CategorySlot,
    Exclusions,
    Spec,
    SpecKind,
    coarse_label,
    coarse_of,
    spec_from_request,
    validate_spec,
)
from tests.tools_helpers import EL_A, VG_A, VG_B

TAXONOMY = {"Video Games", "Games", "Accessories", "Electronics"}


def _req(kind: str, **fields) -> AgentRequest:
    return AgentRequest(request_id=f"{kind}-test-0", kind=kind, segment="sparse", text="...", **fields)


# ---------------------------------------------------------------- schema -- #


def test_minimal_partial_spec_is_valid():
    spec = Spec(kind=SpecKind.PERSONALIZED)
    assert spec.kind is SpecKind.PERSONALIZED
    assert spec.category_leaf is None and spec.price_max is None
    assert spec.exclusions.item_ids == [] and spec.exclusions.category_labels == []
    assert spec.uncategorized_ok is True and spec.oracle is False


def test_similar_requires_seed():
    Spec(kind=SpecKind.SIMILAR, seed_item_id="Video_Games::vg_a")  # ok
    with pytest.raises(ValidationError, match="seed_item_id"):
        Spec(kind=SpecKind.SIMILAR)


def test_exclusion_requires_at_least_one():
    with pytest.raises(ValidationError, match="exclusion"):
        Spec(kind=SpecKind.EXCLUSION)
    Spec(kind=SpecKind.EXCLUSION, exclusions=Exclusions(item_ids=["x"]))
    Spec(kind=SpecKind.EXCLUSION, exclusions=Exclusions(category_labels=["Games"]))


def test_cold_text_requires_category():
    Spec(
        kind=SpecKind.COLD_TEXT,
        category_leaf=CategorySlot(value="Games", strength="hard", provenance="explicit"),
    )
    with pytest.raises(ValidationError, match="cold_text"):
        Spec(kind=SpecKind.COLD_TEXT)
    # empty-valued slot does not count
    with pytest.raises(ValidationError, match="cold_text"):
        Spec(kind=SpecKind.COLD_TEXT, category_leaf=CategorySlot(value=None))


def test_constrained_requires_one_constraint_slot():
    with pytest.raises(ValidationError, match="constrained"):
        Spec(kind=SpecKind.CONSTRAINED)
    # category-only is legal even though price is a dead slot under masking
    Spec(kind=SpecKind.CONSTRAINED, category_leaf=CategorySlot(value="Games"))
    Spec(kind=SpecKind.CONSTRAINED, price_max=19.99)  # dead slot still schema-legal


def test_partial_kinds_never_require_fields():
    for kind in ("personalized", "ambiguous", "unanswerable", "descriptive", "unknown"):
        assert Spec(kind=kind).kind.value == kind


def test_kind_enum_rejects_unknown_string():
    # raw strings outside the enum fail at parse time; converter maps them to "unknown"
    with pytest.raises(ValidationError):
        Spec.model_validate({"kind": "not_a_kind"})


def test_language_and_uncategorized_defaults():
    spec = Spec(kind="ambiguous")
    assert spec.language == "unknown"
    assert spec.uncategorized_ok is True
    with pytest.raises(ValidationError):
        Spec(kind="ambiguous", language="fr")


def test_attributes_slot_is_free_form_dict():
    spec = Spec(kind="descriptive", attributes={"color": "red"})
    assert spec.attributes == {"color": "red"}
    assert Spec(kind="descriptive", attributes=None).attributes is None


# ------------------------------------------------------- taxonomy check -- #


def test_validate_taxonomy_pass_and_fail():
    good = Spec(
        kind=SpecKind.COLD_TEXT,
        category_leaf=CategorySlot(value="Games"),
        exclusions=Exclusions(category_labels=["Accessories"]),
    )
    good.validate_taxonomy(TAXONOMY)  # no raise

    bad = Spec(
        kind=SpecKind.COLD_TEXT,
        category_leaf=CategorySlot(value="Nonexistent Category"),
    )
    with pytest.raises(ValueError, match="Nonexistent Category"):
        bad.validate_taxonomy(TAXONOMY)


def test_validate_taxonomy_is_injectable_and_optional():
    spec = Spec(kind=SpecKind.COLD_TEXT, category_leaf=CategorySlot(value="Whatever"))
    spec.validate_taxonomy({"Whatever"})  # any injected set works — no DB access
    # taxonomy=None -> check skipped entirely
    assert validate_spec({"kind": "cold_text", "category_leaf": {"value": "Whatever"}}).kind is SpecKind.COLD_TEXT
    with pytest.raises(ValueError):
        validate_spec(
            {"kind": "cold_text", "category_leaf": {"value": "Whatever"}},
            taxonomy={"Other"},
        )


# -------------------------------------------------------------- coarse_of -- #


def test_coarse_of_sequence_depths():
    seq = ["Video Games", "Console Games", "Action Games"]
    assert coarse_of(seq, 1) == "Video Games"
    assert coarse_of(seq, 2) == "Console Games"
    assert coarse_of(seq, 3) == "Action Games"
    # depth beyond sequence length -> deepest available (documented behaviour)
    assert coarse_of(seq, 9) == "Action Games"


def test_coarse_of_bare_label_rules():
    assert coarse_of("Games", 1) == "Games"
    with pytest.raises(ValueError, match="bare label"):
        coarse_of("Games", 2)
    with pytest.raises(ValueError):
        coarse_of([], 1)
    with pytest.raises(ValueError):
        coarse_of(["A"], 0)


def test_coarse_label_leaf_up_threshold():
    # workstream C semantics: deepest label whose corpus count >= min_count
    seq = ["Video Games", "Console Games", "Action Games"]
    counts = {"Video Games": 5000, "Console Games": 1500, "Action Games": 40}
    assert coarse_label(seq, counts, min_count=1000) == "Console Games"
    assert coarse_label(seq, counts, min_count=40) == "Action Games"  # leaf qualifies at low threshold
    assert coarse_label(seq, {"Video Games": 10}, min_count=1000) is None  # none qualify
    assert coarse_label([], counts) is None


def test_gold_similar_threshold_path_on_tiny_corpus(corpus):
    # no coarse_depth -> C's N=1000 leaf-up rule; the 5-item fixture has all counts < 1000
    # so category_coarse stays empty (main_category fallback is a scoring-time concern)
    req = _req("similar", seed_item_id=VG_A)
    spec = spec_from_request(req, corpus=corpus)
    assert spec.category_leaf.value == "Games"
    assert spec.category_coarse is None


# ------------------------------------------------------------- gold conv. -- #


def test_gold_similar_clean_with_corpus(corpus):
    req = _req("similar", seed_item_id=VG_A, user_id="u1", user_idx=1, targets=[2])
    spec = spec_from_request(req, corpus=corpus, coarse_depth=1)
    assert spec.kind is SpecKind.SIMILAR
    assert spec.seed_item_id == VG_A
    assert spec.oracle is False  # honest kind
    # VG_A categories ["Video Games", "Games"] -> leaf is last row, soft+inferred
    assert spec.category_leaf.value == "Games"
    assert spec.category_leaf.strength == "soft"
    assert spec.category_leaf.provenance == "inferred"
    assert spec.category_coarse.value == "Video Games"


def test_gold_similar_without_corpus_is_partial(corpus):
    req = _req("similar", seed_item_id=VG_B)
    spec = spec_from_request(req)  # no corpus -> seed only, still valid
    assert spec.seed_item_id == VG_B
    assert spec.category_leaf is None


def test_gold_similar_main_category_fallback():
    # uncategorized item (no item_categories rows) -> category_coarse falls back
    # to items.main_category (agreed fallback, C_REPORT §5 / user decision).
    import pandas as pd
    from package.corpus import ItemCorpus

    meta = pd.DataFrame({
        "parent_asin": ["uncat_1"],
        "domain": ["Toys_and_Games"],
        "first_seen_ts": [1],
        "title": ["Uncategorized Thing"],
        "price": [9.99],
        "average_rating": [4.0],
        "rating_number": [10],
        "store": ["Shop"],
        "main_category": ["Toys"],
        "categories": [[]],
    })
    c = ItemCorpus.from_dataframe(meta)
    item_id = "Toys_and_Games::uncat_1"
    req = _req("similar", seed_item_id=item_id)
    spec = spec_from_request(req, corpus=c)
    assert spec.category_leaf is None  # no taxonomy rows at all
    assert spec.category_coarse is not None
    assert spec.category_coarse.value == "Toys"
    assert spec.category_coarse.strength == "soft"
    assert spec.category_coarse.provenance == "inferred"


def test_gold_similar_missing_seed_fails_validation():
    req = _req("similar")  # no seed_item_id
    with pytest.raises(ValidationError):
        spec_from_request(req)


def test_gold_cold_text_oracle(corpus):
    req = _req("cold_text", category="Building Toys", targets=[0])
    spec = spec_from_request(req, taxonomy=TAXONOMY | {"Building Toys"})
    assert spec.oracle is True  # leaky: category came from a held-out item
    assert spec.category_leaf.value == "Building Toys"
    assert spec.category_leaf.strength == "hard"
    assert spec.category_leaf.provenance == "explicit"  # stated verbatim in text
    assert spec.seed_item_id is None and spec.price_max is None


def test_gold_constrained_oracle_dead_price_slot(corpus):
    req = _req("constrained", price_max=24.99, category="Games", targets=[0])
    spec = spec_from_request(req, taxonomy=TAXONOMY)
    assert spec.oracle is True
    assert spec.price_max == 24.99  # kept in schema, DEAD SLOT — not for v1 metrics
    assert spec.category_leaf.value == "Games"


def test_gold_exclusion_oracle(corpus):
    req = _req(
        "exclusion",
        excluded_item_ids=[EL_A],
        excluded_categories=["Electronics"],
        targets=[1],
    )
    spec = spec_from_request(req, taxonomy=TAXONOMY)
    assert spec.oracle is True
    assert spec.exclusions.item_ids == [EL_A]
    assert spec.exclusions.category_labels == ["Electronics"]


def test_gold_exclusion_without_fields_fails():
    req = _req("exclusion", targets=[1])
    with pytest.raises(ValidationError):
        spec_from_request(req)


def test_gold_partial_kinds(corpus):
    for kind in ("personalized", "ambiguous", "unanswerable", "descriptive"):
        req = _req(kind, user_id="u1", user_idx=1, targets=[2])
        spec = spec_from_request(req)
        assert spec.kind.value == kind
        assert spec.oracle is False
        # everything else explicitly empty/None — missing parts are marked, not guessed
        assert spec.category_leaf is None and spec.seed_item_id is None
        assert spec.price_max is None and spec.min_rating is None
        assert spec.exclusions.item_ids == [] and spec.attributes is None
        assert spec.language == "unknown"


def test_gold_unknown_kind_maps_to_unknown():
    req = _req("some_future_kind")
    spec = spec_from_request(req)
    assert spec.kind is SpecKind.UNKNOWN


def test_gold_taxonomy_check_surfaces_bad_labels(corpus):
    req = _req("cold_text", category="Not A Real Category")
    with pytest.raises(ValueError, match="Not A Real Category"):
        spec_from_request(req, taxonomy=TAXONOMY)
