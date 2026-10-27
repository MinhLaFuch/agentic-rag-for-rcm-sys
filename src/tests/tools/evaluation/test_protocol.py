import pandas as pd
import pytest

from package.tools.evaluation.evaluation_protocol import evaluation_protocol
from scripts.evaluation.run_agent_eval import is_resumable


def inputs():
    return dict(eval_on="validation", tag="D",
                fit_df=pd.DataFrame({"user_idx": [0], "item_idx": [0], "timestamp": [1]}),
                target_df=pd.DataFrame({"user_idx": [0], "item_idx": [1], "timestamp": [2]}),
                user2id={"u": 0}, item2id={"a": 0, "b": 1},
                segments={0: "warm", 1: "cold", 2: "warm"},
                sampled={"warm": [0], "cold": [1]},
                metadata_policy={"as_of_timestamp": 2, "name": "historical_static_catalog"})


def test_population_and_sample_and_split_definitions():
    record = evaluation_protocol(**inputs())
    assert record["segment_population_users"] == {"warm": 2, "cold": 1}
    assert record["segment_sample_users"] == {"warm": 1, "cold": 1}
    assert record["item_knn"]["fit_splits"] == ["train"]
    assert "not population-weighted" in record["sampling"]


def test_temporal_overlap_and_wrong_cutoff_rejected():
    context = inputs()
    context["fit_df"]["timestamp"] = 2
    with pytest.raises(ValueError, match="strictly precede"):
        evaluation_protocol(**context)
    context = inputs()
    context["metadata_policy"]["as_of_timestamp"] = 3
    with pytest.raises(ValueError, match="cutoff"):
        evaluation_protocol(**context)


def test_resume_cannot_mix_metadata_policies_or_legacy_records():
    rec = {"request_id": "x", "text": "hello", "agent": "baseline"}
    args = ({"x": "hello"}, ["baseline"], 0)
    assert not is_resumable(rec, *args, protocol_hash="historical")
    rec["evaluation_protocol_hash"] = "snapshot"
    assert not is_resumable(rec, *args, protocol_hash="historical")
    assert is_resumable(rec, *args, protocol_hash="snapshot")
