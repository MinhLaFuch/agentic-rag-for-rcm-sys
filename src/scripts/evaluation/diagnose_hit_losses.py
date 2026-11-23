"""CLI wrapper for package.evaluation.recommender.analysis.diagnose_hit_losses.

Attributes target losses of the saved CF baseline (``cf_1``) under the
``cf_bm25_rrf`` RRF variant in ``records.jsonl`` files produced by
``sparse_seed_eval.py`` / ``sparse_data_diagnostic.py`` runs
(``experiments/sparse_content_eval/exp_*/records.jsonl``).

Record list fields are stored as Python-literal strings and are parsed with
``ast.literal_eval`` before analysis.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.evaluation.recommender.analysis.diagnose_hit_losses import (
    diagnose_hit_losses,
)


def _parse_value(value: Any) -> Any:
    """Parse stringified Python literals (lists/dicts) back to objects."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text in ("None", "nan"):
        return None if text == "None" else value
    if text[0] in "[{":
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return value
    return value


def _parse_record(row: dict[str, Any]) -> dict[str, Any]:
    parsed = {}
    for key, value in row.items():
        if key == "source_candidates" and isinstance(value, str):
            try:
                parsed[key] = {
                    k: _parse_value(v) for k, v in ast.literal_eval(value).items()
                }
            except (ValueError, SyntaxError):
                parsed[key] = value
            continue
        parsed[key] = _parse_value(value)
    return parsed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--records",
        required=True,
        help="Path to records.jsonl (e.g. experiments/sparse_content_eval/exp_002/records.jsonl)",
    )
    ap.add_argument("--domain", action="append", help="Domain(s); default: all (multi_domain)")
    ap.add_argument("--output", default=None, help="Output JSON path (default: <records_dir>/hit_loss_diagnosis.json)")
    args = ap.parse_args()

    records_path = Path(args.records)
    if not records_path.exists():
        raise FileNotFoundError(f"records file not found: {records_path}")

    records = []
    skipped_variants = 0
    with open(records_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # diagnose_hit_losses requires exactly the cf_1 / cf_bm25_rrf pair;
            # records files may carry extra variants (e.g. cf_bm25_history).
            if row.get("variant") not in ("cf_1", "cf_bm25_rrf"):
                skipped_variants += 1
                continue
            records.append(_parse_record(row))
    if skipped_variants:
        print(f"skipped {skipped_variants} records with non-paired variants")
    if not records:
        raise ValueError(f"no cf_1/cf_bm25_rrf records in {records_path}")

    paths = get_data_paths(domains=args.domain)
    _user2id, item2id = load_mappings(paths.mapped_dir)

    result = diagnose_hit_losses(records, item2id)

    output_path = (
        Path(args.output)
        if args.output
        else records_path.parent / "hit_loss_diagnosis.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Hit-loss diagnosis saved to: {output_path}")
    print(f"counts: {result['counts']}")


if __name__ == "__main__":
    main()
