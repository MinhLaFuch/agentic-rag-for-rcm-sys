"""Error classes for LLM module."""


class LLMProviderError(RuntimeError):
    """General error when calling LLM provider (timeout, auth, rate limit...)."""