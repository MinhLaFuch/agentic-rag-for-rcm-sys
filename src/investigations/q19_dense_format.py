"""Q19: dense-vs-BM25 gap — is it a query/doc FORMAT mismatch?

Docs were embedded as field-lines: "Title. Store: X. Main: Y. Categories: a, b."
Queries are raw NL text. Hypothesis: wrapping/augmenting the query to mimic
doc structure improves dense recall.

Arms (same encoder, same doc vectors — NO re-embed):
  raw      : request text as-is (status quo)
  cataug   : text + " Categories: <request category>" when request has one
  docstyle : "Product: <text>." pseudo-doc wrapper

Qrels: held-out target item_ids from campaign_005 requests (text-bearing kinds).
Metric: recall@{50,200,1000} of ANY target in top-k dense neighbors.
BM25 reference via SearchTool on the same queries.

Run with .venv python (sentence-transformers + torch).
Output: investigations/q19_dense_format.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl"
VEC_DIR = ROOT / "experiments/embedding_builds/multi_domain_full"
OUT = Path(__file__).parent / "q19_dense_format.json"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
KS = (50, 200, 1000)


def main():
    reqs = [json.loads(l) for l in REQ.read_text(encoding="utf-8").splitlines()]
    item2id = json.loads((ROOT / "resource/mapped/multi_domain/item2id.json").read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}

    # queries: requests with non-trivial text and >=1 target
    queries = []
    for r in reqs:
        text = (r.get("text") or "").strip()
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = json.loads(tg)
        tgt_ids = [id2item[int(t)] for t in (tg or []) if int(t) in id2item]
        if len(text) >= 10 and tgt_ids:
            queries.append({
                "request_id": r["request_id"], "kind": r["kind"],
                "text": text, "category": r.get("category"),
                "targets": tgt_ids,
            })
    print(f"queries with targets: {len(queries)}")

    # doc vectors (memmap) + id->row
    vecs = np.load(VEC_DIR / "vectors.npy", mmap_mode="r")
    doc_ids = np.load(VEC_DIR / "item_ids.npy", allow_pickle=True)
    id2row = {str(i): r for r, i in enumerate(doc_ids)}
    print(f"docs: {len(doc_ids):,} dim={vecs.shape[1]}")
    tgt_rows = []
    for q in queries:
        q["tgt_rows"] = sorted({id2row[t] for t in q["targets"] if t in id2row})
    queries = [q for q in queries if q["tgt_rows"]]
    print(f"queries with in-catalog targets: {len(queries)}")

    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer(MODEL, device="cuda")

    def arm_texts(kind):
        out = []
        for q in queries:
            t = q["text"]
            if kind == "cataug" and q.get("category") not in (None, "None"):
                t = f"{t} Categories: {q['category']}."
            elif kind == "docstyle":
                t = f"Product: {t}."
            out.append(t)
        return out

    # encode all arms, score in chunks on GPU
    import torch
    V = torch.from_numpy(np.asarray(vecs, dtype=np.float32)).to("cuda")
    V = torch.nn.functional.normalize(V, dim=1)
    results = {}
    for kind in ("raw", "cataug", "docstyle"):
        texts = arm_texts(kind)
        e = enc.encode(texts, convert_to_tensor=True, normalize_embeddings=True).to("cuda")
        scores = e @ V.T  # (nq, ndocs)
        top = torch.topk(scores, k=max(KS), dim=1).indices.cpu().numpy()
        rec = {k: 0 for k in KS}
        for i, q in enumerate(queries):
            for k in KS:
                if any(r in set(top[i, :k].tolist()) for r in q["tgt_rows"]):
                    rec[k] += 1
        n = len(queries)
        results[kind] = {f"recall@{k}": round(rec[k] / n, 4) for k in KS}
        print(kind, results[kind], flush=True)
        del scores, top, e
        torch.cuda.empty_cache()

    OUT.write_text(json.dumps({"n_queries": len(queries), "ks": KS, "arms": results}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
