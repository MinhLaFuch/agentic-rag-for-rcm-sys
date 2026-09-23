import pandas as pd
from pathlib import Path
from .jsonl import write_jsonl
from ..train import user_history

def _out_dir(category: str, workspace: str | None = None) -> Path:
    """Helper function to determine output directory."""
    if workspace:
        return Path(workspace) / "processed" / category
    return Path("data/processed") / category

def write_simulator_jsonl(
    test: pd.DataFrame,
    history: pd.DataFrame,
    products: pd.DataFrame,
    category: str,
    workspace: str | None = None,
    sample_n: int = 900,
    seed: int = 2024,
    max_history_len: int = 10,
    max_title_len: int = 50,
) -> Path:
    """Section 8: `simulator_test_data_{n}.jsonl`."""
    indexed = products.set_index("id")
    id2title = {
        item_id: str(row.title)[:max_title_len] for item_id, row in indexed.iterrows()
    }
    histories = user_history(history)
    sample_n = min(sample_n, len(test))
    sampled = test.sample(sample_n, random_state=seed).copy()
    sampled["history"] = sampled["user_id"].map(
        lambda user: "; ".join(
            id2title[item] for item in histories.get(user, [])[-max_history_len:]
        )
    )
    sampled["target"] = sampled["item_id"].map(indexed["title"])
    out_dir = _out_dir(category, workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"simulator_test_data_{sample_n}.jsonl"
    write_jsonl(sampled[["history", "target"]].to_dict("records"), path)
    return path