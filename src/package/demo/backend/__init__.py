from .live_backend import LiveBackend
from .offline_backend import OfflineDemoBackend

__all__ = ["LiveBackend", "OfflineDemoBackend", "get_backend"]


def get_backend(mock: bool = False):
    """Factory function to get backend. Returns OfflineDemoBackend if mock=True, else LiveBackend."""
    if mock:
        return OfflineDemoBackend()
    return LiveBackend
