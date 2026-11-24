# Workstream B — Audit: price/rating masking under `historical_static_catalog` có over-aggressive không?

Repo: `agentic-rag-for-rcm-sys/src`, branch `distill-phase05-1`. Read-only audit; mọi số liệu đo trực tiếp (sqlite `mode=ro`, parquet, gzip jsonl) ngày audit.

**TL;DR:** Masking **over-aggressive ở rating, đúng mức ở price**. `average_rating`/`rating_number` bị NULL cho **100% items** dù interactions đã chứa `rating`+`timestamp` và pipeline **đã có sẵn** cơ chế recompute causal (`item_rating` proxy, dùng cho `min_rating`/`order_by`) — chỉ là không request kind nào dùng nó và `min_rating_number` vẫn bị chặn. `price` là snapshot đơn trị, không có temporal source → mask là hợp lý, nhưng hệ quả là `constrained` requests chết hoàn toàn (0 request trong mọi artifact) và FilterTool raise lỗi cho mọi price filter. Nếu chỉ mở snapshot-price: **40 constrained requests** (cap 20/segment) sinh được cho cả validation và test. Nếu chỉ recompute rating mà price vẫn mask: **0** (constrained cần price, không cần rating).

---

## 1. Masking xảy ra ở đâu, field nào, mode nào

- `package/corpus/apply_metadata_policy.py:8` — `POLICIES = ("historical_static_catalog", "snapshot", "no_filter")`.
- `apply_metadata_policy.py:9` — `MUTABLE_FIELDS = ("price", "average_rating", "rating_number")`.
- `apply_metadata_policy.py:109` — `masked = list(MUTABLE_FIELDS) if policy == "historical_static_catalog" else []`.
- `apply_metadata_policy.py:156-158` — TEMP view `items` được build với `NULL AS "<col>"` cho từng masked field (projection), cộng filter `first_seen_ts <= as_of_timestamp` (`:211-215`).
- `apply_metadata_policy.py:269-278` — authorizer deny `SQLITE_READ` trên `main.items` masked columns và `items_fts*` shadow tables → agent SQL không đọc được giá trị gốc.
- **Modes không mask:** `snapshot` (`masked=[]`, `snapshot_mutable_fields_used=True`, flagged non-causal — `:124`) và `no_filter` (`masked_fields: []`, không first_seen filter, `:89-104`). Cả hai tồn tại nhưng **không config nào dùng**: `configs/agent/agent_eval.yaml:27`, `configs/eval/candidate_recall.yaml:11`, `configs/eval/ranking_eval.yaml:14`, `configs/eval/embedding_benchmark_contract.yaml:4`, `configs/profiles/multi_domain*.yaml` đều pin `historical_static_catalog`.
- Cột corpus bị ảnh hưởng đúng 3: `price`, `average_rating`, `rating_number` (`package/data/_schema.py:8-20`, `ITEM_COLUMNS`). `title`, `store`, `main_category`, `item_categories`, FTS **không bị mask**.

## 2. Split timestamps & temporal usability

Splits `resource/splits/multi_domain/*.parquet` (cols `user_idx, item_idx, rating, timestamp, ...`), timestamp = ms epoch:

| split | rows | timestamp min | max |
|---|---|---|---|
| train | 48,766,894 | 848,336,280,000 | 1,617,737,606,134 |
| validation | 7,787,433 | 1,617,737,606,549 | 1,651,701,127,817 |
| test | 7,511,892 | 1,651,701,131,688 | 1,694,625,981,867 |

- Ranh giới sạch: train.max < val.min (~435 ms gap), val.max < test.min. `as_of = target_df.timestamp.min()` (`run_agent_eval.py:476`) → validation as_of ≈ 2021-04, test as_of ≈ 2022-05.
- **Interactions CÓ `rating` (float 1–5) và `timestamp`** (`resource/filtered/multi_domain/interactions.parquet`, 64,066,219 rows, cùng schema) → rating **tái tính được theo thời gian** từ fit split. `first_seen_ts` trong corpus cũng derive từ min interaction ts.

## 3. Trước masking: tỉ lệ non-null price/rating

Corpus sqlite `resource/corpus/multi_domain/corpus_multi_domain.sqlite` (query `mode=ro`, bảng `main.items` — giá trị vật lý vẫn đầy đủ, mask chỉ là TEMP view):

| metric | value |
|---|---|
| items | 2,637,776 |
| `price` non-null | **1,016,912 (38.5%)** |
| `average_rating` non-null | **2,637,776 (100%)** |
| `rating_number` non-null | **2,637,776 (100%)** |
| `first_seen_ts` non-null | 2,637,776 (100%) |

Đối chiếu raw `resource/raw/meta_*.jsonl.gz` (đếm toàn bộ 2,638,155 dòng): price parse được = 1,017,086 (38.5%, khớp); `average_rating`/`rating_number` non-"None" = 100% — **mask rating xoá thông tin của mọi item**, kể cả item không có interaction nào.

**Trong eval targets** (held-out items của users có target, `eval_on=validation`: 5,096,026 users / 771,511 unique target items; `eval_on=test`: 4,519,632 users / 768,179 items):

| | validation | test |
|---|---|---|
| target items có price non-null | 423,817/771,511 = **54.9%** | 526,637/768,179 = **68.6%** |
| target items có ≥1 category | 92.5% | 95.8% |
| target items có rating trong **fit split** (proxy coverage) | 457,272/771,511 = **59.3%** | 448,515/768,179 = **58.4%** |

## 4. rating/rating_number: aggregate-at-crawl hay temporal? Recompute được không?

- `average_rating`/`rating_number` trong meta là **aggregate tại thời điểm scrape** (single snapshot, không timestamp, không version) — đúng lý do bị mask.
- **Nhưng recompute từ interactions được**: splits + filtered parquet đều có `rating`+`timestamp` per review. Code **đã tồn tại**: `scripts/evaluation/run_agent_eval.py:519-532` build `popularity` (fit interaction counts) và `ratings` (fit mean rating per item) → `apply_metadata_policy(..., popularity=, ratings=)` tạo temp `item_popularity`/`item_rating` (`apply_metadata_policy.py:160-210`, docstring `:19-29` ghi rõ "causal, pre-as_of").
- Tiêu thụ: `package/tools/sql/filter_tool.py:95-116` — `min_rating` trên masked `average_rating` được rewrite sang `item_rating.avg_rating >= ?`; `:186-197` — `order_by='average_rating'` → `causal_rating` ordering. `min_rating_number` **không** có proxy → vẫn raise (`:124-137`).
- Coverage của proxy: fit items = 2,003,873 (validation) / 2,318,112 (test) distinct item_idx trên tổng 2,637,776 corpus items → **~76% / ~88% corpus items** có fit-rating; ~59% eval targets. Phần còn lại (item chỉ xuất hiện sau cutoff, hoặc metadata-only không có review) sẽ là NULL — trung thực.
- Lưu ý: mean-of-fit-ratings ≠ `average_rating` scrape (khác population, khác thời điểm) — là proxy causal, không phải giá trị gốc.

## 5. price: temporal source? Leak risk?

- **Không có temporal source.** Price chỉ tồn tại trong `meta_*.jsonl.gz` như một scalar tại crawl time (scrape ~2023, sau cả test as_of 2022-05). Interactions không chứa price; không bảng price-history nào trong `resource/`.
- Leak risk **cao hơn rating** ở 2 lớp: (a) bản thân giá trị snapshot post-date cutoff → agent thấy giá "tương lai"; (b) `build_requests.py:75-87` suy ra `price_max = held_out_price × 1.25` — trực tiếp encode giá target vào request spec (oracle leak by design, nhưng cần price thật để build). Rating không có vai trò nào trong `build_requests` (không kind nào dùng `min_rating`) nên recompute rating **không mở khoá thêm request nào** — xem §7.
- Ngoài ra `items_satisfying` (`_helper.py:23-39`) dùng `items.price` cho gold `targets` → cần unmasked price để gold đúng.

## 6. Field khác leak tương lai chưa mask

Những gì agent thực sự đọc được = `ITEM_COLUMNS` + `item_categories` + FTS(title, store, main_category, categories) (`_sql.py:27-56`). Đã kiểm:

| field | trong corpus? | leak? |
|---|---|---|
| `price`, `average_rating`, `rating_number` | có | đang mask (đúng cho price; quá tay cho rating — xem §4) |
| `title` chứa giá | có, **không mask** | **~7,311 items có `$` trong title** (query `LIKE '%$%'`). Phần lớn là gift-card denomination (`$50 Xbox Gift Card`, `B0BL65X86R`) — vẫn là thông tin giá; một phần là pattern trang trí (`100$ Cash Money Patterned`, `B09TKK8GH6`). `LIKE '%rating%'` 2,521 hits nhưng gần hết false positive (`Operating`, `CERORatings`); `'%star%'` 54,985 cần rà soát thêm — **chưa xác minh** có "5 stars" review-text leak trong title. |
| `store`, `main_category` chứa `$` | có | 25 rows — negligible |
| `description`, `features`, `details`, `images`, `videos`, `bought_together` | **không load vào corpus** (`ITEM_COLUMNS` loại trừ) | agent không đọc được → không leak qua tools. Nhưng raw meta chứa: `details["Best Sellers Rank"]` (~143k/300k Electronics sample ≈ 48%), `details["Date First Available"]` (~96%), `bought_together` **0/2,638,155 non-empty**, description/features có `$\\d` trong ~0.6% sample — nếu sau này load các field này vào corpus sẽ leak ngay. |
| `item_categories` / FTS categories | có | labels taxonomy tĩnh, không chứa giá/rating |

## 7. Ước lượng số `constrained` requests khả dĩ

Tái hiện đúng logic `build_requests.py:70-87` + `run_agent_eval.py:473-489` (`select_fit_target`, `target_by_user`, `hist_size`, `segment_users_by_history` với `sparse_max=4`, `per_segment=20` từ `agent_eval.yaml`), lookup price/category từ `main.items`/`item_categories` (bảng vật lý, chưa mask). "Valid" = `picked is not None` = ≥1 held-out item có price non-null VÀ ≥1 category; request vẫn được `add()` kể cả khi `relevant` rỗng.

| kịch bản | eval_on=validation | eval_on=test |
|---|---|---|
| Hiện tại (historical_static_catalog) | **0** (price NULL → mọi user skip) | **0** |
| CHỈ mở snapshot-price (rating vẫn mask) | eligible sparse=1,496,278 / warm=591,008 users → cap 20/segment → **40 requests** | eligible sparse=1,472,542 / warm=617,036 → **40 requests** |
| CHỈ recompute train-period rating, price vẫn mask | **0** — constrained cần `price`, không dùng rating; `min_rating` không xuất hiện trong request builder | **0** |

Lưu ý: eligible users >> cap nên kết quả luôn = 40 (20 sparse + 20 warm) bất kể seed; con số 40 là trần `per_segment`, không phải số user đủ điều kiện (~2.1M users eligible cho validation).

## 8. Kết luận & options/risks (không implement)

**Kết luận:**
- Masking **đúng** cho `price` (single post-cutoff snapshot, không cách nào recompute causal) — nhưng cái giá là `constrained` kind chết hoàn toàn và FilterTool raise trên mọi `price_min/price_max/min_rating_number` (`filter_tool.py:124-137`). Đây là over-aggressive **theo nghĩa tính năng** chứ không phải leak: option "snapshot" tồn tại sẵn nhưng bị gắn cờ non-causal.
- Masking **over-aggressive** cho `average_rating`/`rating_number`: dữ liệu causal đã có sẵn trong splits (rating+timestamp), proxy code đã viết và đang chạy (`item_rating`), coverage ~59% targets / ~76-88% corpus. Tuy nhiên **unmask rating đơn thuần không cứu được request nào** vì không kind nào dùng rating — lợi ích chỉ đến nếu thêm kind/filter dùng `min_rating` (FilterTool đã support qua proxy).

**Options & risks:**
1. **Giữ nguyên** — an toàn tuyệt đối, chấp nhận constrained dead + rating info bị bỏ phí. Risk: eval không đo được price/rating-constrained behaviour; mọi `price_*`/`min_rating_number` filter đều ToolInputError.
2. **Snapshot mode cho eval phụ (non-causal)** — `policy="snapshot"`/`no_filter` đã implement sẵn; chỉ cần chạy thêm 1 eval pass. Risk: kết quả non-causal (leak thật: giá crawl-2023 + `price_max` derive từ held-out) — chỉ hợp lệ như upper-bound/diagnostic, không so sánh causal.
3. **Rating proxy mở rộng** — dùng `item_rating` cho `min_rating_number`-style filters hoặc thêm request kind rating-based; dữ liệu đã có. Risk: coverage chỉ ~59% targets → request set thiên lệch về popular items; mean-rating ≠ scrape-average_rating (proxy, không phải ground truth).
4. **Unmask rating fields nhưng giữ price mask** — không giải quyết constrained; chỉ có ích nếu kết hợp (3). Risk: `rating_number` (số lượt review) không recompute được chính xác từ fit interactions? — **chưa xác minh**: fit count là unique (user,item) pairs, `rating_number` gốc là tổng review count tại scrape; tương đương gần đúng nhưng khác semantics.
5. **Price temporal rebuild** — không khả thi với data hiện có (không price history). Nếu meta crawl lại theo thời gian hoặc có price trong reviews → cần pipeline mới. Risk: chi phí crawl, coverage.
6. **Leak hygiene bổ sung** — title chứa `$` (~7.3k items, gồm gift-card denominations) và (nếu load) `details["Best Sellers Rank"]`/`"Date First Available"` là future-leak channels chưa mask; cân nhắc sanitize title hoặc ghi nhận là accepted-risk. Risk: sửa title phá FTS/embedding.

*Caveats: "chưa xác minh" — (a) `'%star%'` titles có chứa review-count text không; (b) `rating_number` semantics vs fit interaction count; (c) `relevant` rỗng trong constrained requests có bị `filter_requests_by_scope`/scoring drop downstream không (không ảnh hưởng count 40 vì cap bind trước).*
