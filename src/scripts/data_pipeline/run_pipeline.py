"""Run the full data pipeline or selected stages."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from package.config import get_data_paths, get_domains, load_config
from package.data.pipeline import build_artifacts, clean_domain, map_split, merge_filter_domains


def _parse_stages(arg: str) -> list[int]:
    """Parse --stages argument into sorted list of stage numbers."""
    if arg == "all":
        return [1, 2, 3, 4]
    try:
        stages = []
        for part in arg.split(","):
            stages.append(int(part.strip()))
        return sorted(set(stages))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--stages must be 'all' or comma-separated integers (e.g., '1,2' or '2,3')"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stages",
        default="all",
        help="Stages to run: 'all' (default), '1', '2', '3', '4', or comma-separated (e.g., '1,2', '2,3'). "
             "Stages always run in order 1→2→3→4 regardless of input order.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        help="Domain name(s) (repeat for multiple). Default: all domains in domains.yaml. "
             "Used for stage 1 (run per domain) and stage 2.",
    )
    parser.add_argument("--tag", help="Run tag (default: tag from run_tag.yaml). Used for stages 2 and 3.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument(
        "--cold-start-report",
        action="store_true",
        help="Print cold-start statistics for stage 2 (expensive).",
    )
    parser.add_argument(
        "--review-path",
        help="Override review path for stage 1 (only valid with --domain single and --stages 1).",
    )
    parser.add_argument(
        "--skip-corpus",
        action="store_true",
        help="Skip corpus building in stage 4.",
    )
    parser.add_argument(
        "--skip-item-knn",
        action="store_true",
        help="Skip ItemKNN building in stage 4.",
    )
    args = parser.parse_args()

    stages = _parse_stages(args.stages)
    domains = args.domain or get_domains()
    tag = args.tag or load_config("path/run_tag")["tag"]

    # Validate --review-path constraint
    if args.review_path:
        if len(domains) != 1 or 1 not in stages:
            parser.error("--review-path is only valid with a single domain and stage 1")

    paths = get_data_paths(tag)
    # Splits cho stage 4 ItemKNN lấy từ split.item_knn_splits (configs/data/split.yaml).
    eval_on_list = [str(s) for s in load_config("data/split")["split"]["item_knn_splits"]]

    # Fail-fast checks before running any stage
    errors = []
    if 1 in stages:
        for domain in domains:
            review_path = Path(args.review_path) if args.review_path else paths.review_path(domain)
            if not review_path.exists():
                errors.append(f"Stage 1 input missing: {review_path} (domain '{domain}')")
            output_path = paths.cleaned_dir / domain / "interactions.parquet"
            if output_path.exists() and not args.force:
                errors.append(f"Stage 1 output exists (use --force): {output_path}")

    if 2 in stages:
        for domain in domains:
            cleaned_path = paths.cleaned_path(domain)
            if not cleaned_path.exists():
                errors.append(f"Stage 2 input missing: {cleaned_path} (domain '{domain}')")
        if paths.filtered_path.exists() and not args.force:
            errors.append(f"Stage 2 output exists (use --force): {paths.filtered_path}")

    if 3 in stages:
        if not paths.filtered_path.exists():
            # Only error if stage 2 is not also running (which would create it)
            if 2 not in stages:
                errors.append(f"Stage 3 input missing: {paths.filtered_path}")
        for split_name in ["train", "validation", "test"]:
            split_path = paths.split_path(split_name)
            if split_path.exists() and not args.force:
                errors.append(f"Stage 3 output exists (use --force): {split_path}")

    if 4 in stages:
        if not paths.mapped_dir.exists():
            # Only error if stage 3 is not also running (which would create it)
            if 3 not in stages:
                errors.append(f"Stage 4 input missing: {paths.mapped_dir}")
        if not args.skip_corpus and paths.corpus_path.exists() and not args.force:
            errors.append(f"Stage 4 output exists (use --force): {paths.corpus_path}")
        if not args.skip_item_knn:
            for split in eval_on_list:
                item_knn_path = paths.item_knn_path(split)
                if item_knn_path.exists() and not args.force:
                    errors.append(f"Stage 4 output exists (use --force): {item_knn_path}")

    if errors:
        print("Pre-check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Run stages
    overall_start = time.time()
    stage_times = {}

    try:
        if 1 in stages:
            stage_start = time.time()
            for domain in domains:
                clean_domain(
                    paths,
                    domain,
                    review_path=Path(args.review_path) if args.review_path else None,
                    force=args.force,
                )
            stage_times[1] = time.time() - stage_start

        if 2 in stages:
            stage_start = time.time()
            merge_filter_domains(paths, domains, force=args.force, cold_start_report=args.cold_start_report)
            stage_times[2] = time.time() - stage_start

        if 3 in stages:
            stage_start = time.time()
            map_split(paths, force=args.force)
            stage_times[3] = time.time() - stage_start

        if 4 in stages:
            stage_start = time.time()
            build_artifacts(
                paths,
                domains=domains,
                eval_on=eval_on_list,
                skip_corpus=args.skip_corpus,
                skip_item_knn=args.skip_item_knn,
                force=args.force,
            )
            stage_times[4] = time.time() - stage_start

    except SystemExit:
        # Re-raise with stage info
        print(f"\nPipeline stopped during stage {stages[len(stage_times)] if stage_times else 1}", file=sys.stderr)
        raise

    overall_time = time.time() - overall_start

    print("\n=== PIPELINE SUMMARY ===")
    print(f"Stages run: {stages}")
    for stage in stages:
        if stage in stage_times:
            print(f"  Stage {stage}: {stage_times[stage]:.2f}s")
    print(f"Total time: {overall_time:.2f}s")
    print("=== DONE ===")


if __name__ == "__main__":
    main()
