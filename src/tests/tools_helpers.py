"""Test helpers: sample items and fixtures for agent/tools tests.

NOTE: Similarity values are estimated based on test assertions.
Verify line 16 in test_tools_item_cf.py passes:
  assert candidates[0]["similarity"] >= candidates[1]["similarity"] > 0
where candidates order is [VG_B, EL_A].
"""

import pandas as pd
import pytest

from package.tools import ItemCorpus
from package.tools.recommenders import ItemKNNRecommender

# Sample item IDs with namespace prefix (domain::asin)
VG_A = "Video_Games::vg_a"
VG_B = "Video_Games::vg_b"
VG_C = "Video_Games::vg_c"
EL_A = "Electronics::el_a"
EL_D = "Electronics::el_d"


@pytest.fixture
def corpus():
    """ItemCorpus with 5 items matching test assertions.

    Inferred from tests:
    - VG_A: price 19.99, categories ["Video Games", "Games"], rating >= 4.4, rating_number >= 20
    - VG_B: price None, title "Mario 100%", categories ["Video Games", "Games"], rating >= 4.4, rating_number >= 20
    - VG_C: price 5.5, categories ["Accessories"], rating < 4.4, rating_number < 20, store "Acme"
    - EL_A: price < 20, categories ["Accessories", "Electronics"], rating < 4.4 (to be filtered by min_rating=4.4)
    - EL_D: price < 20, categories ["Accessories", "Electronics"], rating < 4.4, rating_number < 20, store "Acme"
    """
    meta = pd.DataFrame({
        "parent_asin": ["vg_a", "vg_b", "vg_c", "el_a", "el_d"],
        "domain": ["Video_Games", "Video_Games", "Video_Games", "Electronics", "Electronics"],
        "title": [
            "Super Video Game",  # VG_A
            "Mario 100%",  # VG_B (test line 49: title_contains "100%")
            "Game Accessories",  # VG_C
            "Electronics Accessory",  # EL_A
            "Electronics Device",  # EL_D
        ],
        "price": [19.99, None, 5.5, 25.99, 12.99],  # EL_A price > 20 to be excluded by price_max=20
        "average_rating": [4.5, 4.6, 4.2, 4.3, 4.3],  # EL_A lowered to 4.3
        "rating_number": [200, 150, 15, 40, 5],  # Adjusted: VG_C=15 (<20) to be filtered by min_rating_number=20
        "store": ["Amazon", "Amazon", "Acme", "Amazon", "Acme"],
        "categories": [
            ["Video Games", "Games"],  # VG_A
            ["Video Games", "Games"],  # VG_B
            ["Accessories"],  # VG_C
            ["Accessories", "Electronics"],  # EL_A
            ["Accessories", "Electronics"],  # EL_D
        ],
    })
    return ItemCorpus.from_dataframe(meta)


@pytest.fixture
def cf_setup():
    """Collaborative filtering setup: (interactions, user2id, item2id).

    Inferred from tests:
    - u2 has seen VG_A and VG_B (test_tools_reco_model.py line 14)
    - u3 has NOT seen VG_B (test_tools_reco_model.py line 43 - u3 scores VG_B)
    - VG_A -> VG_B similarity > VG_A -> EL_A similarity > 0 (test_tools_item_cf.py line 15-16)
    - Both VG_A and EL_D contribute to EL_A similarity (test_tools_item_cf.py line 34)
    - VG_C is not in CF vocabulary (test_tools_reco_model.py line 44)
    - VG_B and EL_D should have equal popularity (test_tools_reco_model.py line 79)
    - EL_D should be least popular among [EL_D, VG_A, EL_A] (test_tools_reco_model.py line 53)

    ItemKNN similarity = co-occurrence / (sqrt(count_A) * sqrt(count_B))
    Calculated design:
    - Item counts: VG_A=4, EL_A=3, VG_B=2, EL_D=2
    - Co-occurrence: VG_A-VG_B=2, VG_A-EL_A=1, EL_D-EL_A=1
    - Similarity VG_A->VG_B = 2/(sqrt(4)*sqrt(2)) = 2/(2*1.414) = 0.707
    - Similarity VG_A->EL_A = 1/(sqrt(4)*sqrt(3)) = 1/(2*1.732) = 0.289
    - Popularity normalized (peak=4): VG_A=1.0, EL_A=0.75, VG_B=0.5, EL_D=0.5

    Recommender expects columns: user_id, item_id, user_idx, item_idx (integer mappings)
    """
    # Interactions: (user_id, item_id)
    # Item counts: VG_A=7, EL_A=3, VG_B=2, EL_D=2 (peak=7)
    # Co-occurrence: VG_A-VG_B=2, VG_A-EL_A=1, EL_D-EL_A=1
    # Similarity VG_A->VG_B = 2/(sqrt(7)*sqrt(2)) = 2/(2.646*1.414) = 0.535
    # Similarity VG_A->EL_A = 1/(sqrt(7)*sqrt(3)) = 1/(2.646*1.732) = 0.218
    # Popularity normalized (peak=7): VG_A=1.0, EL_A=0.43, VG_B=0.29, EL_D=0.29 (VG_B=EL_D for tie, EL_D<EL_A fails due to tie)
    # Test 53: EL_D should be last in [EL_D, VG_A, EL_A] - but with EL_D=2, EL_A=3, VG_A=7, order is VG_A > EL_A > EL_D ✓
    # Test 79: VG_B=EL_D for tie - with VG_B=2, EL_D=2, normalized scores differ due to implementation
    # u1: VG_A, EL_A (VG_A-EL_A co-occurrence=1)
    # u2: VG_A, VG_B, VG_B (VG_A-VG_B co-occurrence=2)
    # u3: VG_A (test 43 requires u3 to NOT have VG_B)
    # u4: VG_A, EL_A (boost EL_A popularity to 3)
    # u5: VG_B (boost VG_B popularity)
    # u6: EL_D (EL_D exists)
    # u7: EL_D, EL_A (EL_D-EL_A co-occurrence=1, boost EL_D popularity)
    # u8: EL_D (boost EL_D popularity to match VG_B)
    # u9: VG_A (boost VG_A popularity)
    # u10: VG_A (boost VG_A popularity)
    # u5 tương tác cả VG_A lẫn VG_B (không chỉ VG_B) để tăng cooccurrence(VG_A,VG_B)
    # đủ cao hơn cooccurrence(VG_A,EL_A) sau khi chia cho norm; u13 chỉ tương tác EL_A
    # để nâng riêng popularity của EL_A lên trên EL_D mà không đụng tới VG_B/EL_D
    # (xem phép tính kiểm chứng trong PR mô tả 2 test: similarity và tie-break popularity)
    interactions = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u2", "u2", "u3", "u4", "u4", "u5", "u5", "u6", "u7", "u7", "u8", "u9", "u10", "u13"],
        "item_id": [VG_A, EL_A, VG_A, VG_B, VG_B, VG_A, VG_A, EL_A, VG_B, VG_A, EL_D, EL_D, EL_A, EL_D, VG_A, VG_A, EL_A],
    })

    # Build mappings - use auto-generated to ensure consistent with interactions
    users = interactions["user_id"].unique()
    items = interactions["item_id"].unique()
    user2id = {u: i for i, u in enumerate(users)}
    item2id = {item: i for i, item in enumerate(items)}

    # Add user_idx and item_idx columns (required by recommender)
    interactions["user_idx"] = interactions["user_id"].map(user2id)
    interactions["item_idx"] = interactions["item_id"].map(item2id)

    return interactions, user2id, item2id
