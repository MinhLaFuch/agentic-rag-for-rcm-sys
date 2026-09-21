"""Amazon Reviews 2023 -> 4 standard files.

Flow: load -> merge -> k-core -> assign idx -> leave-one-out split -> save.
"""
from __future__ import annotations

import pandas as pd

from notebook.pipeline.preprocess import leave_one_out_split
from package.utils.data import get_amazon_category
from package.utils.log import AMAZON_PROCESS_LOG_DIR
from package.utils import setup_logging
from package.preprocess._export import write_outputs

from .utils._assign_index import assign_idx
from .utils._kcore_filter import kcore_filter
from .utils._leave_one_out import leave_one_out
from .utils._load_df import load_meta_df, load_review_df, merge_df

logger = setup_logging(__name__, log_dir=AMAZON_PROCESS_LOG_DIR)


class ProcessPipeline:
    """Preprocess one Amazon category, e.g. ProcessPipeline("beauty").run()."""

    def __init__(self, category: str, min_interactions: int = 5):
        self.category = get_amazon_category(category)  # "beauty" -> All_Beauty
        self.min_interactions = min_interactions
        self.out_dir = self.category.processed_dir

        self.reviews: pd.DataFrame | None = None
        self.meta: pd.DataFrame | None = None
        self.canonical: pd.DataFrame | None = None
        
        self.user2idx: dict | None = None
        self.item2idx: dict | None = None

    # ---- steps -------------------------------------------------------
    def load(self) -> "ProcessPipeline":
        """1a. Load reviews and metadata separately."""
        self.reviews = load_review_df(self.category)
        self.meta = load_meta_df(self.category)
        logger.info("reviews: %s, meta: %s", self.reviews.shape, self.meta.shape)
        return self

    def merge(self) -> "ProcessPipeline":
        """1b. Merge reviews with metadata into the canonical table."""
        if self.reviews is None or self.meta is None:
            raise RuntimeError("Call load() before merge().")
        self.canonical = merge_df(self.reviews, self.meta)
        logger.info("%d rows after merging review+metadata", len(self.canonical))
        return self

    def filter_kcore(self) -> "ProcessPipeline":
        """2. Iterative k-core filter on users and items."""
        df = self._require_canonical("filter_kcore")
        self.canonical = kcore_filter(df, self.min_interactions)
        logger.info(
            "%d rows after k-core (>= %d)", len(self.canonical), self.min_interactions
        )
        return self

    def index_and_split(self) -> "ProcessPipeline":
        """3. Assign contiguous user/item idx, then leave-one-out split by time."""
        df = self._require_canonical("index_and_split")
        df, self.user2idx, self.item2idx = assign_idx(df)
        self.canonical = leave_one_out_split(df)
        logger.info("%d users, %d items", len(self.user2idx), len(self.item2idx))
        logger.info("split counts:\n%s", self.canonical["split"].value_counts())
        return self

    def save(self) -> "ProcessPipeline":
        """4. Write interactions / item_lookup parquet + user2idx / item2idx json."""
        df = self._require_canonical("save")
        if self.user2idx is None or self.item2idx is None:
            raise RuntimeError("Call index_and_split() before save().")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        write_outputs(df, self.user2idx, self.item2idx, str(self.out_dir))
        logger.info("Saved to %s: %s", self.out_dir, sorted(p.name for p in self.out_dir.iterdir()))
        return self

    def run(self) -> "ProcessPipeline":
        """Run all four steps in order."""
        logger.info("Processing category=%s (min_interactions=%d)", self.category.name, self.min_interactions)
        return self.load().merge().filter_kcore().index_and_split().save()

    # ---- helpers -----------------------------------------------------
    def _require_canonical(self, step: str) -> pd.DataFrame:
        if self.canonical is None:
            raise RuntimeError(f"Call merge() before {step}().")
        return self.canonical