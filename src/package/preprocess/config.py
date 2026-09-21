"""Hằng số cấu hình dùng chung."""
import os

DEFAULT_LOCAL_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "resource", "data", "raw")
)
