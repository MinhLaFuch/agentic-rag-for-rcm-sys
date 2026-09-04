#!/usr/bin/env python
"""Prepare Steam review/game data for sequential recommendation / simulator use.

Pipeline: load raw json.gz reviews/games (or cached csv) + a supplementary
steam_games.csv -> clean text/price fields -> join the two meta sources on
lowercased game name -> filter/clean interactions (dedup, k-core) -> map ids
-> leave-one-out split -> save train/valid/test + game table -> build a
sampled jsonl set of (history, target) pairs for a simulator.
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
from bs4 import BeautifulSoup

logger = logging.getLogger("prepare_steam")


# --------------------------------------------------------------------------- #
# Raw json.gz loading
# --------------------------------------------------------------------------- #

def parse(path: str):
    """Yield one parsed record per line from a gzip file using Python literal
    eval (the Steam dumps use single-quoted dict literals, not strict JSON)."""
    with gzip.open(path, "r") as g:
        for line in g:
            yield eval(line)


def load_raw_reviews(review_file: str, cache_path: str) -> pd.DataFrame:
    if not os.path.exists(cache_path):
        logger.info("No review cache found, parsing raw file: %s", review_file)
        raw_review_df = pd.DataFrame(list(parse(review_file)))
        raw_review_df.to_csv(cache_path, index=None, sep="|")
    else:
        logger.info("Loading cached reviews from %s", cache_path)
        raw_review_df = pd.read_csv(cache_path, sep="|")
    logger.info("Shape of raw reviews: %s", raw_review_df.shape)
    return raw_review_df


def load_raw_meta(meta_file: str, cache_path: str) -> pd.DataFrame:
    if not os.path.exists(cache_path):
        logger.info("No meta cache found, parsing raw file: %s", meta_file)
        raw_meta_df = pd.DataFrame(list(parse(meta_file)))
        raw_meta_df.to_csv(cache_path, index=None, sep="|")
    else:
        logger.info("Loading cached meta from %s", cache_path)
        raw_meta_df = pd.read_csv(cache_path, sep="|")
    logger.info("Shape of raw meta: %s", raw_meta_df.shape)
    return raw_meta_df


# --------------------------------------------------------------------------- #
# Text cleaning
# --------------------------------------------------------------------------- #

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def remove_html_tags(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text()


def remove_emojis(text: str) -> str:
    return _EMOJI_PATTERN.sub(r"", text)


def remove_special_characters(text: str, remove_digits: bool = False) -> str:
    pattern = r"[^a-zA-Z0-9\s\u4e00-\u9fa5\,\.\!]" if not remove_digits else r"[^a-zA-Z\s\u4e00-\u9fa5\,\.\!]"
    return re.sub(pattern, "", text)


def clean_text(text: str, remove_digits: bool = False) -> str:
    text = remove_html_tags(text)
    text = remove_emojis(text)
    text = remove_special_characters(text, remove_digits=remove_digits)
    return text


def process_price(x) -> float:
    if isinstance(x, str):
        price = re.findall(r"\d+\.?\d*", x)
        return eval(price[0]) if price else 0
    elif isinstance(x, float):
        return x
    else:
        return 0


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
    processed_dir = os.path.join(args.data_dir, args.processed_subdir)
    chatbot_dir = os.path.join(args.data_dir, args.output_subdir)
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(chatbot_dir, exist_ok=True)

    review_file = os.path.join(args.data_dir, args.review_file)
    meta_file = os.path.join(args.data_dir, args.meta_file)
    all_meta_file = os.path.join(args.data_dir, args.all_meta_file)

    raw_review_df = load_raw_reviews(review_file, os.path.join(processed_dir, "reviews.csv"))
    raw_meta_df = load_raw_meta(meta_file, os.path.join(processed_dir, "meta.csv"))
    all_meta_df = pd.read_csv(all_meta_file)
    logger.info("Shape of supplementary meta (%s): %s", args.all_meta_file, all_meta_df.shape)

    # --- clean price, drop rows missing id/app_name, cast types ---
    raw_meta_df["price"] = raw_meta_df["price"].apply(process_price)
    avg_price = raw_meta_df["price"][~raw_meta_df["price"].isna()].mean()
    raw_meta_df["price"] = raw_meta_df["price"].fillna(avg_price)

    raw_meta_df_0 = raw_meta_df[~raw_meta_df["id"].isna()]
    raw_meta_df_0 = raw_meta_df_0[~raw_meta_df_0["app_name"].isna()]
    raw_meta_df_0.reset_index(inplace=True, drop=True)

    col2types = {"publisher": str, "app_name": str, "price": float, "id": int, "developer": str}
    raw_meta_df_1 = raw_meta_df_0.astype(col2types)
    raw_meta_df_1["app_name"] = raw_meta_df_1["app_name"].apply(lambda x: clean_text(x) if x is not None else "")
    raw_meta_df_1["developer"] = raw_meta_df_1["developer"].apply(lambda x: clean_text(x) if x is not None else "")

    # --- clean + join supplementary meta on lowercased game name ---
    all_meta_df_0 = all_meta_df[~all_meta_df["name"].isna()].reset_index(drop=True)
    all_meta_df_0 = all_meta_df_0.astype({"name": "str", "game_details": "str", "game_description": "str"})
    all_meta_df_0["name"] = all_meta_df_0["name"].apply(lambda x: clean_text(x) if x is not None else "")
    all_meta_df_0["game_details"] = all_meta_df_0["game_details"].apply(lambda x: clean_text(x) if x is not None else "")
    all_meta_df_0["game_description"] = all_meta_df_0["game_description"].apply(lambda x: clean_text(x) if x is not None else "")

    all_meta_df_0["_lower_name"] = all_meta_df_0["name"].apply(lambda x: x.lower()).astype(str)
    raw_meta_df_1["_lower_name"] = raw_meta_df_1["app_name"].apply(lambda x: x.lower()).astype(str)
    raw_meta_df_1 = raw_meta_df_1.drop_duplicates(keep="first").reset_index(drop=True)
    raw_meta_df_1 = raw_meta_df_1.set_index("_lower_name")
    all_meta_df_0 = all_meta_df_0.set_index("_lower_name")

    cat_df = raw_meta_df_1.join(all_meta_df_0, on="_lower_name", rsuffix="_all")
    logger.info(
        "Joined meta shape: %s (missing description=%d, missing details=%d)",
        cat_df.shape, cat_df["game_description"].isna().sum(), cat_df["game_details"].isna().sum(),
    )

    cat_df["release_date_all"] = pd.to_datetime(cat_df["release_date_all"], format="%b %d, %Y", errors="coerce")
    cat_df["release_date"] = pd.to_datetime(cat_df["release_date"], format="%Y-%m-%d", errors="coerce")
    missing_release = cat_df["release_date"].isna()
    cat_df.loc[missing_release, "release_date"] = cat_df.loc[missing_release, "release_date_all"]

    used_cols = ["id", "app_name", "release_date", "tags", "price", "game_description"]
    final_meta_df = cat_df[used_cols].reset_index(drop=True)
    final_meta_df["game_description"] = final_meta_df["game_description"].fillna("No description")
    final_meta_df.rename(columns={"app_name": "title", "game_description": "description"}, inplace=True)
    logger.info("Final meta shape: %s", final_meta_df.shape)

    coverage = raw_review_df["product_id"].isin(final_meta_df["id"]).sum() / raw_review_df.shape[0]
    logger.info("Review->meta id coverage: %.4f", coverage)

    # --- filter interactions ---
    review_df_0 = raw_review_df[["username", "product_id", "date"]]
    review_df_0 = review_df_0[~review_df_0["username"].isna()].reset_index(drop=True)

    data_df = keep_first_filter(review_df_0, user_col="username", item_col="product_id", time_col="date")
    data_df = k_core_filter(data_df, args.user_k, args.item_k, user_col="username", item_col="product_id")
    data_df = data_df.reset_index(drop=True)
    data_df = data_df.rename(columns={"username": "user_id", "product_id": "item_id"})

    # --- map ids ---
    (df, _, _), (user_map, item_map, _) = map_id(data_df)

    item_map_json = {str(k): v for k, v in item_map.items()}
    with open(os.path.join(processed_dir, "map.json"), "w") as f:
        json.dump({"item": item_map_json, "user": user_map}, f)
    logger.info("Saved id maps to %s", os.path.join(processed_dir, "map.json"))

    # --- split ---
    df_train_0, df_test = split_leave_one_out_seq(df, "user_id", "date", ["user_id", "item_id"])
    df_train, df_valid = split_leave_one_out_seq(df_train_0, "user_id", "date", ["user_id", "item_id"])

    df_train.to_csv(os.path.join(chatbot_dir, "train.tsv"), index=None)
    df_valid.to_csv(os.path.join(chatbot_dir, "valid.tsv"), index=None)
    df_test.to_csv(os.path.join(chatbot_dir, "test.tsv"), index=None)
    df_train_0.to_csv(os.path.join(chatbot_dir, "user_history.tsv"), index=None)
    logger.info(
        "Saved splits to %s (train=%d, valid=%d, test=%d, full_history=%d)",
        chatbot_dir, len(df_train), len(df_valid), len(df_test), len(df_train_0),
    )

    # --- game table ---
    saved_meta_df = final_meta_df[final_meta_df["id"].isin(item_map.keys())]
    saved_meta_df = saved_meta_df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    saved_meta_df["id"] = saved_meta_df["id"].apply(lambda x: item_map[x])
    saved_meta_df["tags"] = saved_meta_df["tags"].apply(lambda x: eval(x) if isinstance(x, str) else [])

    item_count = pd.value_counts(df_train_0["item_id"])
    saved_meta_df["visited_num"] = saved_meta_df["id"].apply(lambda x: item_count.loc[x] if x in item_count else 0)

    saved_meta_df.to_feather(os.path.join(chatbot_dir, "games.ftr"))
    logger.info("Saved game table (%d games) to %s", len(saved_meta_df), chatbot_dir)

    # --- simulator jsonl sample ---
    saved_meta_df_indexed = saved_meta_df.set_index("id")
    max_title_len = args.max_title_len
    id2title = {
        id_: saved_meta_df_indexed.loc[id_].title[:max_title_len] for id_ in saved_meta_df_indexed.index
    }

    n_sample = min(args.simulator_sample_n, len(df_test))
    test_data = df_test.sample(n_sample, random_state=args.seed)
    user_history = (
        df_train_0[df_train_0["user_id"].isin(test_data["user_id"])]
        .reset_index(drop=True)
        .groupby("user_id")
        .agg(list)
    )
    max_len = args.max_history_len
    test_data["history"] = test_data["user_id"].apply(
        lambda x: "; ".join([id2title[i] for i in user_history.loc[x]["item_id"][-max_len:]])
    )
    test_data["target"] = test_data["item_id"].apply(lambda x: saved_meta_df_indexed.loc[x].title)
    test_data.reset_index(drop=True, inplace=True)

    simulator_path = os.path.join(chatbot_dir, f"simulator_test_data_{n_sample}.jsonl")
    write_jsonl(test_data[["history", "target"]].to_dict("records"), simulator_path)

    logger.info("Pipeline complete.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--data_dir", required=True, help="Directory containing the raw dataset (json.gz files, steam_games.csv), and where outputs (processed_subdir/, output_subdir/) are written")
    parser.add_argument("--review_file", default="steam_reviews.json.gz", help="Filename (relative to data_dir) of the raw review json.gz dump")
    parser.add_argument("--meta_file", default="steam_games.json.gz", help="Filename (relative to data_dir) of the raw game json.gz dump")
    parser.add_argument("--all_meta_file", default="steam_games.csv", help="Filename (relative to data_dir) of the supplementary game metadata csv, joined in on lowercased game name")
    parser.add_argument("--processed_subdir", default="processed", help="Subdirectory of data_dir used to cache parsed reviews/meta csv and the id map")
    parser.add_argument("--output_subdir", default="chatbot", help="Subdirectory of data_dir to write splits/games/simulator data into")
    parser.add_argument("--user_k", type=int, default=5, help="Minimum interactions per user for k-core filtering")
    parser.add_argument("--item_k", type=int, default=5, help="Minimum interactions per item for k-core filtering")
    parser.add_argument("--max_history_len", type=int, default=10, help="Max number of past items included in a simulator history string")
    parser.add_argument("--max_title_len", type=int, default=50, help="Max characters of a game title used in simulator history/target strings")
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
