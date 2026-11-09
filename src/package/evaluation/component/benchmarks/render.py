"""Render test cases to JSONL format for the memory correctness benchmark."""

from __future__ import annotations

import json

from .build_cases import build_cases


def render() -> str:
    return "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in build_cases())