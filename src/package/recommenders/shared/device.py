"""Device selection shared by offline recommenders.

Policy: use CUDA when torch is installed and a CUDA device is available;
otherwise fall back to CPU. Callers must still bound GPU memory themselves
(e.g. by tiling) — this only answers "is CUDA usable".
"""
from __future__ import annotations

_DEVICE: str | None = None


def get_device() -> str:
    """Return 'cuda' when torch+CUDA are usable, else 'cpu'. Cached."""
    global _DEVICE
    if _DEVICE is None:
        try:
            import torch
            _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            _DEVICE = "cpu"
    return _DEVICE


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False
