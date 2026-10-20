from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        if encoding and encoding.lower().replace("-", "") != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                # Một số stream (ví dụ khi bị redirect) không hỗ trợ
                # reconfigure — bỏ qua, chấp nhận rủi ro thay vì crash
                # script vì lý do phụ.
                pass
