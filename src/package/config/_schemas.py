"""Pydantic schemas for config validation (mục XX)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentConfig(BaseModel):
    """Agent config from configs/agent/agent.yaml."""

    max_steps: int = Field(gt=0, description="Maximum steps in a plan")
    plan_retries: int = Field(ge=0, description="Number of retries for invalid JSON plans")
    reflect_rounds: int = Field(ge=0, description="Number of reflection rounds after failed execution")
    reflect_error_chars: int = Field(gt=0, description="Max chars to keep from error messages in reflection")
    max_tokens: int = Field(gt=0, description="Max tokens per LLM call")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature")
    type1: Type1Config = Field(description="Type1Agent-specific config")

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if v < 0.0 or v > 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class Type1Config(BaseModel):
    """Type1Agent config."""

    candidate_multiplier: int = Field(gt=0, description="Multiplier for candidate retrieval")
    min_candidates: int = Field(gt=0, description="Minimum candidates required")


class AgentEvalConfig(BaseModel):
    """Agent evaluation config from configs/agent/agent_eval.yaml."""

    agents: list[str] = Field(description="List of agent names to evaluate")
    k: int = Field(gt=0, description="Cutoff for metrics and number of recommendations")
    per_segment: int = Field(gt=0, description="Number of requests per (kind, segment)")
    n_ambiguous: int = Field(ge=0, description="Number of ambiguous requests")
    language: str = Field(description="Language for requests: vi | en")
    price_slack: float = Field(gt=0.0, description="Price slack multiplier for constrained requests")
    price_round_to: int = Field(gt=0, description="Price rounding multiple in USD")
    min_metadata_coverage: float = Field(ge=0.0, le=1.0, description="Minimum metadata coverage threshold")
    trajectory_error_chars: int = Field(gt=0, description="Max chars for error messages in trajectory")
    max_consecutive_llm_errors: int = Field(gt=0, description="Max consecutive LLM errors before aborting")
    experiments_subdir: str = Field(description="Subdirectory for experiments")
    trajectory_file: str = Field(description="Trajectory file name")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("vi", "en"):
            raise ValueError("language must be 'vi' or 'en'")
        return v


class LLMConfig(BaseModel):
    """LLM config from configs/agent/llm.yaml."""

    provider: str = Field(description="LLM provider name")
    model: str = Field(description="Model name")
    base_url: str = Field(default="", description="Base URL for OpenAI-compatible endpoint")
    api_key: str = Field(default="", description="API key (can be empty for local servers)")
    timeout_seconds: float = Field(gt=0.0, description="Request timeout in seconds")


class MemoryConfig(BaseModel):
    """Memory config from configs/agent/memory.yaml."""

    love_min_rating: int = Field(ge=0, le=5, description="Rating threshold for loved items")
    hate_max_rating: int = Field(ge=0, le=5, description="Rating threshold for hated items")
    top_n_loved_items: int = Field(gt=0, description="Number of top loved items to return")
    top_n_hated_items: int = Field(gt=0, description="Number of top hated items to return")
    top_n_categories: int = Field(gt=0, description="Number of top categories to return")
    recent_items: int = Field(gt=0, description="Number of recent items to return")
    session: SessionConfig = Field(description="Session state config")


class SessionConfig(BaseModel):
    """Session state config (multi-turn conversation)."""

    max_turns: int = Field(gt=0, description="Maximum turns in a session")
    max_shown_items: int = Field(gt=0, description="Maximum shown items to track")
    max_candidates: int = Field(gt=0, description="Maximum candidates per turn")
    max_turn_chars: int = Field(gt=0, description="Max chars for turn summary")


class ToolsConfig(BaseModel):
    """Tools config from configs/agent/tools.yaml."""

    max_candidates: int = Field(gt=0, description="Max candidates from SQLTool/ItemCFTool/SemanticSearchTool")
    max_query_rows: int = Field(gt=0, description="Max rows from QueryTool")
    sql_time_budget_seconds: float = Field(gt=0.0, description="SQL time budget in seconds")
    max_output_summary_chars: int = Field(gt=0, description="Max chars for output summary in trajectory")
    defaults: ToolsDefaultsConfig = Field(description="Default values for tool arguments")
    semantic_search: SemanticSearchConfig = Field(description="Semantic search specific config")


class ToolsDefaultsConfig(BaseModel):
    """Default values for tool arguments."""

    sql_limit: int = Field(gt=0, description="Default SQLTool limit")
    item_cf_top_k: int = Field(gt=0, description="Default ItemCFTool top_k")
    query_max_rows: int = Field(gt=0, description="Default QueryTool max_rows")
    memory_top_n_categories: int = Field(gt=0, description="Default MemoryTool top_n_categories")
    memory_recent_items: int = Field(gt=0, description="Default MemoryTool recent_items")


class SemanticSearchConfig(BaseModel):
    """Semantic search specific config."""

    default_limit: int = Field(gt=0, description="Default limit for SemanticSearchTool")
    max_query_tokens: int = Field(gt=0, description="Max tokens for BM25 query after stopword removal")


class InferenceConfig(BaseModel):
    """Inference config from configs/agent/inference.yaml."""

    mode: str = Field(description="Inference mode: llm | template")
    max_items: int = Field(gt=0, description="Max items to present in answer")
    max_tokens: int = Field(gt=0, description="Max tokens for LLM answer generation")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature for answer generation")
    llm_retries: int = Field(ge=0, description="Number of retries for invalid/ungrounded LLM answers")
    check_numbers: bool = Field(description="Whether to check prices/ratings in LLM answers")
    title_chars: int = Field(gt=0, description="Max chars for product title truncation")
    reason_chars: int = Field(gt=0, description="Max chars for error/reason truncation")
    price_tolerance: float = Field(ge=0.0, description="Price tolerance in USD for number checking")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("llm", "template"):
            raise ValueError("mode must be 'llm' or 'template'")
        return v


class AblationConfig(BaseModel):
    """Ablation config from configs/agent/ablation.yaml."""

    bootstrap_resamples: int = Field(gt=0, description="Number of bootstrap resamples")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level (e.g., 0.95 for 95%)")
    min_n_warn: int = Field(gt=0, description="Minimum sample count to show warning")
    seed: int = Field(description="Random seed for bootstrap")
    metrics: list[str] = Field(description="List of metrics to compare")
    groups: dict[str, list[str]] = Field(description="Group labels to experiment directories")
    contrasts: list[dict[str, Any]] = Field(description="List of contrasts to compare")
    output_subdir: str = Field(description="Output subdirectory for reports")


class ReferencePlansConfig(BaseModel):
    """Reference plans config from configs/agent/reference_plans.yaml."""

    reference_plans: dict[str, list[list[str]]] = Field(
        description="Mapping from request kind to ordered groups of tools"
    )

    model_config = {"extra": "ignore"}


def validate_config(name: str, config_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a config dict against its Pydantic schema.

    Args:
        name: Config name (e.g., "agent/agent", "agent/llm")
        config_dict: Raw config dict from YAML

    Returns:
        Validated config dict

    Raises:
        ConfigError: If validation fails
    """
    from ._error import ConfigError

    config_map = {
        "agent/agent": ("agent", AgentConfig),
        "agent/agent_eval": ("agent_eval", AgentEvalConfig),
        "agent/llm": (None, LLMConfig),
        "agent/memory": ("memory", MemoryConfig),
        "agent/tools": ("tools", ToolsConfig),
        "agent/inference": ("inference", InferenceConfig),
        "agent/ablation": ("ablation", AblationConfig),
        "agent/reference_plans": (None, ReferencePlansConfig),  # No key wrapper
    }

    if name not in config_map:
        # No schema defined yet, return as-is
        return config_dict

    key, schema_cls = config_map[name]

    try:
        if key:
            validated = schema_cls(**config_dict[key])
            config_dict[key] = validated.model_dump()
        else:
            validated = schema_cls(**config_dict)
            config_dict = validated.model_dump()
        return config_dict
    except Exception as exc:
        # Provide more detailed error message
        import traceback
        error_details = traceback.format_exc()
        raise ConfigError(f"Config validation failed for {name}: {exc}\nDetails:\n{error_details}") from exc
