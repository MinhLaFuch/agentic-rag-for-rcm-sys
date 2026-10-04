"""Helper functions for corpus module."""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np


def read_only_authorizer():
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }

    def authorizer(action, arg1, *_):
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
