"""Protocol for candidate scoring."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class CandidateScorer(Protocol):
    """Anything that can score a given candidate set for a user (swap in SASRec/BPR later)."""

    name: str
    num_items: int

    def is_known_user(self, user_idx: int) -> bool: ...
    def seen_items(self, user_idx: int) -> set[int]: ...
    def score(self, user_idx: int, item_idxs: np.ndarray) -> np.ndarray:
        """Higher = better. Unknown users must still get a fallback score."""
        ...
    def has_personal_signal(self, user_idx: int) -> bool: ...
