"""Dựng ItemCorpus từ meta_<Domain>.jsonl.gz, chỉ giữ item có trong mapping, và kiểm tra độ phủ."""

from __future__ import annotations

from itertools import islice

import pandas as pd

from package.data import namespaced_item_id
from package.data.loader import load_item_metadata

from .corpus import ItemCorpus

COVERAGE_SAMPLE = 5000  # số item mapping đầu tiên dùng để ước lượng độ phủ metadata


def build_corpus(
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    namespaced: bool,
    min_coverage: float,
) -> tuple[ItemCorpus, pd.DataFrame, float]:
    """
    meta_files: [(domain, đường dẫn meta)]. namespaced: key trong item2id có dạng 'Domain::asin' hay asin thuần.
    min_coverage: tỉ lệ tối thiểu item mapping phải có metadata, dưới mức này ném ValueError
    (thường do sai file meta hoặc sai định dạng id).
    Trả về (corpus, bảng metadata đã lọc, độ phủ ước lượng) — bảng này còn dùng để dựng text cho query mô phỏng.
    """

    def in_mapping(domain: str, asin: str) -> bool:
        return (namespaced_item_id(domain, asin) if namespaced else asin) in item2id

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
