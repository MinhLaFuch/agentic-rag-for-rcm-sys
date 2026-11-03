"""Read train-core pairs and translate local indices by canonical IDs."""
import json
import numpy as np
import pandas as pd
from ...data.mapping import load_mappings


def core_inputs(paths, user2id, item2id):
    manifest = paths.splits_dir / "stage_3.manifest.json"
    if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")).get("flags", {}).get("data_protocol") != "temporal_train_core":
        return None
    users, items = load_mappings(paths.mapped_dir / "fit_core")
    pairs = pd.read_parquet(paths.splits_dir / "train_core.parquet", columns=["user_idx", "item_idx"])
    # Translate by canonical IDs, never by coincident numeric positions.
    user_indices = np.empty(len(users), dtype=np.int64)
    item_indices = np.empty(len(items), dtype=np.int64)
    for key, index in users.items():
        user_indices[index] = user2id[key]
    for key, index in items.items():
        item_indices[index] = item2id[key]
    return pairs, users, items, user_indices, item_indices


