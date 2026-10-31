__all__ = ["JevClient"]


def __getattr__(name: str):
    if name == "JevClient":
        from .judge import JevClient
        return JevClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
