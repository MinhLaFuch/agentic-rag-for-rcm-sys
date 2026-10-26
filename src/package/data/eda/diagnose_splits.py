"""Read-only split diagnostics with explicit event, pair and user denominators.

Validation fit is train; test fit is train+validation. These are catalog-signal
statistics, not a universal Recall@K ceiling or proof of label leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from ._dataclass import SplitDiagnosis


def _pct(mask):
    return float(np.mean(mask) * 100) if len(mask) else 0.0


def _stats(values):
    return {"min": float(values.min()), "median": float(np.median(values)),
            "p90": float(np.quantile(values, .9))} if len(values) else dict.fromkeys(("min", "median", "p90"), 0.0)


def _compute_multi_domain_pct(df):
    return _pct(df.groupby("user_idx", observed=True)["domain"].nunique().to_numpy() > 1) if "domain" in df else 0.0


def diagnose_splits(train, validation, test, user2id=None, item2id=None):
    """Retain explicitly named train-only fields; fit_diagnostics uses runtime fit.

    History is the number of UNIQUE fit items and includes zero-history target
    users, consistent with binary CSR evaluation. Domain statistics use global
    fit history for users with targets in that domain.
    """
    frames = (train, validation, test)
    for name, df in zip(("train", "validation", "test"), frames):
        missing = {"user_idx", "item_idx"} - set(df.columns)
        if missing:
            raise ValueError(f"{name} missing columns: {missing}")
        for col in ("user_idx", "item_idx"):
            v = df[col]
            if len(v) and (v.isna().any() or (v < 0).any() or not np.array_equal(v.to_numpy(), v.to_numpy(dtype=np.int64))):
                raise ValueError(f"{name} {col} must contain non-negative integer IDs")
    stride = max((int(df.item_idx.max()) + 1 for df in frames if len(df)), default=1)
    max_user = max((int(df.user_idx.max()) for df in frames if len(df)), default=0)
    if max_user > (np.iinfo(np.int64).max - (stride - 1)) // stride:
        raise ValueError("IDs too large for safe numeric pair encoding")

    def pairs(df):
        return np.unique(df.user_idx.to_numpy(dtype=np.int64) * stride + df.item_idx.to_numpy(dtype=np.int64))

    train_pairs, val_pairs, test_pairs = (pairs(df) for df in frames)
    test_fit = np.union1d(train_pairs, val_pairs)
    train_items = np.unique(train_pairs % stride)
    train_users = np.unique(train_pairs // stride)

    # Compute fit profiles once; every domain reuses the same global history.
    profiles = {}
    for fit in (train_pairs, test_fit):
        ids, counts = np.unique(fit // stride, return_counts=True)
        profiles[id(fit)] = (pd.Series(counts, index=ids), np.unique(fit % stride))

    def history(fit, users):
        return profiles[id(fit)][0].reindex(users, fill_value=0).to_numpy(dtype=np.int64)

    def report(target, fit):
        target_users = np.unique(target // stride)
        hist = history(fit, target_users)
        warm = np.isin(target % stride, profiles[id(fit)][1])
        positions = np.searchsorted(fit, target)
        repeat = np.zeros(len(target), dtype=bool)
        valid = positions < len(fit)
        repeat[valid] = fit[positions[valid]] == target[valid]
        eligible = warm & ~repeat
        per_user_n = pd.Series(target // stride).value_counts().reindex(target_users, fill_value=0).to_numpy()
        per_user_e = pd.Series(target[eligible] // stride).value_counts().reindex(target_users, fill_value=0).to_numpy()
        return {
            "target_unique_pairs": int(len(target)), "target_users": int(len(target_users)),
            "item_warm_unique_pair_pct": _pct(warm), "repeat_unique_pair_pct": _pct(repeat),
            "novel_item_warm_unique_pair_pct": _pct(eligible),
            "cold_user_pct": _pct(hist == 0), "history_unique_items_including_zero": _stats(hist),
            "catalog_eligible_macro_recall_at_10_upper_bound": float(np.mean(np.minimum(10, per_user_e) / per_user_n)) if len(target_users) else None,
        }

    val_report, test_report = report(val_pairs, train_pairs), report(test_pairs, test_fit)
    result = {}
    for prefix, df in zip(("train", "val", "test"), frames):
        result.update({f"{prefix}_rows": len(df), f"{prefix}_users": int(df.user_idx.nunique()),
                       f"{prefix}_items": int(df.item_idx.nunique()),
                       f"{prefix}_timestamp_min": int(df.timestamp.min()) if "timestamp" in df and len(df) else 0,
                       f"{prefix}_timestamp_max": int(df.timestamp.max()) if "timestamp" in df and len(df) else 0,
                       f"{prefix}_domain_ratios": {str(k): float(v) for k,v in df.domain.value_counts(normalize=True).items()} if "domain" in df else {},
                       f"{prefix}_multi_domain_users_pct": _compute_multi_domain_pct(df)})
    for prefix, df, target, fit_report in (("val", validation, val_pairs, val_report), ("test", test, test_pairs, test_report)):
        result.update({
            f"{prefix}_items_in_train_pct": _pct(np.isin(df.item_idx.unique(), train_items)),
            f"{prefix}_rows_with_train_item_pct": _pct(np.isin(df.item_idx.to_numpy(), train_items)),
            f"{prefix}_users_with_train_history_pct": _pct(np.isin(df.user_idx.unique(), train_users)),
            f"{prefix}_history_len_stats": _stats(history(train_pairs, np.unique(target // stride))),
            f"{prefix}_repeat_pairs_pct": fit_report["repeat_unique_pair_pct"],
            f"{prefix}_reachable_pct": fit_report["novel_item_warm_unique_pair_pct"],
        })
    domain_reports = {}
    for name, df, fit in (("validation", validation, train_pairs), ("test", test, test_fit)):
        domain_reports[name] = {str(d): report(pairs(group), fit) for d, group in df.groupby("domain", observed=True)} if "domain" in df else {}
    return SplitDiagnosis(**result, fit_diagnostics={"validation": val_report, "test": test_report},
                          domain_diagnostics=domain_reports, protocol={
        "version": 2, "fit_splits": {"validation": ["train"], "test": ["train", "validation"]},
        "repeat_and_eligibility_denominator": "unique target user-item pairs (micro)",
        "history": "unique fit items per target user; includes zero",
        "legacy_history_len_stats": "train-only, including zero; see fit_diagnostics for runtime fit",
        "catalog_assumption": "frozen full mapping; item warm means any fit user interacted, not same-user repeat",
        "cohort_selection": "upstream pre-split filtering; future-informed cohort, not a production population claim",
        "reachability_scope": "fit-catalog novel targets; content retrieval can also retrieve cold items",
    })
