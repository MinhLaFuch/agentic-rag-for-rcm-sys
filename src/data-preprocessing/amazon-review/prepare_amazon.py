#!/usr/bin/env python
"""Prepare Amazon review data (e.g. Beauty) for sequential recommendation / simulator use.

Pipeline: load raw json.gz (or cached tsv) -> clean meta -> merge/filter interactions
(dedup, rating threshold, k-core) -> map ids -> leave-one-out split -> save train/valid/test
+ product table -> build a small sampled jsonl set of (history, target) pairs for a simulator.
"""

import argparse
import gzip
import json
import logging
import os
import pickle
import re
from typing import Dict, List

import pandas as pd

logger = logging.getLogger("prepare_amazon")


# --------------------------------------------------------------------------- #
# Raw json.gz loading
# `---------------------------------------------------------------------------` #

def parse(path: str):
    """Yield one parsed JSON record per line from a gzip file with Amazon's
    loose single-quoted JSON format."""
    quote_fix = re.compile(r"(?<!\\)'")  # unescaped single quotes -> double quotes
    with gzip.open(path, "rb") as g:
        for line in g:
            line = quote_fix.sub('"', line)
            yield json.loads(line)


def get_df(path: str) -> pd.DataFrame:
    records = {i: d for i, d in enumerate(parse(path))}
    return pd.DataFrame.from_dict(records, orient="index")


def load_reviews_and_meta(data_dir: str, dataset_name: str) -> "tuple[pd.DataFrame, pd.DataFrame]":
    """Load review/meta data, using a cached tsv pair if present, else parsing
    the raw json.gz files and writing the tsv cache for next time."""
    reviews_tsv = os.path.join(data_dir, "reviews.tsv")
    meta_tsv = os.path.join(data_dir, "meta.tsv")

    if not (os.path.exists(reviews_tsv) and os.path.exists(meta_tsv)):
        logger.info("No tsv cache found, loading from raw json.gz files")
        review_df = get_df(os.path.join(data_dir, f"reviews_{dataset_name}.json.gz"))
        meta_df = get_df(os.path.join(data_dir, f"meta_{dataset_name}.json.gz"))
        review_df.to_csv(reviews_tsv, index=None)
        meta_df.to_csv(meta_tsv, index=None)
    else:
        logger.info("Loading from cached tsv files")
        review_df = pd.read_csv(reviews_tsv, low_memory=False)
        meta_df = pd.read_csv(meta_tsv, low_memory=False)

    logger.info("Columns of reviews: %s", list(review_df.columns))
    logger.info("Columns of meta data: %s", list(meta_df.columns))
    logger.info("Shape of reviews: %s", review_df.shape)
    logger.info("Shape of metas: %s", meta_df.shape)
    return review_df, meta_df


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #

def get_valid_ids(df: pd.DataFrame, col_name: str, k: int) -> pd.Index:
    frequency = df.groupby([col_name])[[col_name]].count()
    return frequency[frequency[col_name] >= k].index


def keep_first_filter(
    df: pd.DataFrame, user_col: str = "user_id", item_col: str = "item_id", time_col: str = "timestamp"
) -> pd.DataFrame:
    """Only keep the first interaction for duplicated (user, item) reviews."""
    logger.info("Keeping only the first interaction per duplicated review, begin: %s", df.shape)
    df = df.sort_values(by=[user_col, time_col]).reset_index(drop=True)
    df = df.drop_duplicates(subset=[user_col, item_col], keep="first").reset_index(drop=True)
    logger.info("After keep-first filter: %s", df.shape)
    return df


def k_core_filter(
    df: pd.DataFrame,
    user_k: int = 10,
    item_k: int = 10,
    user_col: str = "user_id",
    item_col: str = "item_id",
    max_iter: int = 20,
) -> pd.DataFrame:
    """Iteratively drop users/items with fewer than user_k/item_k interactions
    until the counts stop changing (or max_iter is reached)."""
    logger.info(
        "k-core filtering: users with < %d interactions and items with < %d interactions are dropped, begin: %s",
        user_k, item_k, df.shape,
    )
    num_users_prev = len(df[user_col].unique())
    num_items_prev = len(df[item_col].unique())
    delta = True
    it = 0

    while delta and it < max_iter:
        valid_users = get_valid_ids(df, user_col, user_k)
        df = df[df[user_col].isin(valid_users)]

        valid_items = get_valid_ids(df, item_col, item_k)
        df = df[df[item_col].isin(valid_items)]

        num_users = len(valid_users)
        num_items = len(valid_items)

        delta = (num_users != num_users_prev) or (num_items != num_items_prev)
        logger.info(
            "Iter %d: users %d/%d, items %d/%d", it, num_users, num_users_prev, num_items, num_items_prev
        )

        num_users_prev = num_users
        num_items_prev = num_items
        it += 1

    logger.info("After k-core filter: %s", df.shape)
    return df


def low_rating_filter(df: pd.DataFrame, rating_thres: float = 3.0, rating_col: str = "rating") -> pd.DataFrame:
    logger.info("Filtering ratings below %.1f, begin: %s", rating_thres, df.shape)
    df = df[df[rating_col] >= rating_thres].reset_index(drop=True)
    logger.info("After rating filter: %s", df.shape)
    return df


# --------------------------------------------------------------------------- #
# ID mapping
# --------------------------------------------------------------------------- #

def map_id(
    df: pd.DataFrame,
    user_colname: str = "user_id",
    item_colname: str = "item_id",
    group_colname: str = None,
    price_df: pd.DataFrame = None,
    group_df: pd.DataFrame = None,
):
    """Map raw user/item ids to contiguous 1-indexed integer ids. Returns
    ((df, price_df, group_df), (user_map, item_map, group_map))."""
    logger.info("Mapping user and item ids to contiguous integers")
    users = df[user_colname].unique()
    items = df[item_colname].unique()
    user_map = {u: k + 1 for k, u in enumerate(users)}
    item_map = {i: k + 1 for k, i in enumerate(items)}
    df[user_colname] = df[user_colname].apply(lambda x: user_map[x])
    df[item_colname] = df[item_colname].apply(lambda x: item_map[x])

    if group_colname is not None and group_colname in df:
        groups = df[group_colname].unique()
        group_map = {g: k + 1 for k, g in enumerate(groups)}
        df[group_colname] = df[group_colname].apply(lambda x: group_map[x])
    else:
        group_map = {}

    if price_df is not None:
        if user_colname in price_df:
            price_df = price_df[price_df[user_colname].isin(users)].reset_index(drop=True)
            price_df[user_colname] = price_df[user_colname].apply(lambda x: user_map[x])
        if item_colname in price_df:
            price_df = price_df[price_df[item_colname].isin(items)].reset_index(drop=True)
            price_df[item_colname] = price_df[item_colname].apply(lambda x: item_map[x])

    if group_df is not None:
        if user_colname in group_df:
            group_df = group_df[group_df[user_colname].isin(users)].reset_index(drop=True)
            group_df[user_colname] = group_df[user_colname].apply(lambda x: user_map[x])
        if item_colname in group_df:
            group_df = group_df[group_df[item_colname].isin(items)].reset_index(drop=True)
            group_df[item_colname] = group_df[item_colname].apply(lambda x: item_map[x])
        if group_colname is not None and group_colname in group_df:
            groups = group_df[group_colname].unique()
            group_map = {g: k + 1 for k, g in enumerate(groups)}
            group_df[group_colname] = group_df[group_colname].apply(lambda x: group_map[x])

    return (df, price_df, group_df), (user_map, item_map, group_map)


# --------------------------------------------------------------------------- #
# Train/valid/test splitting
# --------------------------------------------------------------------------- #

def split_leave_one_out_seq(
    data: pd.DataFrame, col_name: str, time_colname: str, col_names_2_return: list
):
    """Leave the last (by time) interaction per group as the held-out set."""
    if time_colname in data:
        df_sorted = data.sort_values(by=[col_name, time_colname]).reset_index(drop=True)
    else:
        df_sorted = data.sort_values(by=col_name).reset_index(drop=True)

    df_test = df_sorted.groupby(by=col_name, as_index=False).nth(-1)
    df_train = df_sorted.iloc[df_sorted.index.difference(df_test.index)]
    return (
        df_train.reset_index(drop=True)[col_names_2_return],
        df_test.reset_index(drop=True)[col_names_2_return],
    )


# --------------------------------------------------------------------------- #
# Simulator jsonl export
# --------------------------------------------------------------------------- #

def write_jsonl(obj: List[Dict], fpath: str) -> None:
    try:
        with open(fpath, "w") as outfile:
            for entry in obj:
                json.dump(entry, outfile)
                outfile.write("\n")
        logger.info("Saved %d records to %s", len(obj), fpath)
    except Exception as e:
        fallback = f"{fpath}.pkl"
        logger.exception("Failed to write jsonl (%s), falling back to pickle at %s", e, fallback)
        with open(fallback, "wb") as tempfile:
            pickle.dump(obj, tempfile)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

def run_pipeline(args: argparse.Namespace) -> None:
    out_dir = os.path.join(args.data_dir, args.output_subdir)
    os.makedirs(out_dir, exist_ok=True)

    review_df, meta_df = load_reviews_and_meta(args.data_dir, args.dataset_name)

    # --- clean meta ---
    meta_df["categories"] = meta_df["categories"].apply(lambda x: eval(x)[0])
    meta_df = meta_df[~meta_df["title"].isna()]
    meta_df.reset_index(drop=True, inplace=True)
    logger.info("Meta after dropping missing titles: %s", meta_df.shape)

    used_col = {
        "review": ["reviewerID", "asin", "overall", "unixReviewTime"],
        "meta": ["asin", "title", "categories", "price", "description", "brand"],
    }
    review_df = review_df[used_col["review"]]
    meta_df = meta_df[used_col["meta"]]
    review_df = review_df.rename(
        columns={"overall": "rating", "unixReviewTime": "timestamp", "asin": "item_id", "reviewerID": "user_id"}
    )
    meta_df = meta_df.rename(columns={"asin": "item_id", "categories": "category"})

    # --- filter interactions ---
    review_df = review_df[review_df["item_id"].isin(meta_df["item_id"])].reset_index(drop=True)
    data_df = keep_first_filter(review_df)
    data_df = low_rating_filter(data_df, args.rating_threshold)
    data_df = k_core_filter(data_df, args.user_k, args.item_k)
    data_df = data_df.reset_index(drop=True)

    # --- map ids ---
    (df, _, _), (user_map, item_map, _) = map_id(data_df)

    with open(os.path.join(args.data_dir, "map.json"), "w") as f:
        json.dump({"item": item_map, "user": user_map}, f)
    logger.info("Saved id maps to %s", os.path.join(args.data_dir, "map.json"))

    # --- split ---
    df_train_0, df_test = split_leave_one_out_seq(df, "user_id", "timestamp", ["user_id", "item_id"])
    df_train, df_valid = split_leave_one_out_seq(df_train_0, "user_id", "timestamp", ["user_id", "item_id"])

    df_train.to_csv(os.path.join(out_dir, "train.tsv"), index=None)
    df_valid.to_csv(os.path.join(out_dir, "valid.tsv"), index=None)
    df_test.to_csv(os.path.join(out_dir, "test.tsv"), index=None)
    df_train_0.to_csv(os.path.join(out_dir, "user_history.tsv"), index=None)
    logger.info(
        "Saved splits to %s (train=%d, valid=%d, test=%d, full_history=%d)",
        out_dir, len(df_train), len(df_valid), len(df_test), len(df_train_0),
    )

    # --- product table ---
    saved_meta_df = meta_df[meta_df["item_id"].isin(item_map.keys())]
    saved_meta_df = saved_meta_df.drop_duplicates(subset=["item_id"], keep="first").reset_index(drop=True)
    saved_meta_df["item_id"] = saved_meta_df["item_id"].apply(lambda x: item_map[x])

    user_history = df_train_0.groupby("user_id").agg(list)
    item_count = pd.value_counts(user_history["item_id"].explode())
    saved_meta_df.rename(columns={"item_id": "id"}, inplace=True)
    saved_meta_df["visited_num"] = saved_meta_df["id"].apply(lambda x: item_count.loc[x] if x in item_count else 0)

    saved_meta_df.to_feather(os.path.join(out_dir, "products.ftr"))
    saved_meta_df.to_csv(os.path.join(out_dir, "products.csv"), index=None, sep="|")
    logger.info("Saved product table (%d items) to %s", len(saved_meta_df), out_dir)

    # --- simulator jsonl sample ---
    saved_meta_df_indexed = saved_meta_df.set_index("id")
    max_title_len = args.max_title_len
    id2title = {
        id_: saved_meta_df_indexed.loc[id_].title[:max_title_len] for id_ in saved_meta_df_indexed.index
    }

    n_sample = min(args.simulator_sample_n, len(df_test))
    test_data = df_test.sample(n_sample, random_state=args.seed)
    max_len = args.max_history_len
    test_data["history"] = test_data["user_id"].apply(
        lambda x: "; ".join([id2title[i] for i in user_history.loc[x]["item_id"][-max_len:]])
    )
    test_data["target"] = test_data["item_id"].apply(lambda x: saved_meta_df_indexed.loc[x].title)
    test_data.reset_index(drop=True, inplace=True)

    simulator_path = os.path.join(out_dir, f"simulator_test_data_{n_sample}.jsonl")
    write_jsonl(test_data[["history", "target"]].to_dict("records"), simulator_path)

    logger.info("Pipeline complete.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--data_dir", required=True, help="Directory containing the raw dataset (json.gz files or cached tsv), and where outputs (map.json, output_subdir/) are written")
    parser.add_argument("--dataset_name", default="Beauty", help="Amazon category name, used to locate reviews_{name}.json.gz / meta_{name}.json.gz when no tsv cache exists")
    parser.add_argument("--output_subdir", default="chatbot", help="Subdirectory of data_dir to write splits/products/simulator data into")
    parser.add_argument("--rating_threshold", type=float, default=3.0, help="Minimum rating kept (rows below this are dropped)")
    parser.add_argument("--user_k", type=int, default=5, help="Minimum interactions per user for k-core filtering")
    parser.add_argument("--item_k", type=int, default=5, help="Minimum interactions per item for k-core filtering")
    parser.add_argument("--max_history_len", type=int, default=10, help="Max number of past items included in a simulator history string")
    parser.add_argument("--max_title_len", type=int, default=50, help="Max characters of a product title used in simulator history/target strings")
    parser.add_argument("--simulator_sample_n", type=int, default=900, help="Number of test users sampled for the simulator jsonl export")
    parser.add_argument("--seed", type=int, default=2024, help="Random seed for the simulator sample")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting pipeline with args: %s", vars(args))
    run_pipeline(args)


if __name__ == "__main__":
    main()
