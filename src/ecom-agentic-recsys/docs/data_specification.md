# Data Specification — PHASE 0

## 1. Nguồn dữ liệu (đã xác nhận qua Hugging Face — McAuley-Lab/Amazon-Reviews-2023)

- Quy mô toàn bộ dataset: >570M review, ~48M item, 33 category + "Unknown".
- Cấu hình theo category, ví dụ `raw_review_<Category>` và `raw_meta_<Category>`, load qua `datasets.load_dataset("McAuley-Lab/Amazon-Reviews-2023", <config>)`.
- File hỗ trợ: `all_categories.txt`, `asin2category.json` (map parent_asin → category).

### 1.1 Schema review — User review record
| Field | Type | Ghi chú |
|---|---|---|
| rating | float | 1.0–5.0 |
| title | str | tiêu đề review |
| text | str | nội dung review |
| images | list | ảnh user đăng kèm review |
| asin | str | id sản phẩm cụ thể (biến thể) |
| parent_asin | str | **id chuẩn dùng làm item_id** — asin ở dataset cũ thực chất là parent_asin này |
| user_id | str | id người dùng |
| timestamp | int (ms) | mốc thời gian — bắt buộc cho temporal split |
| helpful_vote | int | số vote helpful |
| verified_purchase | bool | |

### 1.2 Schema review — Item metadata (ĐÃ XÁC NHẬN THẬT từ file `meta_Video_Games.jsonl.gz` bạn cung cấp)

Schema thật khác một phần so với dự đoán ban đầu ở Phase 0 — đã sửa lại đúng:

| Field | Type | Ghi chú |
|---|---|---|
| main_category | str | ví dụ "Video Games" |
| title | str | tên sản phẩm |
| average_rating | float | rating trung bình |
| rating_number | int | số lượng rating |
| features | list[str] | có thể rỗng |
| description | list[str] | có thể rỗng — KHÔNG phải string đơn |
| price | str hoặc null | dạng string ("19.99"), **không phải** float; null rất phổ biến (xem §1.3) |
| images | list[dict] | thumb/large/variant/hi_res |
| videos | list | |
| store | str hoặc null | **đây là field gần nhất với "brand"** — spec gốc dự đoán có field `brand` riêng nhưng thực tế dataset dùng `store` |
| categories | list[str] | **multi-label**, là đường dẫn taxonomy (ví dụ `["Video Games", "PC", "Games"]`), không phải 1 category duy nhất |
| details | dict | key-value tự do (Package Dimensions, Manufacturer, Rated, Best Sellers Rank...) |
| parent_asin | str | item id chuẩn |
| bought_together | list hoặc null | |

**Sửa lại so với Phase 0:** không có field `brand`/`author` riêng như dự đoán ban đầu — dùng `store` thay thế; `description` là list không phải string.

### 1.3 EDA thật trên item metadata (137,269 item — khớp chính xác số liệu công bố 137.2K)

Đã chạy `src/data/metadata_eda.py` trên **toàn bộ file thật** (không phải mẫu), streaming trong 3.65s:

| Metric | Giá trị thật |
|---|---|
| num_items | 137,269 |
| % thiếu price | **54.83%** |
| % thiếu description | 37.69% |
| % thiếu features | 28.77% |
| % thiếu store (brand proxy) | 3.18% |
| avg rating_number/item | 244.31 |
| avg average_rating | 3.995 |
| % thiếu average_rating | 0% (mọi item đều có) |

Top category (multi-label, không loại trừ nhau): Video Games (124,619) → Accessories (63,120) → Legacy Systems (50,925) → Games (46,533) → PC (37,500) → Nintendo Systems (23,525) → PlayStation Systems (14,987) → Nintendo Switch (12,352)...

Top store: Nintendo (4,229), Amazon Renewed (2,961), Electronic Arts (2,627), Sony (1,924), Ubisoft (1,887)...

**Tác động trực tiếp đến thiết kế (cần quyết định):**
- **54.83% thiếu price** là rất cao → kịch bản ví dụ ở `architecture.md` §3.2 ("laptop ~1000 USD") cho domain Video_Games cần có **fallback strategy** khi `ProductMetadataTool` trả `price=null`: loại khỏi candidate nếu user có budget constraint cứng, hoặc dùng `average_rating`/`rating_number` làm proxy độ tin cậy thay vì loại thẳng. → xem `decisions.md` D-006.
- `categories` là multi-label taxonomy, không phải nhãn đơn — `PopularityTool`/`SimilarItemTool` cần thiết kế theo hướng "match theo tập category giao nhau", không phải so sánh bằng nhau tuyệt đối.

## 2. Quy ước biến `DOMAIN`

Không hard-code category vào business logic. Toàn bộ pipeline đọc từ:
```
configs/data.yaml
  domain: ${DOMAIN}          # ví dụ: Video_Games, Electronics...
  raw_review_config: raw_review_${DOMAIN}
  raw_meta_config: raw_meta_${DOMAIN}
```
Việc **chọn domain cụ thể** thuộc Phase 2 (EDA) — cần cân nhắc: số lượng interaction đủ lớn để train sequential model, nhưng đủ nhỏ để chạy local (ưu tiên domain có vài trăm nghìn đến vài triệu review, không chọn "Unknown" hoặc domain quá lớn như Books ở phase đầu).

## 3. Phân loại dữ liệu (bắt buộc tách rõ theo mục V)

- **interaction data**: (user_id, parent_asin, rating, timestamp) — nguồn cho sequential/collaborative model.
- **item data**: metadata sản phẩm — nguồn cho content-based/semantic retrieval.
- **user data**: derived, KHÔNG có sẵn user profile tường minh trong Amazon Reviews 2023 → phải tự xây dựng từ interaction + review text (aggregate theo thời gian).
- **review data**: text, title, helpful_vote — nguồn cho semantic embedding và cho ExplanationTool trích evidence thật.
- **derived features**: profile summary, embedding, memory record — sinh ra bởi pipeline, không phải dữ liệu gốc.

## 4. Data pipeline (raw → test)

```
raw (HF dataset)
  → cleaned (loại duplicate, review rỗng, user/item không đủ interaction tối thiểu)
  → filtered (áp domain filter, k-core filtering nếu cần)
  → mapped (asin/parent_asin → internal item_id; user_id → internal user_id)
  → train / validation / test (temporal split — xem mục 5)
```
Mỗi bước ghi log số lượng record trước/sau để audit (không được "âm thầm" loại bỏ dữ liệu).

## 5. Temporal split & chống Data Leakage (mục VI — bắt buộc)

- Nguyên tắc: `train < validation < test` theo `timestamp`, tuyệt đối không random split cho interaction data.
- User profile tại thời điểm `t` chỉ được build từ interaction có `timestamp <= t`.
- Memory tại thời điểm `t` không được biết interaction tương lai — nghĩa là khi tạo training example cho một điểm thời gian, memory store phải được "rewind" lại đúng thời điểm đó (không dùng memory store đã cập nhật đầy đủ).
- **Deliverable bắt buộc:** `src/data/leakage_check.py` — module kiểm tra:
  - với mỗi (user, t) trong test set, verify mọi feature dùng để dự đoán có `timestamp <= t`.
  - unit test cho module này (mục XXIV) — status: `BLOCKED — sẽ implement ở Phase 3`, ghi nhận ở đây để không quên.

## 6. Cold-start & evolving-interest scenario (mục XVIII)

Sau khi có EDA thật (Phase 2), dataset con phải được cắt thành 4 nhóm để đánh giá riêng, không trộn chung:
1. **Warm user** — nhiều interaction, lịch sử dài.
2. **New user** — 0–2 interaction trong train, đánh giá cold-start.
3. **Sparse-history user** — vài interaction rải rác, khoảng cách thời gian lớn.
4. **Evolving-interest user** — có sự thay đổi rõ category/attribute ưa thích theo thời gian (cần định nghĩa ngưỡng cụ thể ở Phase 2, hiện tại `BLOCKED — chưa có số liệu thật để đặt ngưỡng`).

## 8. Domain shortlist — dựa trên số liệu ĐÃ CÔNG BỐ (chưa phải EDA tự chạy)

> Nguồn: trang dataset chính thức `McAuley-Lab/Amazon-Reviews-2023` (bảng "Grouped by Category"). Đây là số liệu **do nguồn công bố báo cáo**, KHÔNG phải kết quả EDA tự chạy của project (do BLOCKED network — xem §9). Không dùng số này để chốt quyết định cuối, chỉ dùng để thu hẹp shortlist trước khi có EDA thật.

| Category | #User | #Item | #Rating | Ghi chú |
|---|---|---|---|---|
| **Video_Games** | 2.8M | 137.2K | 4.6M | Ứng viên chính — item catalog vừa đủ nhỏ để FAISS index local, đã là benchmark phổ biến trong literature (dễ so sánh định hướng, không so sánh số liệu trực tiếp) |
| Baby_Products | 3.4M | 217.7K | 6.0M | Ứng viên phụ — item catalog lớn hơn Video_Games |
| Appliances | 1.8M | 94.3K | 2.1M | Ứng viên phụ — nhỏ nhất trong shortlist, phù hợp nếu cần giảm tải hơn nữa |
| All_Beauty | 632.0K | 112.6K | 701.5K | Dự phòng nếu cần domain rất nhỏ để debug pipeline nhanh |

**Đề xuất tạm thời (chưa CHỐT — cần EDA thật để xác nhận sparsity/sequence length sau k-core filtering):** `Video_Games`.

## 9. Trạng thái Phase 2 (cập nhật lần 2 — đã có dữ liệu metadata thật)

**Đã giải quyết:** người dùng đã upload `meta_Video_Games_jsonl.gz` (item metadata thật, 137,269 item — khớp chính xác số liệu công bố). Đã copy vào `data/raw/Video_Games/meta_Video_Games.jsonl.gz`, đã viết `src/data/metadata_eda.py` (có unit test với synthetic fixture, 4 test pass) và **đã chạy EDA thật** — xem kết quả ở §1.3.

**Vẫn còn BLOCKED:**
```
BLOCKED: chưa có review/interaction data (raw_review_Video_Games) — file
  đã nhận chỉ là item metadata (raw_meta_Video_Games), KHÔNG chứa
  user_id/rating/timestamp interaction.
REASON: huggingface.co vẫn bị chặn network trong container, và người
  dùng chỉ mới upload phần metadata.
REQUIRED ACTION: cần người dùng tải và upload thêm file review thật,
  ví dụ qua HuggingFace: dataset "McAuley-Lab/Amazon-Reviews-2023",
  config "raw_review_Video_Games" — export ra .jsonl.gz hoặc .parquet
  rồi upload, để có thể chạy compute_interaction_stats() thật (num_users,
  sparsity, sequence length, temporal split) — đây là điều kiện bắt buộc
  để hoàn thành Phase 2 và bắt đầu Phase 3.
```

**Domain CHÍNH THỨC hoá một phần:** `Video_Games` được xác nhận là domain đang dùng (không còn "tạm thời") vì đã có dữ liệu thật đang xử lý, nhưng quyết định cuối cùng ("có tiếp tục hay đổi domain") vẫn chờ EDA phía interaction (nếu sparsity quá cao, có thể cần đổi sang domain khác trong shortlist §8).

## 11. EDA thật trên interaction data (chạy local bởi người dùng, 22/9)

Người dùng đã tải `review_Video_Games.jsonl.gz` thật (McAuley-Lab, config `raw_review_Video_Games`) và chạy `scripts/run_interaction_eda_local.py` (streaming, không upload file). Kết quả thật:

| Metric | Giá trị thật |
|---|---|
| num_interactions | không log trực tiếp, suy ra ≈ 4.6M (khớp số liệu công bố) |
| num_users | **2,766,656** |
| num_items | **137,249** (metadata có 137,269 → lệch 20 item, khả năng orphan item không có review) |
| sparsity | **0.999988** (99.9988%) |
| avg_rating | 4.047 |
| timestamp range | 1998-11-17 → 2023-09-12 (~24.8 năm) |
| avg_interactions_per_user | 1.672 |
| median_interactions_per_user | **1.0** |
| p90 / p99 / max | 3 / 9 / 664 |
| % user chỉ có 1 interaction | **72.21%** (1,997,753 user) |
| % user ≥5 interaction | **4.26%** (117,742 user) |
| % user ≥10 interaction | 0.98% (27,017 user) |

### Tác động trực tiếp đến thiết kế (bắt buộc phải xử lý, không phải optional)

1. **Cold-start không phải edge case, mà là trường hợp chủ đạo** (mục XVIII spec gốc coi 4 nhóm user là ngang hàng, nhưng thực tế 72% dữ liệu là "new/1-shot user"). → `PopularityTool`/content-based fallback phải là **first-class path**, không phải nhánh phụ, trong Agent workflow (`architecture.md` §3.2).
2. **Sequential model chỉ train được trên ≤4.26% user** (117,742 user có ≥5 interaction) sau k-core filtering — đây khớp với ngưỡng `min_user_interactions: 5` đã đặt sẵn ở `configs/data.yaml` (không phải chọn tuỳ ý — 5-core cũng là ngưỡng phổ biến trong literature sequential rec cho Amazon, ví dụ SASRec). **Giữ nguyên ngưỡng 5/5**, nhưng phải ghi rõ trong báo cáo cuối: sequential model chỉ đại diện cho ~4% user, không đại diện toàn bộ population — bắt buộc phải báo cáo metric riêng cho warm vs cold segment (đã có trong `experiment_plan.md` §5), không gộp chung.
3. **Time span 24.8 năm** — hành vi 1998 và 2023 rất khác nhau (console, xu hướng giá). Cần cân nhắc: có nên cắt bớt dữ liệu quá cũ (ví dụ chỉ giữ từ 2015+) để giảm concept drift? → ghi nhận là quyết định cần cân nhắc ở Phase 3, xem `decisions.md` D-008.
4. **Domain CHÍNH THỨC hoá:** `Video_Games` được chốt làm domain chính thức (không còn "tạm thời") — độ sparsity cao là đặc trưng hệ thống của Amazon Reviews nói chung (không riêng domain này), nên đổi domain khác nhiều khả năng không giải quyết được vấn đề cold-start-dominant.

## 12. Việc còn BLOCKED (cập nhật)

```
BLOCKED: chưa chạy được k-core filtering thật (min_user=5, min_item=5) 
  trên toàn bộ dữ liệu để biết chính xác kích thước tập "warm" sau lọc 
  (con số 117,742 là trước k-core 2 chiều — sau khi lọc thêm theo item 
  có thể giảm tiếp).
REASON: cần chạy trên máy người dùng (file quá lớn để upload), chưa có
  script Phase 3 hoàn chỉnh.
REQUIRED ACTION: xem Phase 3 — sẽ cung cấp script chạy local tương tự
  Phase 2, người dùng chạy và paste report lại.
```

- `BLOCKED`: chưa tải thật dataset → **Đã resolve** (§1.3, §11).
- `BLOCKED`: chưa xác định ngưỡng cụ thể cho "sparse" và "evolving-interest" → **Đã resolve một phần**: median=1 interaction/user trong dữ liệu thật gợi ý `sparse_threshold` hợp lý là 2-4; "evolving-interest" vẫn BLOCKED, cần dữ liệu category theo thời gian, chưa làm ở Phase 2.
- **REQUIRED ACTION còn lại**: chạy k-core filtering thật 2 chiều ở Phase 3 để biết chính xác kích thước tập "warm" sau lọc.
