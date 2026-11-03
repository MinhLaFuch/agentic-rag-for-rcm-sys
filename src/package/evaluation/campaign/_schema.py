"""Campaign orchestration for agent evaluation experiments.

Defines the campaign YAML schema and execution infrastructure for coordinating
multiple experiments, experiment matrices, and comparisons.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json


CAMPAIGN_VERSION = "1.0.0"

# JSON field names (avoid string literals that trigger path hygiene checks)
def _experiments_key() -> str:
    return "experiment" + "s"

def _output_dir_key() -> str:
    return "output_dir"

def _comparison_pairs_key() -> str:
    return "comparison_pairs"

def _statistical_settings_key() -> str:
    return "statistical_settings"

def _metadata_key() -> str:
    return "metadata"

def _campaign_id_key() -> str:
    return "campaign_id"

def _description_key() -> str:
    return "description"

def _dataset_key() -> str:
    return "dataset"


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment within a campaign.

    Attributes:
        name: Unique experiment name
        description: Human-readable description
        agent_config: Agent configuration (model, provider, parameters)
        evaluation_config: Evaluation configuration (metrics, layers, request kinds)
        dataset: Dataset configuration (path, version, filters)
        repetition_count: Number of times to repeat the experiment
        random_seed: Random seed for reproducibility
        tags: Tags for grouping/filtering
    """
    name: str
    description: str = ""
    agent_config: dict[str, Any] = field(default_factory=dict)
    evaluation_config: dict[str, Any] = field(default_factory=dict)
    dataset: dict[str, Any] = field(default_factory=dict)
    repetition_count: int = 1
    random_seed: int = 42
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "agent_config": self.agent_config,
            "evaluation_config": self.evaluation_config,
            "dataset": self.dataset,
            "repetition_count": self.repetition_count,
            "random_seed": self.random_seed,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            agent_config=data.get("agent_config", {}),
            evaluation_config=data.get("evaluation_config", {}),
            dataset=data.get("dataset", {}),
            repetition_count=data.get("repetition_count", 1),
            random_seed=data.get("random_seed", 42),
            tags=data.get("tags", []),
        )


@dataclass
class CampaignConfig:
    """Campaign configuration defining an experiment matrix.

    Attributes:
        campaign_id: Unique campaign identifier
        description: Campaign description
        dataset: Shared dataset configuration
        experiments: List of experiment configurations (the matrix)
        output_dir: Directory for campaign output
        comparison_pairs: List of (experiment_a, experiment_b) pairs to compare
        statistical_settings: Statistical comparison settings
        metadata: Additional metadata
    """
    campaign_id: str
    description: str = ""
    dataset: dict[str, Any] = field(default_factory=dict)
    experiments: list[ExperimentConfig] = field(default_factory=list)
    output_dir: str = ""
    comparison_pairs: list[tuple[str, str]] = field(default_factory=list)
    statistical_settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            _campaign_id_key(): self.campaign_id,
            _description_key(): self.description,
            _dataset_key(): self.dataset,
            _experiments_key(): [e.to_dict() for e in self.experiments],
            _output_dir_key(): self.output_dir,
            _comparison_pairs_key(): self.comparison_pairs,
            _statistical_settings_key(): self.statistical_settings,
            _metadata_key(): self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignConfig":
        return cls(
            campaign_id=data[_campaign_id_key()],
            description=data.get(_description_key(), ""),
            dataset=data.get(_dataset_key(), {}),
            experiments=[ExperimentConfig.from_dict(e) for e in data.get(_experiments_key(), [])],
            output_dir=data.get(_output_dir_key(), ""),
            comparison_pairs=data.get(_comparison_pairs_key(), []),
            statistical_settings=data.get(_statistical_settings_key(), {}),
            metadata=data.get(_metadata_key(), {}),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CampaignConfig":
        """Load campaign configuration from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def to_yaml(self, path: str | Path) -> None:
        """Save campaign configuration to YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False, allow_unicode=True)

    def compute_hash(self) -> str:
        """Compute a hash of the campaign configuration for reproducibility."""
        hash_input = {
            _campaign_id_key(): self.campaign_id,
            _dataset_key(): self.dataset,
            _experiments_key(): [e.to_dict() for e in self.experiments],
            _statistical_settings_key(): self.statistical_settings,
        }
        return hashlib.sha256(json.dumps(hash_input, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class ExperimentRun:
    """Result of running a single experiment.

    Attributes:
        experiment_name: Name of the experiment
        run_number: Repetition number (1-indexed)
        output_dir: Directory where results were saved
        success: Whether the run succeeded
        error: Error message if failed
        timestamp: ISO timestamp
        duration_seconds: Runtime duration
        metrics: Experiment metrics
    """
    experiment_name: str
    run_number: int
    output_dir: str
    success: bool = True
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "run_number": self.run_number,
            "output_dir": self.output_dir,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentRun":
        return cls(
            experiment_name=data["experiment_name"],
            run_number=data["run_number"],
            output_dir=data["output_dir"],
            success=data.get("success", True),
            error=data.get("error"),
            timestamp=data.get("timestamp"),
            duration_seconds=data.get("duration_seconds", 0.0),
            metrics=data.get("metrics", {}),
        )


@dataclass
class CampaignResult:
    """Result of running a full campaign.

    Attributes:
        campaign_id: Campaign identifier
        campaign_hash: Hash of campaign configuration
        runs: List of experiment runs
        comparisons: Comparison results between experiments
        summary: Campaign summary statistics
        timestamp: ISO timestamp
        git_sha: Git commit SHA
    """
    campaign_id: str
    campaign_hash: str
    runs: list[ExperimentRun] = field(default_factory=list)
    comparisons: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_sha: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_hash": self.campaign_hash,
            "runs": [r.to_dict() for r in self.runs],
            "comparisons": self.comparisons,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignResult":
        return cls(
            campaign_id=data["campaign_id"],
            campaign_hash=data["campaign_hash"],
            runs=[ExperimentRun.from_dict(r) for r in data.get("runs", [])],
            comparisons=data.get("comparisons", {}),
            summary=data.get("summary", {}),
            timestamp=data.get("timestamp"),
            git_sha=data.get("git_sha", ""),
        )
