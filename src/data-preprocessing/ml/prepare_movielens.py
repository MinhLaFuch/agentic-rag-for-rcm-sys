#!/usr/bin/env python
"""Prepare MovieLens (ml-10m / ml-latest style) data for sequential recommendation
/ simulator use.

Pipeline: load movies + ratings (.csv or .dat) -> parse movie title/year -> filter
interactions (rating>=3, dedup, k-core) -> map ids -> leave-one-out split -> save
train/valid/test + movie table -> build a sampled simulator jsonl (history/target
from the held-out test set) and a one-turn training jsonl (history/target sampled
from full user histories).
"""

import argparse
import json
import logging
import os
import pickle
import re
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger("prepare_movielens")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_movies(data_dir: str, suffix: str) -> pd.DataFrame:
    path = os.path.join(data_dir, f"movies{suffix}")
    if suffix == ".dat":
        movies = pd.read_csv(path, sep="::", names=["id", "titles", "tags"], engine="python")
    else:
        movies = pd.read_csv(path, sep=",", engine="python")
        movies.rename(columns={"title": "titles", "genres": "tags", "movieId": "id"}, inplace=True)

    pattern = r"^(.+)\((\d{4})\)"
    movies[["title", "release_date"]] = movies["titles"].str.extract(pattern)
    missing_title = movies["release_date"].isna()
    movies.loc[missing_title, "title"] = movies.loc[missing_title, "titles"]
    movies["title"] = movies["title"].apply(lambda x: x.strip())
    movies["tags"] = movies["tags"].str.split("|")
    movies["release_date"] = pd.to_datetime(movies["release_date"])
    logger.info("Loaded movies: %s", movies.shape)
    return movies


def load_ratings(data_dir: str, suffix: str) -> pd.DataFrame:
    path = os.path.join(data_dir, f"ratings{suffix}")
    if suffix == ".dat":
        ratings = pd.read_csv(
            path, sep="::", names=["user_id", "item_id", "rating", "timestamp"], engine="python"
        )
    else:
        ratings = pd.read_csv(path, sep=",", engine="python")
        ratings.rename(columns={"userId": "user_id", "movieId": "item_id"}, inplace=True)
    logger.info("Loaded ratings: %s", ratings.shape)
    return ratings


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #

def get_valid_ids(df: pd.DataFrame, col_name: str, k: int) -> pd.Index:
    frequency = df.groupby([col_name])[[col_name]].count()
    return frequency[frequency[col_name] >= k].index


def k_core_filter(
    df: pd.DataFrame,
    user_k: int = 10,
    item_k: int = 10,
    user_col_name: str = "user_id",
    item_col_name: str = "item_id",
    max_iter: int = 5,
) -> pd.DataFrame:
    """Iteratively drop users/items with fewer than user_k/item_k interactions
    until the counts stop changing (or max_iter is reached)."""
    logger.info(
        "k-core filtering: users with < %d interactions and items with < %d interactions are dropped, begin: %s",
        user_k, item_k, df.shape,
    )
    num_users_prev = len(df[user_col_name].unique())
    num_items_prev = len(df[item_col_name].unique())
    delta = True
    it = 0

    while delta and it < max_iter:
        valid_users = get_valid_ids(df, user_col_name, user_k)
        df = df[df[user_col_name].isin(valid_users)]

        valid_items = get_valid_ids(df, item_col_name, item_k)
        df = df[df[item_col_name].isin(valid_items)]

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


# --------------------------------------------------------------------------- #
# Train/valid/test splitting
# --------------------------------------------------------------------------- #

def split_leave_one_out_seq(
    data: pd.DataFrame, user_col_name: str, time_colname: str, col_names_2_return: list = None
):
    """Leave the last (by time) interaction per user as the held-out set."""
    if time_colname in data:
        df_sorted = data.sort_values(by=[user_col_name, time_colname]).reset_index(drop=True)
    else:
        df_sorted = data.sort_values(by=user_col_name).reset_index(drop=True)

    df_test = df_sorted.groupby(by=user_col_name, as_index=False).nth(-1)
    df_train = df_sorted.iloc[df_sorted.index.difference(df_test.index)]
    if col_names_2_return is None:
        col_names_2_return = data.columns
    return (
        df_train.reset_index(drop=True)[col_names_2_return],
        df_test.reset_index(drop=True)[col_names_2_return],
    )


# --------------------------------------------------------------------------- #
# Simulator / one-turn jsonl export
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
    os.makedirs(args.output_dir, exist_ok=True)

    movies = load_movies(args.data_dir, args.suffix)
    ratings = load_ratings(args.data_dir, args.suffix)

    # --- filter interactions ---
    user_col_name, item_col_name = "user_id", "item_id"
    data = ratings.sort_values(by=[user_col_name, "timestamp"], ignore_index=True)
    logger.info("Original dataset size: %s", data.shape)

    data = data[data["rating"] >= args.rating_threshold].reset_index(drop=True)
    logger.info("After rating>=%.1f filter: %s", args.rating_threshold, data.shape)

    data = data.drop_duplicates(subset=[user_col_name, item_col_name], keep="last").reset_index(drop=True)
    logger.info("After drop_duplicates: %s", data.shape)

    data = k_core_filter(data, user_k=args.user_k, item_k=args.item_k, user_col_name=user_col_name, item_col_name=item_col_name)
    data = data.reset_index(drop=True)

    # --- map ids ---
    users, items = data[user_col_name].unique(), data[item_col_name].unique()
    logger.info("Mapping %d users and %d items to contiguous integers", len(users), len(items))
    user_id_map = {id_: i + 1 for i, id_ in enumerate(users)}
    item_id_map = {id_: i + 1 for i, id_ in enumerate(items)}
    data[item_col_name] = data[item_col_name].apply(lambda x: item_id_map[x])
    data[user_col_name] = data[user_col_name].apply(lambda x: user_id_map[x])

    movies["new_id"] = movies["id"].apply(lambda x: item_id_map[x] if x in item_id_map else -1)
    movies = movies[movies["new_id"] > 0]
    logger.info("Movies kept after id mapping: %s", movies.shape)

    # --- split ---
    df_train0, df_test = split_leave_one_out_seq(data, user_col_name=user_col_name, time_colname="timestamp")
    df_train, df_valid = split_leave_one_out_seq(df_train0, user_col_name=user_col_name, time_colname="timestamp")
    logger.info(
        "Size in Train/Valid/Test: %s / %s / %s", df_train.shape, df_valid.shape, df_test.shape
    )

    df_train = df_train[[user_col_name, item_col_name]]
    df_valid = df_valid[[user_col_name, item_col_name]]
    df_test = df_test[[user_col_name, item_col_name]]
    user_hist = df_train0[[user_col_name, item_col_name]]

    df_train.to_csv(os.path.join(args.output_dir, "train.tsv"), index=None)
    df_valid.to_csv(os.path.join(args.output_dir, "valid.tsv"), index=None)
    df_test.to_csv(os.path.join(args.output_dir, "test.tsv"), index=None)
    user_hist.to_csv(os.path.join(args.output_dir, "user_history.tsv"), index=None)
    logger.info("Saved splits to %s", args.output_dir)

    # --- movie table ---
    movies = movies[["new_id", "title", "release_date", "tags"]]
    view_count = pd.value_counts(user_hist[item_col_name])
    movies["view_count"] = movies["new_id"].apply(lambda x: view_count[x])
    movies.rename(columns={"new_id": "id"}, inplace=True)
    movies.reset_index(drop=True, inplace=True)

    movies.to_feather(os.path.join(args.output_dir, "movies.ftr"))
    movies.to_csv(os.path.join(args.output_dir, "movies.csv"), index=None)
    logger.info("Saved movie table (%d movies) to %s", len(movies), args.output_dir)

    movies_indexed = movies.set_index("id")

    # --- simulator jsonl sample (from held-out test interactions) ---
    user_history_grouped = user_hist.groupby(by=user_col_name).agg(list)
    n_sim_sample = min(args.simulator_sample_n, len(df_test))
    test_data = df_test.sample(n_sim_sample, random_state=args.seed)
    test_data["history"] = test_data[user_col_name].apply(lambda x: user_history_grouped.loc[x][item_col_name])
    test_data["history"] = test_data["history"].apply(lambda x: x[: args.max_history_len])
    test_data["history"] = test_data["history"].apply(
        lambda x: ", ".join([movies_indexed.loc[i].title for i in x])
    )
    test_data["target"] = test_data[item_col_name].apply(lambda x: movies_indexed.loc[x].title)

    simulator_path = os.path.join(args.output_dir, f"simulator_test_data_{n_sim_sample}.jsonl")
    write_jsonl(test_data[["history", "target"]].to_dict("records"), simulator_path)

    # --- one-turn training jsonl (sampled from full user histories) ---
    rng = np.random.default_rng(args.seed)
    n_user = min(args.one_turn_n_user, len(user_history_grouped))
    sampled_user_id = rng.choice(user_history_grouped.index, n_user, replace=False)
    train_data = user_history_grouped.loc[sampled_user_id].copy()

    train_data["target_id"] = train_data[item_col_name].apply(lambda x: x[-1])
    train_data["history_ids"] = train_data[item_col_name].apply(lambda x: x[:-1][-args.max_history_len:])
    train_data["history"] = train_data["history_ids"].apply(
        lambda x: "; ".join([movies_indexed.loc[i].title[: args.max_title_len] for i in x])
    )
    train_data["target"] = train_data["target_id"].apply(lambda x: movies_indexed.loc[x].title[: args.max_title_len])

    one_turn_path = os.path.join(args.output_dir, f"{n_user}-history-data.jsonl")
    write_jsonl(train_data[["history", "target"]].to_dict("records"), one_turn_path)

    logger.info("Pipeline complete.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--data_dir", required=True, help="Directory containing movies{suffix} and ratings{suffix}")
    parser.add_argument("--output_dir", required=True, help="Directory to write splits/movies/jsonl outputs into")
    parser.add_argument("--suffix", default=".csv", choices=[".csv", ".dat"], help="Raw file format/suffix — .csv (ml-latest, comma-separated with header) or .dat (ml-10m, :: separated, no header)")
    parser.add_argument("--rating_threshold", type=float, default=3.0, help="Minimum rating kept (rows below this are dropped)")
    parser.add_argument("--user_k", type=int, default=5, help="Minimum interactions per user for k-core filtering")
    parser.add_argument("--item_k", type=int, default=5, help="Minimum interactions per item for k-core filtering")
    parser.add_argument("--max_history_len", type=int, default=10, help="Max number of past items included in a history string")
    parser.add_argument("--max_title_len", type=int, default=50, help="Max characters of a movie title used in the one-turn history/target strings")
    parser.add_argument("--simulator_sample_n", type=int, default=900, help="Number of test users sampled for the simulator jsonl export")
    parser.add_argument("--one_turn_n_user", type=int, default=500, help="Number of users sampled for the one-turn training jsonl export")
    parser.add_argument("--seed", type=int, default=2024, help="Random seed for sampling")
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
