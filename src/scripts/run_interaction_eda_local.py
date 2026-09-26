import argparse

from package.data.eda import compute_interaction_stats_streaming, print_streaming_stats_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", required=True, help="Đường dẫn tới file review_Video_Games.jsonl.gz"
    )
    args = parser.parse_args()

    print(f"Reading {args.path} ...")
    stats = compute_interaction_stats_streaming(args.path)
    print_streaming_stats_report(stats)


if __name__ == "__main__":
    main()
