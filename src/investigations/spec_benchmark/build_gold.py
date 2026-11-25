"""Build gold Spec JSONL for the 152 campaign requests (offline, no LLM).

Uses spec_from_request with a sqlite-backed corpus shim (same .select contract
as ItemCorpus) so similar seeds get inferred category slots and cold_text /
exclusion / constrained get oracle-flagged fields.

Output: gold_specs.jsonl — one row per request:
  {request_id, kind, segment, text, spec: {...}, oracle}
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from package.evaluation.requests._dataclass import AgentRequest  # noqa: E402
from package.evaluation.spec import spec_from_request  # noqa: E402

CORPUS = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
RUN = Path("experiments/agent_eval/filter_ab/exp_2_baseline/run_1")
OUT = Path("investigations/spec_benchmark/gold_specs.jsonl")
VIEW = Path("investigations/distill_phase2/item_spec_view.parquet")
COARSE_MIN = 1000


class SqliteCorpusShim:
    """Minimal .select(sql, params, max_rows) -> (rows, truncated) over the corpus DB."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def select(self, sql, params=(), max_rows=1000):
        cur = self._conn.execute(sql, tuple(params))
        cols = [d[0] for d in cur.description]
        fetched = cur.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = [dict(zip(cols, r)) for r in fetched[:max_rows]]
        return rows, truncated


def seq_of(conn: sqlite3.Connection, item_id: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT category FROM item_categories WHERE item_id = ? ORDER BY rowid", (item_id,)
        )
    ]


def coarse_and_ancestor(seq: list[str], counts: dict[str, int]):
    """Same leaf-up rule as spec._schema.coarse_label + parent (depth d-1)."""
    from package.evaluation.spec import coarse_label

    seq = [s for s in seq if s]
    coarse = coarse_label(seq, counts, COARSE_MIN)
    if coarse is None:
        return None, None
    idx = len(seq) - 1 - seq[::-1].index(coarse)
    return coarse, (seq[idx - 1] if idx > 0 else None)


def gold_category_levels(req: dict, conn, counts, idx2item, view_indexed):
    """(gold_coarse, gold_ancestor) for cold_text/similar; (None, None) else.

    cold_text -> first held-out target's sequence (oracle, consistent with the
    request.category provenance). similar -> seed item (clean).
    """
    kind = req["kind"]
    if kind == "cold_text":
        targets = req.get("targets") or []
        item_id = idx2item.get(targets[0]) if targets else None
    elif kind == "similar":
        item_id = req.get("seed_item_id")
    else:
        return None, None
    if not item_id:
        return None, None
    coarse, ancestor = coarse_and_ancestor(seq_of(conn, item_id), counts)
    if coarse is None:
        try:
            row = view_indexed.loc[item_id]
            coarse, ancestor = row["coarse"], row["ancestor"]
        except KeyError:
            coarse, ancestor = None, None
    return coarse, ancestor


def main() -> None:
    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    corpus = SqliteCorpusShim(conn)

    # taxonomy = item_categories labels + items.main_category values (gold coarse
    # may resolve to a main_category fallback, which is NOT an item_categories label)
    taxonomy = {r[0] for r in conn.execute("SELECT DISTINCT category FROM item_categories")}
    taxonomy |= {r[0] for r in conn.execute("SELECT DISTINCT main_category FROM items WHERE main_category IS NOT NULL")}
    print(f"taxonomy labels: {len(taxonomy)}", flush=True)

    counts = {
        r[0]: int(r[1])
        for r in conn.execute("SELECT category, COUNT(*) FROM item_categories GROUP BY category")
    }
    import json as _json
    i2i = _json.load(open("resource/mapped/multi_domain/item2id.json", encoding="utf-8"))
    idx2item = {v: k for k, v in i2i.items()}
    import pandas as pd
    view_indexed = pd.read_parquet(VIEW).set_index("item_id", drop=False)

    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for line in open(RUN / "requests.jsonl", encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            req = AgentRequest(
                request_id=r["request_id"], kind=r["kind"], segment=r.get("segment", ""),
                text=r["text"], user_id=r.get("user_id"), user_idx=r.get("user_idx"),
                seed_item_id=r.get("seed_item_id"), targets=r.get("targets") or [],
                price_max=r.get("price_max"), category=r.get("category"),
                excluded_item_ids=r.get("excluded_item_ids") or [],
                excluded_categories=r.get("excluded_categories") or [],
                oracle=bool(r.get("oracle")),
            )
            spec = spec_from_request(req, corpus=corpus, taxonomy=taxonomy)
            gold_coarse, gold_ancestor = gold_category_levels(
                r, conn, counts, idx2item, view_indexed
            )
            row = {
                "request_id": r["request_id"],
                "kind": r["kind"],
                "segment": r.get("segment"),
                "text": r["text"],
                "spec": spec.model_dump(mode="json"),
                "gold_coarse": gold_coarse,
                "gold_ancestor": gold_ancestor,
                "oracle": spec.oracle,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} gold specs -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
