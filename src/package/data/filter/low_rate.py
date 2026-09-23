import pandas as pd

def low_rating_filter(df: pd.DataFrame, rating_threshold: float = 3.0) -> pd.DataFrame:
    """Keep only interactions with rating >= rating_threshold."""
    return df[df["rating"] >= rating_threshold].reset_index(drop=True)