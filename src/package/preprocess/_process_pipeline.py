"""Notebook-compatible Amazon Reviews preprocessing pipeline."""
from __future__ import annotations

import logging

import pandas as pd

from package.config.data import get_amazon_category
from package.config.log import AMAZON_PROCESS_LOG_DIR
from package.utils import LogHelper
from package.utils._export import write_jsonl, write_outputs

from ._assign_index import assign_idx
from ._k_core_filter import keep_first_filter, kcore_filter, low_rating_filter
from ._leave_one_out import leave_one_out_split
from ._loader import load_reviews_and_metadata

logger = LogHelper(
    "process", level=logging.INFO, log_dir=AMAZON_PROCESS_LOG_DIR
).logger


class ProcessPipeline:
    """Run the same stages and produce the same artifacts as process.ipynb."""

    def __init__(
        self,
        category: str,
        rating_threshold: float = 3.0,
        user_k: int = 5,
        item_k: int = 5,
        min_interactions: int | None = None,
        simulator_sample_n: int = 900,
        seed: int = 2024,
        max_history_len: int = 10,
        max_title_len: int = 50,
    ):
        self.category = get_amazon_category(category)
        self.rating_threshold = rating_threshold
        self.user_k = min_interactions if min_interactions is not None else user_k
        self.item_k = min_interactions if min_interactions is not None else item_k
        self.simulator_sample_n = simulator_sample_n
        self.seed = seed
        self.max_history_len = max_history_len
        self.max_title_len = max_title_len
        self.out_dir = self.category.processed_dir / "chatbot"
        self.review_df: pd.DataFrame | None = None
        self.meta_df: pd.DataFrame | None = None
        self.user_map: dict = {}
        self.item_map: dict = {}

    def load(self) -> "ProcessPipeline":
        self.review_df, self.meta_df = load_reviews_and_metadata(self.category, logger)
        logger.info("Loaded reviews: %s", self.review_df.shape)
        logger.info("Loaded metadata: %s", self.meta_df.shape)
        return self

    def filter(self) -> "ProcessPipeline":
        df = self._require_reviews("filter")
        df = keep_first_filter(df)
        logger.info("After keep-first filter: %s", df.shape)
        df = low_rating_filter(df, self.rating_threshold)
        logger.info("After rating filter: %s", df.shape)
        self.review_df = kcore_filter(df, self.user_k, self.item_k)
        logger.info("After k-core filter: %s", self.review_df.shape)
        return self

    def filter_kcore(self) -> "ProcessPipeline":
        """Backward-compatible name for the complete filtering stage."""
        return self.filter()

    def index_and_split(self) -> "ProcessPipeline":
        df = self._require_reviews("index_and_split")
        df, self.user_map, self.item_map = assign_idx(df)
        self.user2idx, self.item2idx = self.user_map, self.item_map
        train, valid, test, history = leave_one_out_split(df)
        self.splits = train, valid, test, history
        self.review_df = df
        return self

    def save(self) -> "ProcessPipeline":
        if not hasattr(self, "splits"):
            raise RuntimeError("Call index_and_split() before save().")
        train, valid, test, history = self.splits
        products = write_outputs(
            train, valid, test, history, self.meta_df, self.user_map, self.item_map, self.out_dir
        )
        product_titles = products.set_index("id")["title"].fillna("").map(
            lambda title: str(title)[: self.max_title_len]
        )
        user_history = history.groupby("user_id")["item_id"].agg(list)
        sample_n = min(self.simulator_sample_n, len(test))
        sampled = test.sample(sample_n, random_state=self.seed).copy()
        sampled["history"] = sampled["user_id"].map(
            lambda user: "; ".join(
                product_titles[item]
                for item in user_history.get(user, [])[-self.max_history_len:]
                if item in product_titles
            )
        )
        sampled["target"] = sampled["item_id"].map(product_titles).fillna("")
        write_jsonl(
            sampled[["history", "target"]].to_dict("records"),
            self.out_dir / f"simulator_test_data_{sample_n}.jsonl",
        )
        logger.info("Pipeline complete: %s", self.out_dir)
        return self

    def run(self) -> "ProcessPipeline":
        return self.load().filter().index_and_split().save()

    def _require_reviews(self, step: str) -> pd.DataFrame:
        if self.review_df is None:
            raise RuntimeError(f"Call load() before {step}().")
        return self.review_df
