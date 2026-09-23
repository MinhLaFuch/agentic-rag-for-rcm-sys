import pandas as pd
from .leakage_error import LeakageError


def check_split_temporal_order(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame
) -> None:
    """
    Verify: max(train.timestamp) <= min(validation.timestamp)
        và  max(validation.timestamp) <= min(test.timestamp)

    Raise LeakageError với thông tin cụ thể (không chỉ True/False) nếu
    vi phạm, để dễ debug.
    """
    if len(train) == 0 or len(validation) == 0 or len(test) == 0:
        raise ValueError(
            "One of train/validation/test is empty — cannot verify temporal "
            "order meaningfully. Check split ratios or input data size."
        )

    train_max = train["timestamp"].max()
    val_min = validation["timestamp"].min()
    val_max = validation["timestamp"].max()
    test_min = test["timestamp"].min()

    if train_max > val_min:
        raise LeakageError(
            f"Temporal leakage: train max timestamp ({train_max}) > "
            f"validation min timestamp ({val_min})"
        )
    if val_max > test_min:
        raise LeakageError(
            f"Temporal leakage: validation max timestamp ({val_max}) > "
            f"test min timestamp ({test_min})"
        )