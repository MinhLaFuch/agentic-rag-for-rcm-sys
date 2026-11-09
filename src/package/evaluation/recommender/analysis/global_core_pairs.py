"""Translate compact training pairs into global evaluation indices."""
import pandas as pd


def global_core_pairs(inputs):
    pairs, _, _, users, items = inputs
    return pd.DataFrame({"user_idx": users[pairs.user_idx.to_numpy()],
                         "item_idx": items[pairs.item_idx.to_numpy()]})


