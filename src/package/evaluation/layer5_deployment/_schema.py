"""Column definitions for Layer 5: Deployment, Safety & Efficiency."""

COLUMNS = (
    "prompt_tokens",
    "completion_tokens",
    "llm_latency_seconds",
    "tool_latency_seconds",
    "wall_seconds",
    "inference_attempts",
    "inference_prompt_tokens",
    "inference_completion_tokens",
    "inference_latency_seconds",
    "provider_error",
    "sql_time_budget_hits",
)
