"""Build test cases for the memory correctness benchmark."""

from __future__ import annotations

from ._dataset_common import SPECS
from .fixtures.create_test_interactions import create_test_interactions
from .fixtures.create_test_mappings import create_test_mappings
from .fixtures.create_test_meta import create_test_meta
from .get_interactions_without_rating import get_interactions_without_rating
from .compute_memory_oracle import compute_memory_oracle
from .leakage_probe import leakage_probe


def build_cases() -> list[dict]:
    inter = create_test_interactions()
    user2id, item2id, _ = create_test_mappings(inter)
    meta = create_test_meta()
    cases = []
    for cid, uid, top_n, as_of, mode, tags, desc, difficulty, tier in SPECS:
        inp = {"user_id": uid, "top_n_categories": top_n}
        if as_of is not None:
            inp["as_of_timestamp"] = as_of
            inp["snapshot_mode"] = mode
        if mode == "untruncated" and "negative" in tags:
            expected = {"expect_error": "LeakageError"}
        else:
            # For u_no_rating, use interactions without rating column
            if uid == "u_no_rating":
                inter_for_case = get_interactions_without_rating(inter, uid)
            else:
                inter_for_case = inter

            # Use default love/hate thresholds matching memory.yaml
            expected = compute_memory_oracle(
                inter_for_case, uid, user2id, item2id, meta,
                top_n_categories=top_n,
                as_of_timestamp=as_of,
                love_min_rating=4,
                hate_max_rating=2,
                top_n_loved_items=10,
                top_n_hated_items=10
            )
            if as_of is not None:
                expected["leakage_probe"] = leakage_probe(
                    inter_for_case, uid, user2id, item2id, as_of, expected["n_interactions"])
        case_meta = {"description": desc, "difficulty": difficulty, "tier": tier}
        if mode == "tool_side_asof":
            # Isolation test for the execute()-level ts<=as_of filter: the
            # constructor guard is bypassed on purpose, so this is NOT a
            # production path — it exists because that filter is otherwise
            # unreachable (evaluator pretruncates + guard rejects future rows).
            case_meta["isolation"] = "tool_side_filter"
            case_meta["production_path"] = False
        cases.append({"case_id": cid, "input": inp, "expected": expected,
                      "tags": ["correctness", *tags], "metadata": case_meta})
    return cases