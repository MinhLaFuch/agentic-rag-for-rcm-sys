"""Pydantic schemas for config validation (mục XX)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# Allowed values duplicated here (not imported) to keep package.config a leaf layer.
AGENT_NAMES = ("baseline", "type1", "planner", "planner_memory")
METADATA_POLICIES = ("historical_static_catalog", "snapshot")
QUERY_NORMALIZATIONS = ("raw", "ascii_fold")
QUERY_MODES = ("history", "category_oracle")
SPLIT_NAMES = ("validation", "test")
EVAL_SPLIT_NAMES = ("train", "validation", "test")
LANGUAGES = ("vi", "en")
INFERENCE_MODES = ("llm", "template")
TOOL_VALIDATION_MODELS = ("knn", "popularity")
REQUEST_SCOPES = ("realistic", "oracle", "all")

_BASE_CONFIG = {"extra": "forbid"}


class AgentConfig(BaseModel):
    """Agent config from configs/agent/agent.yaml."""

    model_config = _BASE_CONFIG

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

    model_config = _BASE_CONFIG

    candidate_multiplier: int = Field(gt=0, description="Multiplier for candidate retrieval")
    min_candidates: int = Field(gt=0, description="Minimum candidates required")


class AgentEvalMultiTurnConfig(BaseModel):
    """Multi-turn conversation evaluation block inside agent_eval.yaml.

    Runs package.evaluation.multi_turn once per run_agent_eval invocation,
    after the main agent evaluation. ``output_dir=None`` writes
    ``multi_turn.json`` into the experiment dir; a path (absolute, or
    relative to experiments_dir) redirects it — the campaign overlay points
    it at ``campaigns/<id>/multi_turn/`` so the artifact lives in exactly
    one place. ``limits`` reserves Phase-C knobs (max turns/steps/token
    budget); empty until semantics are decided — nothing is enforced yet.
    """

    model_config = _BASE_CONFIG

    enabled: bool = Field(default=False, description="Run multi-turn eval after agent eval")
    dataset: str = Field(
        default="package/evaluation/multi_turn/conversations.jsonl",
        description="Conversation dataset path, src/-relative",
    )
    output_dir: str | None = Field(
        default=None,
        description="Directory for multi_turn.json (artifact is always <dir>/multi_turn.json); null = experiment dir",
    )
    limits: dict[str, Any] | None = Field(
        default=None,
        description="Reserved for Phase-C limit knobs (unset = no limits enforced)",
    )
    timeout_seconds: int = Field(
        default=1800, gt=0,
        description="Wall-clock cap for the multi-turn subprocess",
    )


class AgentEvalConfig(BaseModel):
    """Agent evaluation config from configs/agent/agent_eval.yaml."""

    model_config = _BASE_CONFIG

    agents: list[str] = Field(description="List of agent names to evaluate")
    k: int = Field(gt=0, description="Cutoff for metrics and number of recommendations")
    per_segment: int = Field(gt=0, description="Number of requests per (kind, segment)")
    n_ambiguous: int = Field(ge=0, description="Number of ambiguous requests")
    language: str = Field(description="Language for requests: vi | en")
    price_slack: float = Field(gt=0.0, description="Price slack multiplier for constrained requests")
    price_round_to: int = Field(gt=0, description="Price rounding multiple in USD")
    min_metadata_coverage: float = Field(ge=0.0, le=1.0, description="Minimum metadata coverage threshold")
    min_metadata_coverage_by_domain: dict[str, float] = Field(
        default_factory=dict,
        description="Per-domain metadata coverage overrides; unlisted domains inherit min_metadata_coverage",
    )
    trajectory_error_chars: int = Field(gt=0, description="Max chars for error messages in trajectory")
    max_consecutive_llm_errors: int = Field(gt=0, description="Max consecutive LLM errors before aborting")
    trajectory_file: str = Field(description="Trajectory file name")
    request_scope: str = Field(default="realistic", description="realistic | oracle | all request scope")
    enable_session: bool = Field(default=False, description="Create a fresh Session per request")
    metadata_policy: str = Field(default="historical_static_catalog", description="Metadata masking policy")
    use_prebuilt_corpus: bool = Field(default=True, description="Load prebuilt corpus instead of building in RAM")
    allow_missing_corpus_sources: bool = Field(default=False, description="Allow missing raw metadata sources")
    campaign_id: str | None = Field(default=None, description="Campaign identifier when run under a campaign (traceability exp -> campaign)")
    multi_turn: AgentEvalMultiTurnConfig = Field(
        default_factory=AgentEvalMultiTurnConfig,
        description="Optional multi-turn conversation evaluation step",
    )

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v: list[str]) -> list[str]:
        unknown = [a for a in v if a not in AGENT_NAMES]
        if unknown:
            raise ValueError(f"agents must be drawn from {list(AGENT_NAMES)}; got {unknown}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("vi", "en"):
            raise ValueError("language must be 'vi' or 'en'")
        return v

    @field_validator("request_scope")
    @classmethod
    def validate_request_scope(cls, v: str) -> str:
        if v not in REQUEST_SCOPES:
            raise ValueError(f"request_scope must be one of {list(REQUEST_SCOPES)}")
        return v

    @field_validator("metadata_policy")
    @classmethod
    def validate_metadata_policy(cls, v: str) -> str:
        if v not in METADATA_POLICIES:
            raise ValueError(f"metadata_policy must be one of {list(METADATA_POLICIES)}")
        return v


class LLMConfig(BaseModel):
    """LLM config from configs/agent/llm.yaml."""

    model_config = _BASE_CONFIG

    provider: str = Field(description="LLM provider name")
    model: str = Field(description="Model name")
    base_url: str = Field(default="", description="Base URL for OpenAI-compatible endpoint")
    api_key: str = Field(default="", description="API key (can be empty for local servers)")
    timeout_seconds: float = Field(gt=0.0, description="Request timeout in seconds")


class MemoryConfig(BaseModel):
    """Memory config from configs/agent/memory.yaml."""

    model_config = _BASE_CONFIG

    love_min_rating: int = Field(ge=0, le=5, description="Rating threshold for loved items")
    hate_max_rating: int = Field(ge=0, le=5, description="Rating threshold for hated items")
    top_n_loved_items: int = Field(gt=0, description="Number of top loved items to return")
    top_n_hated_items: int = Field(gt=0, description="Number of top hated items to return")
    top_n_categories: int = Field(gt=0, description="Number of top categories to return")
    recent_items: int = Field(gt=0, description="Number of recent items to return")
    session: SessionConfig = Field(description="Session state config")


class SessionConfig(BaseModel):
    """Session state config (multi-turn conversation)."""

    model_config = _BASE_CONFIG

    max_turns: int = Field(gt=0, description="Maximum turns in a session")
    max_shown_items: int = Field(gt=0, description="Maximum shown items to track")
    max_candidates: int = Field(gt=0, description="Maximum candidates per turn")
    max_turn_chars: int = Field(gt=0, description="Max chars for turn summary")


class ToolsConfig(BaseModel):
    """Tools config from configs/agent/tools.yaml."""

    model_config = _BASE_CONFIG

    max_candidates: int = Field(gt=0, description="Max candidates from FilterTool/SimilarTool/SearchTool")
    max_query_rows: int = Field(gt=0, description="Max rows from LookupTool")
    sql_time_budget_seconds: float = Field(gt=0.0, description="SQL time budget in seconds")
    max_output_summary_chars: int = Field(gt=0, description="Max chars for output summary in trajectory")
    defaults: ToolsDefaultsConfig = Field(description="Default values for tool arguments")
    semantic_search: SemanticSearchConfig = Field(description="Semantic search specific config")


class ToolsDefaultsConfig(BaseModel):
    """Default values for tool arguments."""

    model_config = _BASE_CONFIG

    sql_limit: int = Field(gt=0, description="Default FilterTool limit")
    item_cf_top_k: int = Field(gt=0, description="Default SimilarTool top_k")
    query_max_rows: int = Field(gt=0, description="Default LookupTool max_rows")
    memory_top_n_categories: int = Field(gt=0, description="Default MemoryTool top_n_categories")
    memory_recent_items: int = Field(gt=0, description="Default MemoryTool recent_items")


class SemanticSearchConfig(BaseModel):
    """Semantic search specific config."""

    model_config = _BASE_CONFIG

    default_limit: int = Field(gt=0, description="Default limit for SearchTool")
    max_query_tokens: int = Field(gt=0, description="Max tokens for BM25 query after stopword removal")


class InferenceConfig(BaseModel):
    """Inference config from configs/agent/inference.yaml."""

    model_config = _BASE_CONFIG

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
        if v not in INFERENCE_MODES:
            raise ValueError(f"mode must be one of {list(INFERENCE_MODES)}")
        return v


class AblationConfig(BaseModel):
    """Ablation config from configs/agent/ablation.yaml."""

    model_config = _BASE_CONFIG

    bootstrap_resamples: int = Field(gt=0, description="Number of bootstrap resamples")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level (e.g., 0.95 for 95%)")
    min_n_warn: int = Field(gt=0, description="Minimum sample count to show warning")
    seed: int = Field(description="Random seed for bootstrap")
    metrics: list[str] = Field(description="List of metrics to compare")
    groups: dict[str, list[str]] = Field(description="Group labels to experiment directories")
    contrasts: list[dict[str, Any]] = Field(description="List of contrasts to compare")


class ReferencePlansConfig(BaseModel):
    """Reference plans config from configs/agent/reference_plans.yaml."""

    model_config = _BASE_CONFIG

    reference_plans: dict[str, list[list[str]]] = Field(
        description="Mapping from request kind to ordered groups of tools"
    )


class BaselinesConfig(BaseModel):
    """Baselines config from configs/eval/baselines.yaml."""

    model_config = _BASE_CONFIG

    seed: int = Field(description="Random seed for sampling/scoring")
    models: list[str] = Field(description="Baseline model names")
    popularity_fallback: bool = Field(description="Use popularity fallback for item_knn")
    popularity_source: Literal["train_core", "full_history"] = Field(
        default="train_core",
        description="Popularity fit source: train_core pairs or full pre-target history")
    item_knn_hybrid_weight: float | None = Field(
        default=None, ge=0.0, allow_inf_nan=False,
        description="Opt-in HybridItemKNNRecommender weight (CF + full pre-target-history popularity)")
    item_knn: ItemKnnBaselineConfig = Field(description="ItemKNN baseline params")
    bpr_mf: BprMfBaselineConfig = Field(description="BPR-MF baseline params")


class ItemKnnBaselineConfig(BaseModel):
    """ItemKNN baseline params."""

    model_config = _BASE_CONFIG

    k: int = Field(gt=0, description="Neighbors / top_k for item-item similarity")
    block_elements: int = Field(gt=0, description="Max dense elements per block when building similarity")


class BprMfBaselineConfig(BaseModel):
    """BPR-MF baseline params."""

    model_config = _BASE_CONFIG

    embedding_dim: int = Field(gt=0)
    learning_rate: float = Field(gt=0.0)
    reg: float = Field(ge=0.0)
    epochs: int = Field(gt=0)
    batch_size: int = Field(gt=0)


class RankingEvalConfig(BaseModel):
    """Ranking evaluation config from configs/eval/ranking_eval.yaml."""

    model_config = _BASE_CONFIG

    all_users: bool = Field(default=False, description="Evaluate all target-bearing users after exclusions")
    exclude_users_from: list[str] = Field(default_factory=list, description="Prior experiment config.yaml paths whose sampled users are excluded")
    per_segment: int = Field(gt=0, description="Max sampled users per segment")
    candidate_budget: int = Field(gt=0, description="Max candidates per source")
    seed_items: int = Field(gt=0, description="Recent fit items seeding ItemCF")
    query_items: int = Field(gt=0, description="Recent titles joined into semantic query")
    ks: list[int] = Field(description="Metric cutoffs; must be <= 3*candidate_budget")
    popularity_weights: list[float] = Field(description="Popularity weights for BaselineScorer variants")
    metadata_policy: str = Field(description="Metadata masking policy")
    query_normalization: str = Field(description="Query preprocessing mode")
    use_prebuilt_corpus: bool = Field(description="Load prebuilt corpus instead of building in RAM")
    allow_missing_corpus_sources: bool = Field(description="Accept prebuilt corpus when raw meta files are missing")
    batch_size: int = Field(gt=0, description="Checkpoint batch size")
    progress_every: int = Field(gt=0, description="Progress print interval")
    # seed is intentionally absent: the single seed source is eval/baselines.baselines.seed

    @field_validator("metadata_policy")
    @classmethod
    def validate_metadata_policy(cls, v: str) -> str:
        if v not in METADATA_POLICIES:
            raise ValueError(f"metadata_policy must be one of {list(METADATA_POLICIES)}")
        return v

    @field_validator("query_normalization")
    @classmethod
    def validate_query_normalization(cls, v: str) -> str:
        if v not in QUERY_NORMALIZATIONS:
            raise ValueError(f"query_normalization must be one of {list(QUERY_NORMALIZATIONS)}")
        return v

    @field_validator("ks")
    @classmethod
    def validate_ks(cls, v: list[int]) -> list[int]:
        if not v or min(v) < 1:
            raise ValueError("ks must contain positive cutoffs")
        return v

    @field_validator("popularity_weights")
    @classmethod
    def validate_weights(cls, v: list[float]) -> list[float]:
        if not v or len(set(v)) != len(v):
            raise ValueError("popularity_weights must be non-empty and unique")
        return v


class CandidateRecallConfig(BaseModel):
    """Candidate recall config from configs/eval/candidate_recall.yaml."""

    model_config = _BASE_CONFIG

    budgets: list[int] = Field(description="Candidate budgets N to measure")
    per_segment: int = Field(gt=0, description="Max sampled users per segment")
    seed_items: int = Field(gt=0, description="Recent items seeding ItemCF")
    query_items: int = Field(gt=0, description="Recent titles joined into semantic query")
    query_modes: list[str] = Field(description="history | category_oracle query modes")
    metadata_policy: str = Field(description="Metadata masking policy")
    query_normalization: str = Field(description="Query preprocessing mode")
    use_prebuilt_corpus: bool = Field(description="Load prebuilt corpus instead of building in RAM")
    allow_missing_corpus_sources: bool = Field(description="Accept prebuilt corpus when raw meta files are missing")
    min_metadata_coverage: float = Field(ge=0.0, le=1.0, description="Min item-mapping metadata coverage")

    @field_validator("query_modes")
    @classmethod
    def validate_query_modes(cls, v: list[str]) -> list[str]:
        unknown = [m for m in v if m not in QUERY_MODES]
        if not v or unknown:
            raise ValueError(f"query_modes must be drawn from {list(QUERY_MODES)}; got {unknown or v}")
        return v

    @field_validator("metadata_policy")
    @classmethod
    def validate_metadata_policy(cls, v: str) -> str:
        if v not in METADATA_POLICIES:
            raise ValueError(f"metadata_policy must be one of {list(METADATA_POLICIES)}")
        return v

    @field_validator("query_normalization")
    @classmethod
    def validate_query_normalization(cls, v: str) -> str:
        if v not in QUERY_NORMALIZATIONS:
            raise ValueError(f"query_normalization must be one of {list(QUERY_NORMALIZATIONS)}")
        return v


class ToolValidationConfig(BaseModel):
    """Tool validation config from configs/eval/tool_validation.yaml."""

    model_config = _BASE_CONFIG

    model: str = Field(description="knn | popularity")
    eval_users: int = Field(gt=0, description="Validation users sampled for ranking sanity check")
    negatives: int = Field(ge=0, description="Random negative items per user")
    seed: int = Field(description="Sampling seed")

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in TOOL_VALIDATION_MODELS:
            raise ValueError(f"model must be one of {list(TOOL_VALIDATION_MODELS)}")
        return v


class MemoryUtilityConfig(BaseModel):
    """Memory utility config from configs/eval/memory_utility.yaml."""

    model_config = _BASE_CONFIG

    baseline_agent: str = Field(description="Baseline agent name in scored.jsonl")
    memory_agent: str = Field(description="Memory agent name in scored.jsonl")
    k: int = Field(gt=0, description="Cutoff for default_metrics")
    resamples: int = Field(gt=0, description="Bootstrap resample count")
    confidence: float = Field(ge=0.0, lt=1.0, description="Confidence level")
    min_n: int = Field(gt=0, description="Minimum paired samples for a verdict")
    seed: int = Field(description="Bootstrap seed")
    dirs: list[str] = Field(default_factory=list, description="Experiment dirs (relative to experiments_dir) holding both agents")
    baseline_dirs: list[str] = Field(default_factory=list, description="Baseline-only experiment dirs")
    memory_dirs: list[str] = Field(default_factory=list, description="Memory-only experiment dirs")
    metrics: list[str] = Field(default_factory=list, description="Metric names; empty = default_metrics(k)")


class TuningItemKnnGrid(BaseModel):
    model_config = _BASE_CONFIG
    k: list[int] = Field(description="k grid values")


class TuningBprMfGrid(BaseModel):
    model_config = _BASE_CONFIG
    embedding_dim: list[int] = Field(description="embedding_dim grid values")
    learning_rate: list[float] = Field(description="learning_rate grid values")
    reg: list[float] = Field(description="reg grid values")
    epochs: list[int] = Field(description="epochs grid values")


class TuningConfig(BaseModel):
    """Tuning config from configs/eval/tuning.yaml."""

    model_config = _BASE_CONFIG

    selection_metric: str = Field(description="Validation metric used for selection")
    run_final_test: bool = Field(description="Refit winner on train+validation and evaluate test once")
    models: list[str] = Field(description="Default model list")
    item_knn: TuningItemKnnGrid = Field(description="ItemKNN tuning grid")
    bpr_mf: TuningBprMfGrid = Field(description="BPR-MF tuning grid")


class ComponentBenchmarksConfig(BaseModel):
    """Component benchmarks config from configs/eval/component_benchmarks.yaml."""

    model_config = _BASE_CONFIG

    runs: int = Field(ge=1, description="Runs per case to average")
    configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Per-component evaluator config maps"
    )
    datasets: dict[str, str] = Field(
        default_factory=dict,
        description="Component name -> benchmark dataset path (src-relative), used by _run_all.py",
    )


class RankingDiagnosticsConfig(BaseModel):
    """Diagnostics config from configs/eval/ranking_diagnostics.yaml."""

    model_config = _BASE_CONFIG

    seed: int = Field(description="Bootstrap percentile CI seed")
    bootstrap_samples: int = Field(gt=0, description="Resamples for the 95% paired-delta CI")


class TemporalTrainCoreConfig(BaseModel):
    """Fixed cutoffs for the opt-in temporal_train_core data protocol."""

    model_config = _BASE_CONFIG

    train_end_inclusive_ms: int = Field(description="Train cutoff, inclusive (ms)")
    validation_end_inclusive_ms: int = Field(description="Validation cutoff, inclusive (ms)")


class SplitConfig(BaseModel):
    """Split config from configs/data/split.yaml."""

    model_config = _BASE_CONFIG

    train_ratio: float = Field(gt=0.0, lt=1.0)
    validation_ratio: float = Field(ge=0.0, lt=1.0)
    test_ratio: float = Field(ge=0.0, lt=1.0)
    item_knn_splits: list[str] = Field(description="Splits the ItemKNN stage builds for")
    data_protocol: str = Field(default="legacy_kcore_before_split",
                               description="Stage 2/3 protocol: legacy_kcore_before_split | temporal_train_core")
    temporal_train_core: TemporalTrainCoreConfig = Field(
        description="Fixed cutoffs used only when data_protocol=temporal_train_core")

    @field_validator("item_knn_splits")
    @classmethod
    def validate_splits(cls, v: list[str]) -> list[str]:
        unknown = [s for s in v if s not in EVAL_SPLIT_NAMES]
        if unknown:
            raise ValueError(f"item_knn_splits must be drawn from {list(EVAL_SPLIT_NAMES)}; got {unknown}")
        return v

    @field_validator("data_protocol")
    @classmethod
    def validate_data_protocol(cls, v: str) -> str:
        if v not in {"legacy_kcore_before_split", "temporal_train_core"}:
            raise ValueError("data_protocol must be 'legacy_kcore_before_split' or 'temporal_train_core'")
        return v

    @model_validator(mode="after")
    def validate_ratios_sum(self) -> "SplitConfig":
        total = self.train_ratio + self.validation_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"train/validation/test ratios must sum to 1.0 (got {total})")
        return self


class DemoConfig(BaseModel):
    """Demo UI config from configs/agent/demo.yaml."""

    model_config = _BASE_CONFIG

    max_error_length: int = Field(gt=0)
    max_items_display: int = Field(gt=0)
    sample_users_per_segment: int = Field(gt=0)
    default_language: str = Field(description="vi | en")
    max_recent_items_display: int = Field(gt=0)
    max_turn_history_rows: int = Field(gt=0)
    eval_on: str = Field(description="validation | test — split loaded by LiveBackend")
    use_prebuilt_corpus: bool = Field(description="Load prebuilt corpus instead of building in RAM")
    allow_missing_corpus_sources: bool = Field(description="Accept prebuilt corpus when raw meta files are missing")
    intent_path_enabled: bool = Field(default=False, description="Type1 intent search path (keyword + filters); default off")

    @field_validator("default_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in LANGUAGES:
            raise ValueError(f"default_language must be one of {list(LANGUAGES)}")
        return v

    @field_validator("eval_on")
    @classmethod
    def validate_eval_on(cls, v: str) -> str:
        if v not in SPLIT_NAMES:
            raise ValueError(f"eval_on must be one of {list(SPLIT_NAMES)}")
        return v


class CampaignExperimentFileConfig(BaseModel):
    """One experiment entry inside configs/evaluation/campaign.yaml."""

    model_config = _BASE_CONFIG

    name: str = Field(description="Unique experiment name")
    description: str = ""
    agent_config: dict[str, Any] = Field(default_factory=dict)
    evaluation_config: dict[str, Any] = Field(default_factory=dict)
    dataset: dict[str, Any] = Field(default_factory=dict)
    repetition_count: int = 1
    random_seed: int = 42
    tags: list[str] = Field(default_factory=list)


class CampaignFileConfig(BaseModel):
    """configs/evaluation/campaign.yaml — shape validated by load_config; consumed by CampaignConfig.from_dict."""

    model_config = _BASE_CONFIG

    campaign_id: str = Field(description="Unique campaign identifier")
    description: str = ""
    dataset: dict[str, Any] = Field(default_factory=dict)
    parameter_grid: dict[str, Any] = Field(default_factory=dict)
    experiments: list[CampaignExperimentFileConfig] = Field(default_factory=list)
    evaluation_config: dict[str, Any] = Field(default_factory=dict)
    output_dir: str = ""
    comparison_pairs: list[list[str]] = Field(default_factory=list)
    statistical_settings: dict[str, Any] = Field(default_factory=dict)
    default_agents: list[str] = Field(
        default_factory=lambda: ["baseline", "type1", "planner", "planner_memory"]
    )
    allow_missing_corpus_sources: bool = True
    experiment_timeout_seconds: int = 3600
    multi_turn: str = Field(default="once", description="Multi-turn eval mode: once | never | all")

    @field_validator("multi_turn")
    @classmethod
    def validate_multi_turn(cls, v: str) -> str:
        if v not in ("once", "never", "all"):
            raise ValueError("multi_turn must be 'once', 'never' or 'all'")
        return v


class JudgeFaithfulnessConfig(BaseModel):
    """Faithfulness axis of configs/eval/judge.yaml."""

    model_config = _BASE_CONFIG

    support_threshold: float = Field(ge=0.0, le=1.0, description="noul probability >= this counts as supported")
    instructions: str = Field(description="Jev question instructions for faithfulness")


class JudgeCommunicationCriterionConfig(BaseModel):
    """One communication criterion (relevance, clarity, language, honesty_about_gaps)."""

    model_config = _BASE_CONFIG

    instructions: str = Field(description="Jev Score question instructions")
    rubric: list[str] = Field(min_length=1, description="5-point rubric, poor -> excellent")


class JudgeCommunicationConfig(BaseModel):
    """Communication axis: dynamic set of criteria."""

    model_config = _BASE_CONFIG

    criteria: dict[str, JudgeCommunicationCriterionConfig] = Field(
        description="Criterion name -> instructions + rubric"
    )


class JudgeEvaluationConfig(BaseModel):
    """Evaluation section of configs/eval/judge.yaml."""

    model_config = _BASE_CONFIG

    faithfulness: JudgeFaithfulnessConfig
    communication: JudgeCommunicationConfig


class ScoringConfig(BaseModel):
    """Agent scorer config from configs/agent/scoring.yaml."""

    model_config = _BASE_CONFIG

    mode: str = Field(default="baseline", description="baseline | hybrid")
    hybrid_popularity_weight: float = Field(default=4.0, ge=0, description="Hybrid scorer popularity weight")


class JudgeConfig(BaseModel):
    """Jev judge config from configs/eval/judge.yaml (no wrapper key)."""

    model_config = _BASE_CONFIG

    provider: str = Field(description="Judgment provider to use (jev)")
    api_key: str = Field(default="", description="TypeSafe API key; filled by env interpolation")
    model: str = Field(description="Jev model name")
    base_url: str = Field(description="TypeSafe API base URL")
    timeout_seconds: float = Field(gt=0, description="Per-request timeout")
    enable_long_context: bool = Field(default=False, description="Long-context header for large states")
    evaluation: JudgeEvaluationConfig


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
        "agent/demo": ("demo", DemoConfig),
        "agent/llm": (None, LLMConfig),
        "agent/memory": ("memory", MemoryConfig),
        "agent/tools": ("tools", ToolsConfig),
        "agent/inference": ("inference", InferenceConfig),
        "agent/scoring": ("scoring", ScoringConfig),
        "agent/ablation": ("ablation", AblationConfig),
        "agent/reference_plans": (None, ReferencePlansConfig),  # No key wrapper
        "eval/baselines": ("baselines", BaselinesConfig),
        "eval/ranking_eval": ("ranking_eval", RankingEvalConfig),
        "eval/candidate_recall": ("candidate_recall", CandidateRecallConfig),
        "eval/tool_validation": ("tool_validation", ToolValidationConfig),
        "eval/memory_utility": ("memory_utility", MemoryUtilityConfig),
        "eval/tuning": ("tuning", TuningConfig),
        "eval/component_benchmarks": ("component_benchmarks", ComponentBenchmarksConfig),
        "eval/judge": (None, JudgeConfig),
        "eval/ranking_diagnostics": ("ranking_diagnostics", RankingDiagnosticsConfig),
        "data/split": ("split", SplitConfig),
        "evaluation/campaign": (None, CampaignFileConfig),  # No key wrapper
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
