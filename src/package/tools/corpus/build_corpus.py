"""Dựng ItemCorpus từ meta_<Domain>.jsonl.gz, chỉ giữ item có trong mapping, và kiểm tra độ phủ."""

from __future__ import annotations

from itertools import islice

import pandas as pd

from package.data import namespaced_item_id
from package.data.loader import load_item_metadata

from .item_corpus import ItemCorpus
from ._schema import COVERAGE_SAMPLE


def build_corpus(
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
) -> tuple[ItemCorpus, pd.DataFrame, float]:
    """
    meta_files: [(domain, đường dẫn meta)].
    item2id: mapping từ namespaced item_id ('Domain::asin') sang integer id.
    min_coverage: tỉ lệ tối thiểu item mapping phải có metadata, dưới mức này ném ValueError
    (thường do sai file meta hoặc sai định dạng id).
    Trả về (corpus, bảng metadata đã lọc, độ phủ ước lượng) — bảng này còn dùng để dựng text cho query mô phỏng.
    """

    def in_mapping(domain: str, asin: str) -> bool:
        return namespaced_item_id(domain, asin) in item2id

    meta = load_item_metadata(meta_files, keep=in_mapping)
    corpus = ItemCorpus.from_dataframe(meta)
    sample = list(islice(item2id, COVERAGE_SAMPLE))
    coverage = len(corpus.item_domains(sample)) / max(1, len(sample))
    if coverage < min_coverage:
        raise ValueError(
            f"Chỉ {coverage:.1%} item mapping có metadata (cần ≥ {min_coverage:.0%}): "
            "kiểm tra resource/raw/meta_<Domain>.jsonl.gz và định dạng id."
        )
    return corpus, meta, coverage
