"""
Windows PowerShell/cmd mặc định dùng codepage cp1252 hoặc cp437 cho
stdout, không phải UTF-8. Khi script in ký tự tiếng Việt có dấu hoặc
em-dash (—), Python có thể ném UnicodeEncodeError NGAY SAU KHI pipeline
đã chạy xong và lưu kết quả thành công — rất khó chịu vì người dùng
tưởng pipeline lỗi trong khi dữ liệu đã lưu đúng.

Gọi `ensure_utf8_stdout()` ở đầu mỗi script (trước dòng print đầu tiên)
để tự động ép stdout/stderr sang UTF-8, thay ký tự không encode được
bằng '?' thay vì crash toàn bộ chương trình.
"""

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
