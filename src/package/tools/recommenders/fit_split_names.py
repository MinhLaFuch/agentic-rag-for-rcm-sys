from __future__ import annotations



def fit_split_names(eval_on: str) -> list[str]:
    if eval_on not in {"validation", "test"}:
        raise ValueError("eval_on must be validation or test")
    return ["train"] if eval_on == "validation" else ["train", "validation"]

