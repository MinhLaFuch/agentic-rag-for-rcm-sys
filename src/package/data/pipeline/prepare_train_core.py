"""Build the CF fit subset exclusively from the chronological training partition."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..filter import k_core_filter


@dataclass(frozen=True)
class _TrainCoreResult:
    core: pd.DataFrame
    user2id: dict[str, int]
    item2id: dict[str, int]
    users_before: int
    items_before: int


def prepare_train_core(
    train: pd.DataFrame, min_user_interactions: int, min_item_interactions: int
) -> _TrainCoreResult:
    """Filter only train interactions and create deterministic fit-only indices.

    Validation/test data is deliberately not accepted by this API. ``user_idx`` and
    ``item_idx`` are local to the fit core and must not be used as evaluation IDs.
    """
    required = {"user_id", "parent_asin", "timestamp"}
    missing = required - set(train.columns)
    if missing:
        raise ValueError(f"train is missing required columns: {sorted(missing)}")
    if train.empty:
        raise ValueError("train must not be empty")
    fit_core = k_core_filter(
        train,
        min_user_interactions=int(min_user_interactions),
        min_item_interactions=int(min_item_interactions),
    ).copy()
    users = sorted(fit_core["user_id"].astype(str).unique().tolist())
    items = sorted(fit_core["parent_asin"].astype(str).unique().tolist())
    user2id = {value: index for index, value in enumerate(users)}
    item2id = {value: index for index, value in enumerate(items)}
    fit_core["user_idx"] = fit_core["user_id"].astype(str).map(user2id).astype("int64")
    fit_core["item_idx"] = fit_core["parent_asin"].astype(str).map(item2id).astype("int64")
    return _TrainCoreResult(
        core=fit_core.reset_index(drop=True),
        user2id=user2id,
        item2id=item2id,
        users_before=int(train["user_id"].nunique()),
        items_before=int(train["parent_asin"].nunique()),
    )
