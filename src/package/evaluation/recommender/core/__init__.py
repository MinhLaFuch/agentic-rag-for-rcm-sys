"""Core recommender evaluation logic."""

from ._dataclass import EvaluationResult
from .evaluate_recommender import evaluate_recommender
from .evaluate_ranking import evaluate_ranking
from .evaluation_protocol import evaluation_protocol

__all__ = [
    "EvaluationResult",
    "evaluate_recommender",
    "evaluate_ranking",
    "evaluation_protocol",
]
