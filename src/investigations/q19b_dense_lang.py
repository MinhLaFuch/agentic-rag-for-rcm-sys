"""Q19b: language-mismatch test for dense retrieval — NO translation needed.

campaign_005 request texts are Vietnamese; doc vectors + all-MiniLM-L6-v2 are
English. Arm 'raw' already ~0 recall. New arms use the ENGLISH catalog payload
hidden inside each request:
  seedtitle : title of seed_item_id (English catalog text)
  seedcat   : seedtitle + " Categories: <request category>."
If these recover targets that 'raw' misses -> language mismatch confirmed.

Same doc vectors as q19_dense_format.py. .venv python. Output q19b_dense_lang.json
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl"
CORPUS = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
VEC_DIR = ROOT / "experiments/embedding_builds/multi_domain_full"
OUT = Path(__file__).parent / "q19b_dense_lang.json"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
KS = (50, 200, 1000)


def main():
    reqs = [json.loads(l) for l in REQ.read_text(encoding="utf-8").splitlines()]
    item2id = json.loads((ROOT / "resource/mapped/multi_domain/item2id.json").read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}

    # titles for seed items
    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    seed_ids = sorted({r["seed_item_id"] for r in reqs if r.get("seed_item_id")})
    ph = ",".join("?" for _ in seed_ids)
    titles = {iid: t for iid, t in conn.execute(
        f"SELECT item_id, title FROM main.items WHERE item_id IN ({ph})", seed_ids)}
    print(f"seed titles: {len(titles)}/{len(seed_ids)}")

    queries = []
    for r in reqs:
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = json.loads(tg)
        tgt_ids = [id2item[int(t)] for t in (tg or []) if int(t) in id2item]
        sid = r.get("seed_item_id")
        if tgt_ids and sid in titles:
            queries.append({"request_id": r["request_id"], "kind": r["kind"],
                            "title": titles[sid], "category": r.get("category"),
                            "targets": tgt_ids})
    print(f"queries: {len(queries)}")

    vecs = np.load(VEC_DIR / "vectors.npy", mmap_mode="r")
    doc_ids = np.load(VEC_DIR / "item_ids.npy", allow_pickle=True)
    id2row = {str(i): r for r, i in enumerate(doc_ids)}
    for q in queries:
        q["tgt_rows"] = sorted({id2row[t] for t in q["targets"] if t in id2row})
    queries = [q for q in queries if q["tgt_rows"]]
    print(f"with in-catalog targets: {len(queries)}")

    from sentence_transformers import SentenceTransformer
    import torch
    enc = SentenceTransformer(MODEL, device="cuda")
    V = torch.from_numpy(np.asarray(vecs, dtype=np.float32)).to("cuda")
    V = torch.nn.functional.normalize(V, dim=1)

    results = {}
    for kind in ("seedtitle", "seedcat"):
        texts = []
        for q in queries:
            t = q["title"]
            if kind == "seedcat" and q.get("category") not in (None, "None"):
                t = f"{t} Categories: {q['category']}."
            texts.append(t)
        e = enc.encode(texts, convert_to_tensor=True, normalize_embeddings=True).to("cuda")
        scores = e @ V.T
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

    OUT.write_text(json.dumps({"n_queries": len(queries), "arms": results}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
