"""Helper functions for corpus module."""

from __future__ import annotations

import sqlite3
import warnings
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


def read_only_authorizer():
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }

    def authorizer(action, arg1, arg2, *_):
        # These single-opcode functions can allocate arbitrarily large blobs;
        # SQLite's VM progress handler cannot interrupt work inside the C call.
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in {"zeroblob", "randomblob"}:
            return sqlite3.SQLITE_DENY
        if action in allowed:
            return sqlite3.SQLITE_OK
        # FTS5 MATCH reads PRAGMA data_version; deny every other pragma.
        if action == sqlite3.SQLITE_PRAGMA and arg1 == "data_version":
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorizer


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    """Make values JSON-safe (NaN -> None, numpy scalars -> Python)."""
    for k, v in row.items():
        if isinstance(v, float) and np.isnan(v):
            row[k] = None
        elif isinstance(v, np.generic):
            row[k] = v.item()
    return row

def _is_missing(value: Any) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value))


def normalize_categories(value: Any, item_id: str) -> list[str]:
    """Turn one ``categories`` cell into a clean list of category strings.

    Contract: missing (None / NaN / NA) -> []; a string -> [that string]; a list / tuple / set / array of strings
    -> those strings. Inside a list, missing and blank entries are skipped, entries are stripped and
    de-duplicated (order kept). Anything else (dict, bytes, numbers, nested lists, non-string entries) is
    malformed and raises ValueError instead of silently producing categories like 'None' or '97'.
    """
    if _is_missing(value):
        return []
    if isinstance(value, str):
        entries: list[Any] = [value]
    elif isinstance(value, (dict, bytes, bytearray)) or not isinstance(value, Iterable):
        raise ValueError(
            f"categories of item {item_id!r} must be a string or a list of strings, got {type(value).__name__}"
        )
    else:
        entries = list(value)
    out: list[str] = []
    for entry in entries:
        if _is_missing(entry):
            continue
        if not isinstance(entry, str):
            raise ValueError(f"categories of item {item_id!r} must contain only strings, got {entry!r}")
        entry = entry.strip()
        if entry:
            out.append(entry)
    return list(dict.fromkeys(out))


def numeric_column(series: pd.Series, name: str) -> pd.Series:
    """Coerce a metadata column to numbers. Non-numeric values become NULL (NaN) and are counted in a warning,
    so a column like average_rating can never end up with TEXT values that would break ``>=`` comparisons.
    No rounding or truncation is ever applied: 4.5 stays 4.5 and a fractional rating_number stays fractional."""
    numeric = pd.to_numeric(series, errors="coerce")
    invalid = int((numeric.isna() & series.notna()).sum())
    if invalid:
        warnings.warn(f"{invalid} non-numeric {name} value(s) were stored as NULL", UserWarning, stacklevel=3)
    return numeric
