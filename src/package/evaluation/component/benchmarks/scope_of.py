"""Determine scope of a request kind."""

from __future__ import annotations

from package.evaluation._schema import ORACLE_KINDS


def scope_of(kind: str) -> str:
    return "oracle" if kind in ORACLE_KINDS else "realistic"