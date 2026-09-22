import pandas as pd
import pytest

from data.preprocess.temporal_split import compute_temporal_cutoffs, temporal_split


@pytest.fixture
def synthetic_interactions():
    # 10 interaction, timestamp 100..1000 (đều đặn), để tính quantile dễ kiểm tra
    return pd.DataFrame(
        {
            "user_id": [f"u{i}" for i in range(10)],
            "parent_asin": [f"i{i}" for i in range(10)],
            "timestamp": list(range(100, 1100, 100)),  # 100,200,...,1000
        }
    )


def test_compute_temporal_cutoffs_respects_ratios(synthetic_interactions):
    cutoff_1, cutoff_2 = compute_temporal_cutoffs(
        synthetic_interactions, train_ratio=0.8, validation_ratio=0.1, test_ratio=0.1
    )
    # 8/10 -> cutoff_1 tại index 7 (timestamp 800); 9/10 -> cutoff_2 tại index 8 (900)
    assert cutoff_1 == 800
    assert cutoff_2 == 900


def test_compute_temporal_cutoffs_invalid_ratios_raises(synthetic_interactions):
    with pytest.raises(ValueError):
        compute_temporal_cutoffs(
            synthetic_interactions, train_ratio=0.5, validation_ratio=0.3, test_ratio=0.3
        )


def test_compute_temporal_cutoffs_empty_dataframe_raises():
    empty_df = pd.DataFrame({"timestamp": []})
    with pytest.raises(ValueError):
        compute_temporal_cutoffs(empty_df)


def test_temporal_split_produces_disjoint_ordered_sets(synthetic_interactions):
    cutoff_1, cutoff_2 = compute_temporal_cutoffs(synthetic_interactions)
    train, val, test = temporal_split(synthetic_interactions, cutoff_1, cutoff_2)

    assert len(train) + len(val) + len(test) == len(synthetic_interactions)
    assert train["timestamp"].max() <= cutoff_1
    assert val["timestamp"].min() > cutoff_1
    assert val["timestamp"].max() <= cutoff_2
    assert test["timestamp"].min() > cutoff_2
