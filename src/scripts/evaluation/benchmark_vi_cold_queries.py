"""Track B (Vietnamese -> English catalog) benchmark for cold-start shopping queries.

Evaluates realistic Vietnamese shopping queries (with and without diacritics) against the
English 2.64M-item catalog under exact historical_static_catalog eligibility, comparing:
  1. raw_bm25       (Vietnamese query directly into BM25 — baseline failure mode)
  2. raw_dense      (Vietnamese query directly into MiniLM — monolingual dense baseline)
  3. vi_bridge_bm25 (VietnameseQueryTranslator -> SparseBM25)
  4. vi_bridge_dense (VietnameseQueryTranslator -> MiniLM HNSW SQ8)
  5. vi_bridge_hybrid (VietnameseQueryTranslator -> BM25 + Dense RRF)

Uses deterministic intent templates covering Electronics, Video_Games, and Toys_and_Games,
paired with eligible validation-catalog relevance definitions (domain + required English
concept terms in title/categories) so every query has transparent, inspectable ground truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

import numpy as np

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.split import load_splits
from package.embeddings import SparseBM25Index, TextEncoder
from package.evaluation.recommender.config import select_fit_target
from package.tools.retrieval.fuse_candidates import fuse_candidates
from package.tools.retrieval.vietnamese_query_translator import VietnameseQueryTranslator
from package.utils import ensure_utf8_stdout
from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
from scripts.evaluation.ann_validation import build_ann_search


# Curated Vietnamese shopping intents across all 3 catalog domains (with & without diacritics)
# paired with transparent relevance criteria (domain + all required concept groups present in title/category).
VI_SCENARIOS: list[dict] = [
    {"id": "vi_01", "domain": "Electronics", "vi": "tai nghe chống ồn bluetooth tốt", "vi_nodiac": "tai nghe chong on bluetooth tot", "must": [("headphone", "earbud", "headset"), ("noise", "cancel"), ("bluetooth", "wireless")]},
    {"id": "vi_02", "domain": "Electronics", "vi": "tai nghe chụp tai không dây nghe nhạc", "vi_nodiac": "tai nghe chup tai khong day nghe nhac", "must": [("headphone", "headset"), ("wireless", "bluetooth"), ("over", "ear")]},
    {"id": "vi_03", "domain": "Electronics", "vi": "bàn phím cơ yên tĩnh làm văn phòng", "vi_nodiac": "ban phim co yen tinh lam van phong", "must": [("keyboard",), ("mechanical",)]},
    {"id": "vi_04", "domain": "Electronics", "vi": "bàn phím không dây nhỏ gọn di động", "vi_nodiac": "ban phim khong day nho gon di dong", "must": [("keyboard",), ("wireless", "bluetooth"), ("compact", "mini", "portable")]},
    {"id": "vi_05", "domain": "Electronics", "vi": "chuột công thái học không dây văn phòng", "vi_nodiac": "chuot cong thai hoc khong day van phong", "must": [("mouse",), ("ergonomic",), ("wireless", "bluetooth")]},
    {"id": "vi_06", "domain": "Electronics", "vi": "chuột gaming không dây logitech", "vi_nodiac": "chuot gaming khong day logitech", "must": [("mouse",), ("gaming",), ("logitech",)]},
    {"id": "vi_07", "domain": "Electronics", "vi": "loa bluetooth di động chống nước", "vi_nodiac": "loa bluetooth di dong chong nuoc", "must": [("speaker",), ("bluetooth", "wireless"), ("waterproof", "portable")]},
    {"id": "vi_08", "domain": "Electronics", "vi": "ổ cứng di động ssd 1tb usb-c", "vi_nodiac": "o cung di dong ssd 1tb usb-c", "must": [("ssd", "drive"), ("portable", "external")]},
    {"id": "vi_09", "domain": "Electronics", "vi": "thẻ nhớ microsd cho máy ảnh", "vi_nodiac": "the nho microsd cho may anh", "must": [("microsd", "memory"), ("card",)]},
    {"id": "vi_10", "domain": "Electronics", "vi": "cáp sạc nhanh usb-c bền bỉ", "vi_nodiac": "cap sac nhanh usb-c ben bi", "must": [("cable",), ("usb-c", "usb"), ("charging", "charger", "fast")]},
    {"id": "vi_11", "domain": "Electronics", "vi": "sạc dự phòng nhỏ gọn sạc nhanh", "vi_nodiac": "sac du phong nho gon sac nhanh", "must": [("power",), ("bank", "charger"), ("portable",)]},
    {"id": "vi_12", "domain": "Electronics", "vi": "màn hình máy tính 4k gaming", "vi_nodiac": "man hinh may tinh 4k gaming", "must": [("monitor",), ("4k", "gaming")]},
    {"id": "vi_13", "domain": "Electronics", "vi": "chân máy ảnh du lịch nhỏ gọn", "vi_nodiac": "chan may anh du lich nho gon", "must": [("tripod",), ("camera",)]},
    {"id": "vi_14", "domain": "Electronics", "vi": "bộ phát wifi không dây tốc độ cao", "vi_nodiac": "bo phat wifi khong day toc do cao", "must": [("router",), ("wifi", "wireless")]},
    {"id": "vi_15", "domain": "Electronics", "vi": "micro thu âm usb cho máy tính", "vi_nodiac": "micro thu am usb cho may tinh", "must": [("microphone",), ("usb",)]},
    {"id": "vi_16", "domain": "Electronics", "vi": "túi chống sốc cho máy tính xách tay", "vi_nodiac": "tui chong soc cho may tinh xach tay", "must": [("laptop",), ("sleeve", "case", "bag")]},
    {"id": "vi_17", "domain": "Electronics", "vi": "giá đỡ điện thoại để bàn", "vi_nodiac": "gia do dien thoai de ban", "must": [("phone",), ("stand", "holder", "mount")]},
    {"id": "vi_18", "domain": "Electronics", "vi": "pin sạc aa kèm bộ sạc", "vi_nodiac": "pin sac aa kem bo sac", "must": [("battery", "batteries"), ("rechargeable",), ("charger",)]},
    {"id": "vi_19", "domain": "Video_Games", "vi": "tai nghe gaming có micro cho ps5", "vi_nodiac": "tai nghe gaming co micro cho ps5", "must": [("headset", "headphone"), ("gaming",)]},
    {"id": "vi_20", "domain": "Video_Games", "vi": "tay cầm chơi game không dây pc", "vi_nodiac": "tay cam choi game khong day pc", "must": [("controller", "gamepad"), ("wireless", "bluetooth")]},
    {"id": "vi_21", "domain": "Video_Games", "vi": "tay cầm game nintendo switch", "vi_nodiac": "tay cam game nintendo switch", "must": [("controller",), ("switch", "nintendo")]},
    {"id": "vi_22", "domain": "Video_Games", "vi": "bàn phím gaming có đèn rgb", "vi_nodiac": "ban phim gaming co den rgb", "must": [("keyboard",), ("gaming",), ("rgb",)]},
    {"id": "vi_23", "domain": "Video_Games", "vi": "túi chống sốc cho nintendo switch", "vi_nodiac": "tui chong soc cho nintendo switch", "must": [("case",), ("switch", "nintendo")]},
    {"id": "vi_24", "domain": "Video_Games", "vi": "miếng dán màn hình nintendo switch", "vi_nodiac": "mieng dan man hinh nintendo switch", "must": [("screen",), ("protector",), ("switch",)]},
    {"id": "vi_25", "domain": "Video_Games", "vi": "bộ sạc tay cầm chơi game ps4", "vi_nodiac": "bo sac tay cam choi game ps4", "must": [("charger", "charging"), ("controller",), ("ps4", "playstation")]},
    {"id": "vi_26", "domain": "Video_Games", "vi": "đĩa game phiêu lưu nintendo switch", "vi_nodiac": "dia game phieu luu nintendo switch", "must": [("switch", "nintendo"), ("game",)]},
    {"id": "vi_27", "domain": "Toys_and_Games", "vi": "đồ chơi lắp ráp lego cho bé trai", "vi_nodiac": "do choi lap rap lego cho be trai", "must": [("lego",), ("building", "set", "toy")]},
    {"id": "vi_28", "domain": "Toys_and_Games", "vi": "đồ chơi xếp hình bằng gỗ cho trẻ em", "vi_nodiac": "do choi xep hinh bang go cho tre em", "must": [("puzzle", "blocks"), ("kids", "toddler", "toy", "wood", "wooden")]},
    {"id": "vi_29", "domain": "Toys_and_Games", "vi": "gấu bông mềm mại quà tặng cho bé", "vi_nodiac": "gau bong mem mai qua tang cho be", "must": [("plush", "stuffed"), ("toy", "bear", "animal")]},
    {"id": "vi_30", "domain": "Toys_and_Games", "vi": "xe điều khiển từ xa địa hình cho trẻ em", "vi_nodiac": "xe dieu khien tu xa dia hinh cho tre em", "must": [("remote", "rc"), ("car", "truck", "vehicle")]},
    {"id": "vi_31", "domain": "Toys_and_Games", "vi": "trò chơi gia đình board game chiến thuật", "vi_nodiac": "tro choi gia dinh board game chien thuat", "must": [("board", "card"), ("game",), ("family",)]},
    {"id": "vi_32", "domain": "Toys_and_Games", "vi": "bộ cờ vua bằng gỗ cổ điển", "vi_nodiac": "bo co vua bang go co dien", "must": [("chess",), ("set", "board", "game")]},
    {"id": "vi_33", "domain": "Toys_and_Games", "vi": "búp bê thời trang cho bé gái", "vi_nodiac": "bup be thoi trang cho be gai", "must": [("doll",), ("girl", "girls", "playset", "toy", "fashion")]},
    {"id": "vi_34", "domain": "Toys_and_Games", "vi": "đồ chơi giáo dục stem cho trẻ em", "vi_nodiac": "do choi giao duc stem cho tre em", "must": [("stem", "educational", "learning"), ("toy", "kit", "kids")]},
    {"id": "vi_35", "domain": "Toys_and_Games", "vi": "đồ chơi nhà tắm phun nước cho bé", "vi_nodiac": "do choi nha tam phun nuoc cho be", "must": [("bath",), ("toy", "water")]},
    {"id": "vi_36", "domain": "Toys_and_Games", "vi": "mô hình siêu anh hùng sưu tầm", "vi_nodiac": "mo hinh sieu anh hung suu tam", "must": [("figure", "collectible"), ("action", "toy", "model")]},
    {"id": "vi_37", "domain": "Toys_and_Games", "vi": "bộ bài chơi cùng gia đình bạn bè", "vi_nodiac": "bo bai choi cung gia dinh ban be", "must": [("card", "cards"), ("game",)]},
    {"id": "vi_38", "domain": "Toys_and_Games", "vi": "xe mô hình ô tô kim loại cho bé", "vi_nodiac": "xe mo hinh o to kim loai cho be", "must": [("diecast", "car", "vehicle"), ("toy", "model")]},
    {"id": "vi_39", "domain": "Electronics", "vi": "đồng hồ thông minh chống nước theo dõi sức khỏe", "vi_nodiac": "dong ho thong minh chong nuoc theo doi suc khoe", "must": [("smartwatch", "watch"), ("waterproof", "fitness", "smart")]},
    {"id": "vi_40", "domain": "Electronics", "vi": "đèn pin siêu sáng chống nước đi dã ngoại", "vi_nodiac": "den pin sieu sang chong nuoc di da ngoai", "must": [("flashlight",), ("led", "waterproof", "tactical", "bright")]},
]


def _is_relevant(meta_row: tuple[str, str, str], scenario: dict) -> bool:
    dom, title, mcat = meta_row
    if dom != scenario["domain"]:
        return False
    blob = f"{title} {mcat}".lower()
    for group in scenario["must"]:
        if not any(term in blob for term in group):
            return False
    return True


def _metrics_for_list(cands: list[str], meta_map: dict[str, tuple[str, str, str]], scenario: dict, k: int = 10) -> dict[str, float]:
    top = cands[:k]
    hits = [1.0 if (iid in meta_map and _is_relevant(meta_map[iid], scenario)) else 0.0 for iid in top]
    prec = float(np.mean(hits)) if top else 0.0
    hit_any = 1.0 if any(hits) else 0.0
    mrr = next((1.0 / (i + 1) for i, h in enumerate(hits) if h > 0), 0.0)
    dcg = sum(h / np.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1.0 / np.log2(i + 2) for i in range(k))
    ndcg = float(dcg / ideal) if ideal > 0 else 0.0
    return {"precision@10": prec, "hit@10": hit_any, "mrr@10": mrr, "ndcg@10": ndcg}


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--embeddings-path", type=Path, required=True)
    ap.add_argument("--bm25-index-path", type=Path, required=True)
    ap.add_argument("--ann-index-path", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    t0 = time.perf_counter()
    paths = resolve_bundle_paths(tag=args.tag)
    train, val, test = load_splits(paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    _, target_df = select_fit_target(train, val, test, "validation")
    cutoff = int(target_df.timestamp.min())

    store, encoder_impl, emb_prov = load_validated_embeddings(args.embeddings_path, paths.corpus_path)
    encoder = TextEncoder(encoder_impl.encode, dimension=store.dimension)
    bm25 = SparseBM25Index.load(args.bm25_index_path)
    ann_search = build_ann_search(store, {
        "index": "hnsw_sq8", "m": 32, "ef_search": 1024, "warmup_queries": 300, "warmup_limit": args.limit,
        "index_path": str(args.ann_index_path),
        "expected_embedding_build_id": emb_prov.get("build_id"),
    })
    translator = VietnameseQueryTranslator()

    conn = sqlite3.connect(f"file:{paths.corpus_path.resolve()}?mode=ro", uri=True)
    eligible_ids = {
        str(r[0]) for r in conn.execute(
            "SELECT item_id FROM items WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= ?", (cutoff,)
        )
    }
    bm25_valid = bm25.eligible_mask(eligible_ids)
    ann_valid = np.fromiter((i in eligible_ids for i in store.item_ids), dtype=bool, count=len(store.item_ids))
    print(f"[vi-track-b] ready ({len(eligible_ids):,} eligible items) in {time.perf_counter()-t0:.1f}s", flush=True)

    args.output.mkdir(parents=True, exist_ok=True)
    report = {"tag": args.tag, "num_scenarios": len(VI_SCENARIOS), "limit": args.limit, "variants": {}}

    for variant_name, field in (("vi_diacritics", "vi"), ("vi_no_diacritics", "vi_nodiac")):
        arms = ("raw_bm25", "raw_dense", "vi_bridge_bm25", "vi_bridge_dense", "vi_bridge_hybrid")
        results_by_arm: dict[str, list[list[str]]] = {a: [] for a in arms}
        lat_by_arm: dict[str, list[float]] = {a: [] for a in arms}
        all_returned: set[str] = set()
        translations = []

        for sc in VI_SCENARIOS:
            q_raw = sc[field]
            tr = translator.translate(q_raw)
            q_en = str(tr["translated"])
            translations.append({"id": sc["id"], "raw": q_raw, "translated": q_en, "matched": tr["matched_phrases"]})

            # 1. raw_bm25
            ts = time.perf_counter()
            c_rb = bm25.search(q_raw, valid_mask=bm25_valid, limit=args.limit)
            lat_by_arm["raw_bm25"].append(time.perf_counter() - ts)
            results_by_arm["raw_bm25"].append(c_rb)

            # 2. raw_dense
            ts = time.perf_counter()
            v_raw = np.asarray(encoder.encode([q_raw])[0], dtype=np.float32)
            v_raw /= max(float(np.linalg.norm(v_raw)), 1e-12)
            c_rd = ann_search(v_raw, ann_valid, set(), args.limit)
            lat_by_arm["raw_dense"].append(time.perf_counter() - ts)
            results_by_arm["raw_dense"].append(c_rd)

            # 3. vi_bridge_bm25
            ts = time.perf_counter()
            c_tb = bm25.search(q_en, valid_mask=bm25_valid, limit=args.limit)
            lat_by_arm["vi_bridge_bm25"].append(time.perf_counter() - ts)
            results_by_arm["vi_bridge_bm25"].append(c_tb)

            # 4. vi_bridge_dense
            ts = time.perf_counter()
            v_en = np.asarray(encoder.encode([q_en])[0], dtype=np.float32)
            v_en /= max(float(np.linalg.norm(v_en)), 1e-12)
            c_td = ann_search(v_en, ann_valid, set(), args.limit)
            lat_by_arm["vi_bridge_dense"].append(time.perf_counter() - ts)
            results_by_arm["vi_bridge_dense"].append(c_td)

            # 5. vi_bridge_hybrid (weighted RRF favoring BM25 + dense semantic support)
            ts = time.perf_counter()
            c_th = [
                r["item_id"] for r in fuse_candidates(
                    {"bm25": c_tb, "dense": c_td},
                    budget=args.limit,
                    method="weighted_rrf",
                    rrf_k=60,
                    weights={"bm25": 1.0, "dense": 0.7},
                )
            ]
            lat_by_arm["vi_bridge_hybrid"].append(lat_by_arm["vi_bridge_bm25"][-1] + lat_by_arm["vi_bridge_dense"][-1] + (time.perf_counter() - ts))
            results_by_arm["vi_bridge_hybrid"].append(c_th)

            for lst in (c_rb, c_rd, c_tb, c_td, c_th):
                all_returned.update(lst[:10])

        # Fetch metadata for all top-10 returned items once
        meta_map: dict[str, tuple[str, str, str]] = {}
        ret_list = sorted(all_returned)
        for start in range(0, len(ret_list), 500):
            chunk = ret_list[start:start + 500]
            marks = ",".join("?" for _ in chunk)
            for iid, dom, title, mcat in conn.execute(
                f"SELECT item_id, domain, title, main_category FROM items WHERE item_id IN ({marks})", chunk
            ):
                meta_map[str(iid)] = (str(dom or ""), str(title or ""), str(mcat or ""))

        summary = {}
        print(f"\n=== Vietnamese Track B ({variant_name}, n={len(VI_SCENARIOS)}) ===", flush=True)
        for arm in arms:
            rows_m = [_metrics_for_list(cands, meta_map, sc, k=10) for cands, sc in zip(results_by_arm[arm], VI_SCENARIOS)]
            s = {
                **{k: float(np.mean([r[k] for r in rows_m])) for k in rows_m[0]},
                "p50_ms": float(np.percentile(lat_by_arm[arm], 50) * 1000),
                "p95_ms": float(np.percentile(lat_by_arm[arm], 95) * 1000),
            }
            summary[arm] = s
            print(
                f"  {arm:18s}: Hit@10={s['hit@10']:.3f} P@10={s['precision@10']:.3f} "
                f"MRR@10={s['mrr@10']:.3f} NDCG@10={s['ndcg@10']:.3f} | p95={s['p95_ms']:.1f}ms",
                flush=True,
            )
        report["variants"][variant_name] = {"summary": summary, "translations": translations}

    conn.close()
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[vi-track-b] saved -> {args.output / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
