import pandas as pd
from .leakage_error import LeakageError

def check_profile_snapshot(
    as_of_timestamp: int, source_interactions: pd.DataFrame
) -> None:
    
    future_rows = source_interactions[
        source_interactions["timestamp"] > as_of_timestamp
    ]
    if len(future_rows) > 0:
        raise LeakageError(
            f"Profile snapshot leakage at t={as_of_timestamp}: "
            f"{len(future_rows)} interaction(s) with timestamp in the future "
            f"(max found: {future_rows['timestamp'].max()})"
        )