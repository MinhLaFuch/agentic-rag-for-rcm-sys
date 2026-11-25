"""Unit tests for Phase-3 extractor scoring (pure, offline)."""

from __future__ import annotations

from package.evaluation.spec import (
    category_match_level,
    score_extraction,
    score_exclusion_slot,
)

ANC = {
    "Toys & Games": frozenset(),
    "Baby Products": frozenset({"Toys & Games"}),
    "Baby Floats": frozenset({"Toys & Games", "Baby Products"}),
    "Pools & Water Toys": frozenset({"Toys & Games", "Baby Products"}),
    "Electronics": frozenset(),
}

GOLD_CT = {
    "kind": "cold_text",
    "category_leaf": {"value": "Baby Floats"},
    "category_coarse": None,
    "price_max": None,
    "min_rating": None,
    "exclusions": {"item_ids": [], "category_labels": []},
    "seed_item_id": None,
}

GOLD_EX = {
    "kind": "exclusion",
    "category_leaf": None,
    "category_coarse": None,
    "price_max": None,
    "min_rating": None,
    "exclusions": {"item_ids": ["E::B1"], "category_labels": ["Swings"]},
    "seed_item_id": None,
}

GOLD_SIM = {
    "kind": "similar",
    "category_leaf": {"value": "DSLR Cameras"},
    "category_coarse": {"value": "Camera & Photo"},
    "price_max": None,
    "min_rating": None,
    "exclusions": {"item_ids": [], "category_labels": []},
    "seed_item_id": "E::B2",
}


# ------------------------------------------------------- category match -- #


def test_category_match_levels():
    assert category_match_level("Baby Floats", "Baby Floats", ANC) == 1.0
    # ancestor of gold
    assert category_match_level("Baby Products", "Baby Floats", ANC) == 0.5
    # descendant of gold
    assert category_match_level("Baby Floats", "Baby Products", ANC) == 0.5
    # sibling under shared ancestor
    assert category_match_level("Pools & Water Toys", "Baby Floats", ANC) == 0.5
    # unrelated
    assert category_match_level("Electronics", "Baby Floats", ANC) == 0.0
    assert category_match_level(None, "Baby Floats", ANC) == 0.0
    assert category_match_level("Baby Floats", None, ANC) == 0.0


# ------------------------------------------------------------ score_extraction -- #


def test_cold_text_exact_category_full_marks():
    pred = {"kind": "cold_text", "category_leaf": "Baby Floats",
            "language": "vi", "exclusions": {"item_ids": [], "category_labels": []}}
    m = score_extraction(GOLD_CT, {"variant": "original"}, pred, label_ancestors=ANC)
    assert m["kind_acc"] == 1.0
    assert m["cat_f1"] == 1.0 and m["cat_exact"] == 1.0
    assert m["struct_ok"] == 1.0
    assert m["language_acc"] == 1.0  # original -> vi


def test_cold_text_wrong_kind_and_category():
    pred = {"kind": "similar", "category_leaf": "Electronics", "language": "en"}
    m = score_extraction(GOLD_CT, {"variant": "en"}, pred, label_ancestors=ANC)
    assert m["kind_acc"] == 0.0
    assert m["cat_f1"] == 0.0 and m["cat_exact"] == 0.0
    assert m["language_acc"] == 1.0  # en variant -> en


def test_exclusion_set_f1():
    pred = {"kind": "exclusion", "language": "vi",
            "exclusions": {"item_ids": ["E::B1"], "category_labels": ["Wrong"]}}
    m = score_extraction(GOLD_EX, {"variant": "original"}, pred)
    # ids tp=1; cats: pred 'Wrong' fp=1, gold 'Swings' fn=1 -> tp=1 fp=1 fn=1
    assert m["excl_f1"] > 0 and m["excl_f1"] < 1
    perfect = {"kind": "exclusion", "language": "vi",
               "exclusions": {"item_ids": ["E::B1"], "category_labels": ["Swings"]}}
    m2 = score_extraction(GOLD_EX, {"variant": "original"}, perfect)
    assert m2["excl_f1"] == 1.0


def test_similar_seed_and_coarse_credit():
    # pred gives coarse-level label matching gold coarse -> related credit via leaf slot?
    pred = {"kind": "similar", "category_leaf": "Camera & Photo",
            "seed_item_id": "E::B2", "language": "vi"}
    m = score_extraction(GOLD_SIM, {"variant": "original"}, pred, label_ancestors=ANC)
    assert m["kind_acc"] == 1.0
    assert m["seed_item_id_f1"] == 1.0
    # 'Camera & Photo' vs gold coarse 'Camera & Photo' exact via p_leaf vs gold_coarse path
    assert m["cat_f1"] == 1.0


def test_empty_pred_all_zeros_but_scalars():
    m = score_extraction(GOLD_CT, {"variant": "original"}, None)
    assert m["struct_ok"] == 0.0
    assert m["kind_acc"] == 0.0
    assert m["cat_f1"] == 0.0
    assert all(isinstance(v, float) for v in m.values())


def test_exclusion_slot_standalone():
    out = score_exclusion_slot(GOLD_EX["exclusions"] and GOLD_EX, {"exclusions": {"item_ids": [], "category_labels": []}})
    assert out["excl_recall"] == 0.0
    # both empty -> abstention correct
    g_empty = dict(GOLD_EX); g_empty["exclusions"] = {"item_ids": [], "category_labels": []}
    out2 = score_exclusion_slot(g_empty, {"exclusions": {"item_ids": [], "category_labels": []}})
    assert out2["excl_f1"] == 1.0
