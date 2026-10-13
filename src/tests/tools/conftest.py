"""Shared deterministic fixture for the tools/ contract + integration tests ("tiny world").

Items (item_idx = row order).  Same original id ``A1`` exists in BOTH domains.

    idx  item_id        title                      categories              price  rating  n_ratings  store
    0    Games::A1      Quiet Mechanical Keyboard  [Computers, Keyboards]  49.99  4.5     120        Keychron
    1    Games::B2      Wireless Gaming Mouse      "Computers" (a string)  29.5   4.3     80         Logi
    2    Games::C3      Gaming Headset             [Audio]                 NULL   4.0     40         Logi
    3    Games::D4      Retro Console              None (missing)          99.0   NULL    NULL       None
    4    Toys::A1       Wooden Puzzle Game         [Puzzles, Toys]         15.0   4.7     300        Hape
    5    Toys::E5       Building Blocks Set        "Toys" (a string)       22.0   4.6     500        Hape

Train history (user_idx -> items) and what it means for segments with sparse_max=4:

    u0: {}                     cold (0)
    u1: {0}                    sparse (1)
    u2: {0,1,4,5}              sparse (4 == sparse_max, the boundary)
    u3: {0,1,2,4,5}            warm (5 = sparse_max+1); only item 3 is still recommendable
    u4: {0,1,4}                sparse (3)
    u5: {0,1,2,3,4,5}          warm; has seen EVERYTHING (nothing recommendable), no target

Item popularity in train = column sums = [5, 4, 2, 1, 4, 3]; popularity order (ties -> smaller idx) = 0,1,4,5,2,3.

Held-out target:  u0:{4}  u1:{3}  u2:{2,3}  u3:{3}  u4:{2}
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from package.tools import ItemCorpus

ITEMS = ["Games::A1", "Games::B2", "Games::C3", "Games::D4", "Toys::A1", "Toys::E5"]
HISTORY = {0: [], 1: [0], 2: [0, 1, 4, 5], 3: [0, 1, 2, 4, 5], 4: [0, 1, 4], 5: [0, 1, 2, 3, 4, 5]}
TARGET = {0: [4], 1: [3], 2: [2, 3], 3: [3], 4: [2]}
POPULARITY_ORDER = [0, 1, 4, 5, 2, 3]


def _matrix(rows: dict[int, list[int]], n_users: int = 6, n_items: int = 6) -> sp.csr_matrix:
    r = [u for u, items in rows.items() for _ in items]
    c = [i for items in rows.values() for i in items]
    return sp.csr_matrix((np.ones(len(r), dtype=np.float32), (r, c)), shape=(n_users, n_items))


@dataclass
class World:
    meta: pd.DataFrame
    corpus: ItemCorpus
    train: sp.csr_matrix
    target: sp.csr_matrix
    interactions: pd.DataFrame  # user_idx / item_idx long format of ``train`` (legacy DataFrame API)
    item2id: dict[str, int]
    user2id: dict[str, int]


@pytest.fixture
def world() -> World:
    meta = pd.DataFrame(
        {
            "parent_asin": ["A1", "B2", "C3", "D4", "A1", "E5"],
            "domain": ["Games"] * 4 + ["Toys"] * 2,
            "title": [
                "Quiet Mechanical Keyboard", "Wireless Gaming Mouse", "Gaming Headset",
                "Retro Console", "Wooden Puzzle Game", "Building Blocks Set",
            ],
            "store": ["Keychron", "Logi", "Logi", None, "Hape", "Hape"],
            "price": [49.99, 29.5, None, 99.0, 15.0, 22.0],
            "average_rating": [4.5, 4.3, 4.0, None, 4.7, 4.6],
            "rating_number": [120, 80, 40, None, 300, 500],
            "main_category": ["Computers", "Computers", "Audio", None, "Toys", "Toys"],
            "categories": [["Computers", "Keyboards"], "Computers", ["Audio"], None, ["Puzzles", "Toys"], "Toys"],
        }
    )
    corpus = ItemCorpus.from_dataframe(meta)
    train = _matrix(HISTORY)
    rows, cols = train.nonzero()
    return World(
        meta=meta,
        corpus=corpus,
        train=train,
        target=_matrix(TARGET),
        interactions=pd.DataFrame({"user_idx": rows, "item_idx": cols}),
        item2id={item: i for i, item in enumerate(ITEMS)},
        user2id={f"u{i}": i for i in range(6)},
    )

