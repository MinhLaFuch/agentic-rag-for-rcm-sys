from __future__ import annotations

import pandas as pd

from package.data import build_first_seen_timestamps


def test_first_seen_is_minimum_over_all_cleaned_rows_and_namespaced(tmp_path):
    path = tmp_path / "cleaned.parquet"
    pd.DataFrame({
        "user_id": ["u1", "u2", "u3"],
        "parent_asin": ["A", "A", "B"],
        "timestamp": [30, 10, 20],
    }).to_parquet(path, index=False)

    first_seen = build_first_seen_timestamps([("Games", path)], batch_size=2)

    assert first_seen == {"Games::A": 10, "Games::B": 20}
