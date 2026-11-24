# So sánh Amazon Reviews 2023: UCSD raw vs HuggingFace vs corpus local

Ngày chạy: 2026-11-24. Script: `compare_amazon_sources.py` (xem mục "Lệch spec" cuối file).
Outputs: `out_subscription_boxes/report.json`, `out_all_beauty/report.json`, `out_video_games/report.json` (+ `out_video_games.log`, `out_all_beauty.log`).

## 1. Kết luận 3 dòng

- **UCSD raw và HuggingFace giống hệt nhau** trên cả 3 domain đã test: mọi dòng giống nhau từng byte-về-mặt-JSON (row-hash sha1 của canonical JSON trùng 100%), không field nào chỉ có ở một nguồn, không giá trị nào lệch.
  - Subscription_Boxes: meta 641/641, reviews 16,216/16,216 identical (`out_subscription_boxes/report.json`).
  - All_Beauty: meta 112,590/112,590, reviews 701,528/701,528 identical (`out_all_beauty/report.json`).
  - Video_Games: meta 137,269/137,269, reviews 4,624,615/4,624,615 identical (`out_video_games/report.json`).
- File `resource/raw/*` của project **cũng giống hệt** UCSD/HF (Video_Games: 137,269 meta + 4,624,615 reviews identical) — project đang dùng đúng bản raw, không phải bản "thiếu field".
- Field bị rớt **không phải do nguồn dữ liệu** mà do pipeline: stage 1 chỉ giữ 4 cột review (`user_id, parent_asin, rating, timestamp`); corpus chỉ giữ 8 field meta + categories; các field như `features`, `description`, `details` (gồm `Date First Available`), `text`, `helpful_vote`, `verified_purchase` bị bỏ hoàn toàn.

## 2. Bảng field (non-empty %)

### Meta — Video_Games (domain đại diện; UCSD = HF = local raw)

| field | UCSD/HF/local raw | corpus local (`items`+`item_categories`) |
|---|---|---|
| parent_asin | 100.0 | 100.0 (→ `original_item_id`) |
| title | 99.99 | 99.99 |
| store | 96.82 | 96.82 |
| price | 45.17 | 45.15 (str → float, một số giá không parse được) |
| average_rating | 100.0 | 100.0 |
| rating_number | 100.0 | 100.0 (int → float) |
| main_category | 91.96 | 91.96 |
| categories | 90.79 | ~90.8 (flatten sang `item_categories`) |
| **features** | **71.23** | **bị bỏ** |
| **description** | **62.31** | **bị bỏ** |
| **details** | **97.51** | **bị bỏ** |
| **images** | **99.90** | **bị bỏ** |
| **videos** | **21.06** | **bị bỏ** |
| author | 0.19 | bị bỏ |
| subtitle | 0.25 | bị bỏ |
| bought_together | 0.0 | bị bỏ (field tồn tại nhưng rỗng 100% ở mọi domain test) |
| domain / item_id / first_seen_ts | — | 100.0 (field do pipeline sinh thêm) |

Nguồn: `out_video_games/report.json` → `sources.ucsd_meta.fields`, `sources.local_meta_1.fields`.
Meta Subscription_Boxes/All_Beauty chỉ có 14 field (thiếu `author`, `subtitle` — 2 field này chỉ xuất hiện ở một số domain); categories rỗng 100% ở cả hai domain đó (xem mục 4).

### Reviews — Video_Games

| field | raw (UCSD=HF=local) | cleaned `interactions.parquet` |
|---|---|---|
| user_id | 100.0 | 100.0 |
| parent_asin | 100.0 | 100.0 |
| rating | 100.0 | 100.0 |
| timestamp | 100.0 | 100.0 |
| **asin** | **100.0** | **bị bỏ** |
| **title** | **100.0** | **bị bỏ** |
| **text** | **99.99** | **bị bỏ** |
| **helpful_vote** | **100.0** | **bị bỏ** |
| **verified_purchase** | **100.0** | **bị bỏ** |
| **images** | **4.43** | **bị bỏ** |

Nguồn: `out_video_games/report.json`; cleaned parquet = `resource/cleaned/Video_Games/interactions.parquet` (4 cột, 4,570,962 dòng — khớp manifest `num_output`, `resource/cleaned/Video_Games/stage_1.manifest.json`).

## 3. Chênh lệch giá trị

### UCSD vs HF vs `resource/raw`: không có chênh lệch

Row-hash identical = 100% cả 3 cặp so sánh, mọi domain. `field_value_diffs` rỗng (trừ các field có >300K giá trị distinct — `text`, `title`, `user_id`, `timestamp` ở Video_Games — bị cap counter, nhưng identical_rows đã chứng minh toàn bộ dòng trùng).

### Raw → pipeline local (Video_Games)

**Meta → corpus `items` (137,249/137,269 dòng giữ lại; 20 item không có trong mapping bị loại):**

- Field chỉ có ở raw (bị bỏ hoàn toàn): `author` (262 non-empty), `bought_together` (0), `description` (85,539), `details` (133,847), `features` (97,771), `images` (137,127), `subtitle` (350), `videos` (28,913).
- Field đổi kiểu/định dạng (không mất giá trị):
  - `rating_number`: raw `int` ("1") → corpus `float` ("1.0") — do `numeric_column()` ở `package/corpus/build_corpus.py:110-111`. Toàn bộ 137K giá trị "lệch" chỉ vì "1" vs "1.0".
  - `price`: raw là string lẫn lộn ("$12.99", "from 29.99", ký tự lỗi "�") → corpus float; 43 giá trị chỉ có ở raw, non-empty giảm 45.17% → 45.15% (mất ~0.02%, chủ yếu giá không parse được — `build_corpus.py:107-109`).
  - `categories`: 11 giá trị list chỉ có ở raw — do `normalize_categories()` biến đổi cấu trúc (`package/corpus/build_corpus.py:126`); coverage thực tế ~90.8%.
  - `parent_asin`/`title`/`store`/`main_category`/`average_rating`: 19–20 giá trị chỉ ở raw = đúng 20 item bị loại khỏi mapping.

**Reviews → cleaned (4,624,615 → 4,570,962 dòng; mất 53,653 = `num_dropped_duplicates` trong manifest, do dedup keep-last `clean_domain.py:136-144`):**

- `parent_asin`, `rating`: 53,653 giá trị chỉ ở raw — hệ quả của việc keep-last khi trùng `(user_id,parent_asin,timestamp)`.
- `asin`, `title`, `text`, `helpful_vote`, `verified_purchase`, `images`: chỉ có ở raw, pipeline không đọc (`clean_domain.py:101` chỉ request 4 cột).
- `timestamp`, `user_id`: counter bị cap 300K distinct → không diff từng giá trị; nhưng min/max timestamp và tập user_id khớp (metrics giống hệt: 2,766,656 users, ts 911332729000→1694509355529).

Không phát hiện khác biệt "parquet padding" hay "JSON-in-string" nào giữa raw và processed ngoài các đổi kiểu nêu trên.

## 4. Chỉ số liên quan project

| chỉ số | Subscription_Boxes | All_Beauty | Video_Games |
|---|---|---|---|
| meta rows | 641 | 112,590 | 137,269 |
| `categories` rỗng | **100%** | **100%** | **9.21%** (11,258 non-empty... thực tế 90.79% có categories) |
| `details["Date First Available"]` | 0% (key không có trong details domain này) | 0.30% (341 items) | **93.61%** (128,499 items) |
| review rows | 16,216 | 701,528 | 4,624,615 |
| n_users / n_items(asin) | 15,237 / 1,128 | 631,986 / 115,709 | 2,766,656 / 167,645 |
| timestamp range (ms) | 2017-01→2023-08 | 2000-10→2023-09 | 1998-12→2023-09 |
| `asin ≠ parent_asin` | 68.96% | 8.72% | **46.11%** |

Lưu ý: `categories` rỗng 100% ở Subscription_Boxes và All_Beauty — field `categories` của meta_categories gần như chỉ có dữ liệu ở một số domain (Video_Games 90.8%). Đây là đặc tính nguồn, không phải lỗi pipeline. `asin ≠ parent_asin` rất cao cho thấy `asin` (child ASIN) khác `parent_asin` thường xuyên — pipeline group theo `parent_asin` là đúng hướng.

## 5. Field đáng dùng (kèm coverage)

- **`details["Date First Available"]`** — 93.61% items Video_Games, 97.51% items có `details` non-empty. Có thể làm `first_seen` causal-safe thay proxy "earliest review" hiện tại (`package/data/_schema.py:12` ghi rõ first_seen_ts chỉ là proxy). Ở All_Beauty chỉ 0.3% nên coverage domain-dependent — cần đo trên Electronics/Toys_and_Games trước khi dùng.
- **`features`** (71.23% VG), **`description`** (62.31% VG) — text enrichment cho retrieval/FTS; hiện corpus FTS chỉ index `title, store, main_category, categories` (`package/corpus/_sql.py:38-39, 63-64`).
- **`details`** còn chứa `Brand` (VG: nằm trong top details keys), `Best Sellers Rank`, `Release date`, `Manufacturer` — nguồn brand/rank sạch hơn `store` hiện tại.
- **`images`/`videos` meta** (99.9%/21.1% VG) — chưa rõ use-case; có thể bỏ qua.
- **Review `text` (99.99%), `title` (100%), `helpful_vote` (100%), `verified_purchase` (100%)** — hiện bị drop ở stage 1; `text`/`title` review có thể enrich item representation, `verified_purchase`/`helpful_vote` có thể lọc/rerank. Lưu ý `OPTIONAL_COLUMNS` đã định nghĩa các field này (`package/data/_schema.py:7`) nhưng không nơi nào dùng.
- **`bought_together`** — tồn tại trong schema nhưng 0% non-empty ở cả 3 domain → không đáng dùng.
- **`categories`** — coverage cực không đều (0% All_Beauty/SubBoxes vs 90.8% VG); project đã có pipeline inferred categories (`investigations/q2_inferred_cats`) nên raw `categories` chỉ bổ sung được cho domain có sẵn.

## 6. Chưa xác minh

- Electronics và Toys_and_Games **chưa chạy** (quá lớn: reviews gz 6.5GB và 1.9GB); kết luận UCSD≡HF mới kiểm chứng trên 3/33 domain.
- HF `benchmark/` splits và `0core`/`5core`/`10core` filtered files **chưa so** — chỉ so `raw/`.
- Value-diff theo từng giá trị của `text`, `title`, `user_id`, `timestamp` ở Video_Games bị cap 300K distinct/field → "values_skipped"; bù lại identical_rows = 4,624,615/4,624,615 chứng minh bằng nhau tuyệt đối giữa UCSD/HF/local raw.
- `local_meta_1` (corpus export) là subset theo item2id mapping và `categories` được aggregate từ bảng `item_categories`, không phải raw field nguyên bản — so sánh mang tính "pipeline output" chứ không phải raw-vs-raw.
- Không kiểm tra thứ tự dòng (chỉ so multiset row-hash); nếu HF sắp xếp khác UCSD thì pipeline đọc tuần tự có thể thấy thứ tự khác — nhưng nội dung giống hệt.
- `author`/`subtitle` chỉ thấy ở Video_Games meta; chưa rõ chúng xuất hiện ở domain nào khác.

## Lệch spec / ghi chú tái lập

1. **File `compare_amazon_sources.py` đính kèm không tồn tại** trong repo/Downloads → đã viết lại theo spec (cùng CLI `--domain/--out/--local`).
2. **URL UCSD**: link `datarepo.eng.ucsd.edu` trong HF README hiện trả 404; host thật là `mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/...` (lấy từ amazon-reviews-2023.github.io). Script dùng host này.
3. UCSD files là `.jsonl.gz`; HF files là `.jsonl` (uncompressed) — script đọc cả hai.
4. Video_Games reviews (814MB gz) tải bằng parallel HTTP range (16 kết nối) do single-stream ~10MB/phút; file đã `gzip -t` pass và size khớp `resource/raw` từng byte.
5. `out_video_games/report.json` đã strip `row_hashes` (bản gốc 1.05GB → 34KB) sau khi diff xong; `out_subscription_boxes`/`out_all_beauty` giữ nguyên.
