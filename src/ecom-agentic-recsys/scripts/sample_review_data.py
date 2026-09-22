
from __future__ import annotations

import argparse
import gzip
import random


def sample_jsonl_gz(input_path: str, output_path: str, sample_size: int, seed: int = 42) -> None:
    random.seed(seed)

    # Reservoir sampling — không cần load toàn bộ file vào RAM.
    reservoir: list[str] = []
    with gzip.open(input_path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < sample_size:
                reservoir.append(line)
            else:
                j = random.randint(0, i)
                if j < sample_size:
                    reservoir[j] = line

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        f.writelines(reservoir)

    print(f"Sampled {len(reservoir)} lines -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sample-size", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    sample_jsonl_gz(args.input, args.output, args.sample_size, args.seed)
