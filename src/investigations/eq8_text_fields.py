"""E-Q8 remainder: text-field coverage audit (read-only).

Corpus `items` columns: title, store, price, average_rating, rating_number,
main_category — NO description, NO features. Categories live in
item_categories. Embeddings use title+store+main_category+categories only.

Measures:
  A) corpus side (sqlite): title NULL/empty %, title length distribution
     (chars + whitespace-token count), store empty %, per domain.
  B) raw meta side (rescan meta_*.jsonl.gz): coverage of `description`
     (non-empty text), `features` (non-empty list), `store`, `title`
     per domain -> shows what text EXISTS but is unused by corpus/embeddings.

Outputs: investigations/eq8_text_fields.json (+ eq8_meta_text.parquet)
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
META = {
    "Electronics": "resource/raw/meta_Electronics.jsonl.gz",
    "Toys_and_Games": "resource/raw/meta_Toys_and_Games.jsonl.gz",
    "Video_Games": "resource/raw/meta_Video_Games.jsonl.gz",
}
OUT_JSON = Path(__file__).parent / "eq8_text_fields.json"
OUT_PARQUET = Path(__file__).parent / "eq8_meta_text.parquet"


def corpus_side(conn) -> dict:
    rows = conn.execute(
        "SELECT domain, title, store, main_category FROM items").fetchall()
    df = pd.DataFrame(rows, columns=["domain", "title", "store", "main_category"])
    out = {}
    for dom, g in df.groupby("domain"):
        t = g.title.fillna("").astype(str)
        tokens = t.str.split().str.len()
        out[dom] = {
            "n": int(len(g)),
            "title_empty_pct": round(100 * (t.str.strip() == "").mean(), 3),
            "title_chars_p10": float(t.str.len().quantile(0.1)),
            "title_chars_median": float(t.str.len().median()),
            "title_chars_p90": float(t.str.len().quantile(0.9)),
            "title_tokens_p10": float(tokens.quantile(0.1)),
            "title_tokens_median": float(tokens.median()),
            "title_tokens_p90": float(tokens.quantile(0.9)),
            "title_tokens_gt20_pct": round(100 * (tokens > 20).mean(), 2),
            "store_empty_pct": round(
                100 * (g.store.fillna("").astype(str).str.strip() == "").mean(), 3),
            "main_category_empty_pct": round(
                100 * (g.main_category.fillna("").astype(str).str.strip() == "").mean(), 3),
        }
    return out


def meta_side() -> tuple[pd.DataFrame, dict]:
    rows = []
    for domain, path in META.items():
        n = 0
        with gzip.open(ROOT / path, "rt", encoding="utf-8") as f:
            for line in f:
                n += 1
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                desc = r.get("description")
                # description is a LIST of strings in this scrape
                if isinstance(desc, list):
                    desc_text = " ".join(str(x) for x in desc).strip()
                elif isinstance(desc, str):
                    desc_text = desc.strip()
                else:
                    desc_text = ""
                feats = r.get("features")
                rows.append((
                    domain, r.get("parent_asin"),
                    bool(desc_text),
                    len(desc_text),
                    isinstance(feats, list) and len(feats) > 0,
                    (isinstance(feats, list) and len(feats)) or 0,
                    isinstance(r.get("store"), str) and bool(str(r.get("store")).strip()),
                    isinstance(r.get("title"), str) and bool(str(r.get("title")).strip()),
                ))
        print(f"{domain}: {n:,} rows", flush=True)
    df = pd.DataFrame(rows, columns=[
        "domain", "parent_asin", "has_description", "desc_chars",
        "has_features", "n_features", "has_store", "has_title"])
    df.to_parquet(OUT_PARQUET, index=False)
    stats = {}
    for dom, g in df.groupby("domain"):
        dc = g.loc[g.has_description, "desc_chars"]
        stats[dom] = {
            "n": int(len(g)),
            "description_coverage_pct": round(100 * g.has_description.mean(), 2),
            "desc_chars_median": float(dc.median()) if len(dc) else None,
            "desc_chars_p90": float(dc.quantile(0.9)) if len(dc) else None,
            "features_coverage_pct": round(100 * g.has_features.mean(), 2),
            "features_count_median": float(g.loc[g.has_features, "n_features"].median())
                if g.has_features.any() else None,
            "store_coverage_pct": round(100 * g.has_store.mean(), 2),
            "title_coverage_pct": round(100 * g.has_title.mean(), 2),
        }
    return df, stats


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    corpus = corpus_side(conn)
    print("corpus side done", flush=True)
    _, meta_stats = meta_side()
    report = {
        "method": "corpus items table direct scan (title/store/main_category); "
                  "raw meta rescan for description/features/store/title coverage",
        "note": "corpus has NO description/features columns; embeddings use "
                "title+store+main_category+categories only -> description/features "
                "exist in raw meta but are unused everywhere",
        "corpus": corpus, "raw_meta": meta_stats,
        "examples": [],
    }
    # examples: items with rich description from parquet
    df = pd.read_parquet(OUT_PARQUET)
    rich = df[df.has_description & (df.desc_chars > 200)].head(5)
    report["examples"] = rich[["domain", "parent_asin", "desc_chars",
                                "n_features"]].to_dict("records")
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")
    print("wrote", OUT_JSON, flush=True)


if __name__ == "__main__":
    main()
