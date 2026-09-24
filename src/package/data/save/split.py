import logging
from pathlib import Path

import pandas as pd

from .layout import ExportDirs, ensure_dir

log = logging.getLogger(__name__)


def write_splits(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> Path:
    """Section 6: `train.tsv`, `valid.tsv`, `test.tsv`, `user_history.tsv`."""
    out = ensure_dir(ExportDirs(category, workspace).splits)
    train.to_csv(out / "train.tsv", index=False)
    valid.to_csv(out / "valid.tsv", index=False)
    test.to_csv(out / "test.tsv", index=False)
    history.to_csv(out / "user_history.tsv", index=False)
    log.info(
        "Wrote splits to %s (train=%d, valid=%d, test=%d, history=%d)",
        out, len(train), len(valid), len(test), len(history),
    )
    return out