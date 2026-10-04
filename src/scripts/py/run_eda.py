"""
EDA interaction trên review thô đã tải về (resource/raw/<Domain>.jsonl.gz), đọc theo dòng.

    PYTHONPATH=. python scripts/py/run_eda.py                      # mọi domain trong data.yaml
    PYTHONPATH=. python scripts/py/run_eda.py --domain Video_Games
    PYTHONPATH=. python scripts/py/run_eda.py --path /duong/dan/review_Video_Games.jsonl.gz
"""

import argparse

from package.config import get_data_paths, get_domains
from package.data.eda import compute_interaction_stats_streaming, print_streaming_stats_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain", action="append", help="Lặp lại cho nhiều domain (mặc định: tất cả trong data.yaml)."
    )
    parser.add_argument("--path", help="Chạy thẳng trên một file .jsonl.gz, bỏ qua --domain.")
    args = parser.parse_args()

    if args.path:
        targets = [(args.path, args.path)]
    else:
        paths = get_data_paths()
        targets = [(d, paths.review_path(d)) for d in (args.domain or get_domains())]

    for name, path in targets:
        print(f"\n##### {name}: reading {path} ...")
        print_streaming_stats_report(compute_interaction_stats_streaming(str(path)))


if __name__ == "__main__":
    main()
