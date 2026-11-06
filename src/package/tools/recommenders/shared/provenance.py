"""Provenance tracking for recommender models.

Re-exports fit_provenance from fit_provenance.py for backward compatibility
with imports using `from package.tools.recommenders.shared.provenance import fit_provenance`.
"""

from .fit_provenance import fit_provenance


class Provenance:
    """Provenance tracking for recommender models."""

    @staticmethod
    def fit_provenance(fit_pairs, *, user2id=None, item2id=None, eval_on=None, tag=None) -> dict:
        """Compute fit provenance metadata."""
        return fit_provenance(fit_pairs, user2id=user2id, item2id=item2id, eval_on=eval_on, tag=tag)


__all__ = ["fit_provenance", "Provenance"]