import pandas as pd
from pathlib import Path

def _out_dir(category: str, workspace: str | None = None) -> Path:
    """Helper function to determine output directory."""
    if workspace:
        return Path(workspace) / "splits" / category
    return Path("data/splits") / category

def write_splits(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> Path:
    """Section 6: `train.tsv`, `valid.tsv`, `test.tsv`, `user_history.tsv`."""
    out = _out_dir(category, workspace)
    out.mkdir(parents=True, exist_ok=True)
    train.to_csv(out / "train.tsv", index=False)
    valid.to_csv(out / "valid.tsv", index=False)
    test.to_csv(out / "test.tsv", index=False)
    history.to_csv(out / "user_history.tsv", index=False)
    return out