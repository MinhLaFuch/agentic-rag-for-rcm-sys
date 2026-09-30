class LLMProviderError(RuntimeError):
    """Lỗi chung khi gọi LLM provider (timeout, auth, rate limit...)."""