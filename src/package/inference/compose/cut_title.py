from __future__ import annotations

from .._limits import get_inference_limits


def cut_title(title: str) -> str:
    title = " ".join(title.split())
    limit = get_inference_limits().title_chars
    return title if len(title) <= limit else title[: limit - 1] + "…"
