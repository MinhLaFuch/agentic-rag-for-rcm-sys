# So sánh độ khó giao thức đánh giá — 7 repo đã clone vs giao thức project

Ngày: 2026-11-22. Phạm vi: read-only + emulation offline. Không sửa `src/`,
không gọi LLM, không train.

**Artifacts:**
- `protocol_emulation.py` — emulator 8 giao thức × 3 baseline × 5 seed trên 196
  held-out target của campaign_005 exp_5 (as_of=1617737606549,
  `historical_static_catalog`).
- `protocol_emulation_results.json` — mean±std toàn bộ metric.
- `negative_stats.py` / `negative_stats.json` — độ cứng của negative
  (category overlap, popularity gap).
- `METRICS_FORMULAS.md` — cách tính điểm từng repo: công thức trích từ
  code + ví dụ số + quirks làm inflate metric.

**Data anchors (giống `run_agent_eval`, eval_on=validation):**
- Popularity = interaction count trên **fit split** (`train.parquet`,
  48.77M rows) — causal pre-as_of, cùng proxy `temp.item_popularity` của
  commit dc100d1. Tiebreak `item_idx` (≈ `item_id` của FilterTool).
- Universe = `items.first_seen_ts <= as_of` → **2,003,873 / 2,637,776** item
  nhìn thấy tại as_of.
- 196 target / 152 request; 96/152 user có fit history (56 user cold →
  `same_category` fallback về popularity).
- Category = node sâu nhất của `item_categories` (chỉ có cho
  Electronics/Toys_and_Games/Video_Games — 3 domain của split này).

---

## 1. Kết luận (10 dòng)

1. Xếp độ khó tăng dần: **BiLLP/T-PRA** (env tuần tự, metric custom — không
   so được) < **ItemRAG/MemRec/iAgent** (pool 10, uniform negative, request
   giàu thông tin) < **InteRecAgent ranking** (pool 20) < **InteRecAgent
   retrieval** (full-catalog Recall@5) ≈ **project** (full-catalog,
   1 held-out target, request tối thiểu).
2. Pool nhỏ đồng nghĩa **không đo retrieval**: target được đặt sẵn vào pool,
   model chỉ cần re-rank 9–19 item. iAgent/MemRec/ItemRAG không có bước
   "tìm item trong catalog" nào được đánh giá.
3. Trên dữ liệu của ta, **baseline tầm thường `popularity` đã đạt
   HR@1=0.527 / NDCG@5=0.662 trên pool-10 uniform** — ngang headline
   H@1≈0.49–0.58 của ItemRAG. Phần lớn "thành tích" của pool-10 đến từ việc
   negative uniform phần lớn là item đuôi ít phổ biến còn target lệch về
   item phổ biến.
4. Cùng pool-10 nhưng negative lấy **theo popularity** thì popularity
   baseline sụp còn HR@1=0.049 — tức "độ khó" phụ thuộc hoàn toàn vào cách
   sample negative, và không repo nào trong 6 repo dùng popularity/catneg
   cho eval chính.
5. Full-catalog của ta khó hơn pool-10 uniform ~**116×** ở HR@10
   (popularity baseline: 0.005 vs 0.592), ~**154×** so với pool-20
   (0.005 vs 0.771); random HR@10 = k/2.0M ≈ 5e-6.
6. Request của literature chứa nhiều thông tin hơn request của ta
   (instruction/instruction+review/ user-simulator biết target), trong khi
   request campaign_005 chủ yếu là "gợi ý tương tự <seed>" hoặc filter trơn.
7. Metric của BiLLP/T-PRA (Len/Reach/Rtraj, Acce/IoR/Coh) đo hành vi
   tuần tự nhiều lượt, không tương thích top-k — không xếp vào cùng thang.
8. Kết luận thực dụng: con số HR@1≈0.5/NDCG@5≈0.67 của các paper pool-10
   **không thể so trực tiếp** với bất kỳ con số nào của project; nếu trích
   dẫn phải báo kèm "pool=10, 1+9 uniform negative, không đo retrieval".
9. Điểm làm tăng điểm lớn nhất của họ: (a) candidate pool nhỏ có sẵn target,
   (b) negative uniform = item tail dễ loại, (c) request giàu mô tả target,
   (d) một số repo retry/bỏ case lỗi làm tăng mẫu số thuận lợi.
10. Project nên giữ full-catalog làm metric chính, chỉ thêm "sampled-pool"
    như metric phụ khi so literature, và luôn báo baseline popularity/CF.

---

## 2. Thẻ giao thức từng repo (Phase A — đọc code, không chạy)

| Trường | iAgent | MemRec | ItemRAG | BiLLP | T-PRA | InteRecAgent | **Project** |
|---|---|---|---|---|---|---|---|
| Dataset | InstructRec (Books/Movietv/Goodreads/Yelp) | InstructRec (Books/Goodreads/Movietv/Yelp) | "latest Amazon Reviews" (Sports/Toys/Beauty/Arts&Crafts) | Steam + Amazon-Book (≥90 interact → rất đặc) | Steam + Amazon-Book | Steam, MovieLens-10M, Amazon Beauty | multi_domain: Electronics/Toys/Video_Games |
| Tiền xử lý | LOO last-item; `ranked_lists` precomputed | LOO; warmup memory rounds | LOO; 1000 users; last-11 history | filter ≥5 (Steam rating rule), ≥90 (Book) | seq ≥20; split 80/20 | LOO; tools train train+val | temporal split; as_of causal |
| Chia dữ liệu | held-out last item | held-out + sampled 1k users | held-out last purchase | train/test env riêng | 80/20 sequences | LOO + simulator data | validation targets, fit=train |
| Test set | toàn bộ eval split của InstructRec | 1k-user subset (sweep) | 1000 users × 3 runs | sampled target items | sampled sequences | 1000 sim instances (500 one-turn, 100 lifelong) | 152 req / 196 target |
| Candidate pool | `ranked_list`/`pure_ranked_list` từ dataset (độ dài `chưa xác minh`, prompt yêu cầu rerank list dài 10 — `model.py:208`) | **10** = 1 target + 9 neg (`trainer_memrec.py:59`, `:309-315`) | **10** = target + `np.random.choice(total_items, 9)` (`evaluation.py:108-113`) | không có pool — agent đề xuất tuần tự, grounding NN toàn catalog | tương tự BiLLP | retrieval: full catalog (buffer cap 1000, `one_turn_eval.py:266-268`); ranking: **pool 20** = 1+19 (paper Table 5; `neg_item_sample` bị comment `one_turn_eval_ranking.py:242-248`, `--k 20` `:330`) | **toàn catalog** 2.0M visible |
| Negative sampling | nằm sẵn trong ranked_list (không rõ) | uniform `all_items - user_history - {target}` (`:309`) | uniform toàn `total_items`, **không loại history/target** (`evaluation.py:111`) | không áp dụng | không áp dụng | `chưa xác minh` (data file tạo ngoài repo) | — |
| Metric | HR/NDCG/MRR @1,3,5 (`model.py:21-35,197-199`); MRR=−1 khi miss → retry ≤3 (`:201-203`) | Hit/NDCG/MRR @1,3,5,10 (`configs/common.yaml:5-6`, `trainer_memrec.py:1128-1146`) | HR/NDCG @1,3,5 (`evaluation.py:9-25`) | Len/Reach/Rtraj (custom) | Acce/IoR/Coh (custom) | sim: Hit@5+AT (rapidfuzz `hit_judge`, `user_simulator.py:387-477`); one-turn: Hit; ranking: NDCG@20 (`one_turn_eval_ranking.py:255-320`); retrieval Recall@5 chỉ có trong paper — **không thấy code tính Recall** | recall@k trên output agent vs 196 target |
| Xử lý lỗi LLM | parse fail → retry 3; miss → retry với hint; case vẫn tính (MRR=−1 → retry, cuối cùng vẫn ghi) | `chưa xác minh` chi tiết | `chưa xác minh` | grounding NN luôn map về item thật | grounding NN | `get_rank` trả −1 → NDCG=0 (`one_turn_eval_ranking.py:275-290`); miss tính 0, không bỏ mẫu | miss tính 0 |
| Thông tin trong request | `instruction` (InstructRec, sinh từ target) + title/desc/review của history (`model.py:60-78`); i²Agent thêm pos/neg profile | instruction + history + memory graph | purchase history + enriched item text | sequential env, hidden target | hidden target + preference pairs | user-simulator multi-turn (user giấu target đến khi hit); one-turn: context+question | text request tối thiểu + seed_item/category/filters |
| Thông tin cho model | full ranked list (id) + knowledge string | candidates (id+text?) + facets | 10 candidates kèm title+summary+co-purchase | item names qua grounding | item names | candidate titles + tool outputs | catalog metadata qua tools |
| Retrieval có đo? | **Không** — ranked_list cho sẵn | **Không** — candidates cho sẵn | **Không** (precompute offline) | một phần (grounding=NN retrieval nhưng metric không đo recall) | tương tự | **Có** — retrieval eval riêng Recall@5 full catalog | Có (đây là bottleneck #1) |
| Metric headline | i2Agent Books HR@1=35.1/NDCG@3=45.6; Movietv HR@1=46.4 (`framework_review/REPORT.md` Table 2/3) | H@1 +29% vs i2Agent Goodreads; +34% vs naive Books (paper, số tuyệt đối `chưa xác minh`) | H@1: Beauty 49.1, Toys 49.5, Sports 51.6, Arts 57.8 (Table 1) | Rtraj 42.4 Amazon / 69.2 Steam | Acce ~0.42-0.65 (Table 1) | Hit@5: Steam .87/Movie .85/Beauty .54; NDCG@20: .60/.64/.40; retrieval Recall@5: 65/52/30% | campaign_005 exp_5: 0 target tới rank_input; popularity ceiling r@10≈1.5% (rating_number) / HR@10=0.5% (causal) |

**Repo không có script eval riêng:** BiLLP, T-PRA (chỉ có env/training code;
metric tính trong training loop/eval notebooks — `chưa xác minh` script cụ thể).
VibeMus: **không áp dụng** (sinh nhạc, LLM-judge rubric, không phải recsys).

---

## 3. Bảng emulation (mean ± std, 5 seed, 196 target)

`protocol_emulation_results.json`. HR@10=1.0 ở pool-10 là hiển nhiên
(pool=10 → mọi target đều "hit@10") — không dùng để so.

### pool10_uniform (≈ MemRec/ItemRAG/iAgent)

| baseline | HR@1 | HR@3 | HR@5 | NDCG@5 | NDCG@10 |
|---|---|---|---|---|---|
| random | .108±.311 | .328±.469 | .507±.500 | .304 | .460 |
| popularity | **.527±.499** | .711±.453 | **.775±.418** | **.662** | .729 |
| same_category | .504±.500 | .709±.454 | .775±.418 | .653 | .720 |

### pool20_uniform (≈ InteRecAgent ranking)

| baseline | HR@1 | HR@5 | HR@10 | NDCG@5 | NDCG@20 |
|---|---|---|---|---|---|
| random | .053±.224 | .251±.434 | .514±.500 | .150 | .355 |
| popularity | **.430±.495** | .708±.455 | .771±.420 | .579 | **.654** |
| same_category | .394±.489 | .707±.455 | .772±.419 | .562 | .636 |

### pool100_uniform

| baseline | HR@1 | HR@5 | HR@10 | HR@20 | NDCG@5 | NDCG@20 |
|---|---|---|---|---|---|---|
| random | .009±.095 | .050±.218 | .116±.321 | .239±.426 | .030 | .081 |
| popularity | .228±.419 | .493±.500 | .592±.492 | .688±.463 | .364 | .421 |
| same_category | .149±.356 | .459±.498 | .591±.492 | .688±.463 | .307 | .375 |

### Biến thể negative (pool10 / pool100)

| giao thức | baseline | HR@1 | HR@5 | NDCG@5 |
|---|---|---|---|---|
| pool10_popneg | popularity | .049±.216 | .322±.467 | .180 |
| pool10_popneg | same_category | .056±.230 | .330±.470 | .187 |
| pool100_popneg | popularity | .002±.045 | .013±.114 | .008 |
| pool100_popneg | same_category | .007±.084 | .020±.141 | .014 |
| pool10_catneg | popularity | .480±.500 | .765±.424 | .632 |
| pool10_catneg | same_category | .477±.499 | .765±.424 | .631 |
| pool100_catneg | popularity | .190±.392 | .436±.496 | .318 |
| pool100_catneg | same_category | .178±.382 | .436±.496 | .313 |

### full_catalog (giao thức của project)

| baseline | HR@1 | HR@3 | HR@5 | HR@10 | HR@20 | NDCG@5 |
|---|---|---|---|---|---|---|
| random | 0 | 0 | 0 | 0 | 0 | 0 |
| popularity (causal) | 0 | .005 | .005 | .005 | .005 | .003 |
| same_category | 0 | 0 | 0 | 0 | 0 | 0 |

(random full-catalog: HR@k = k/2,003,873 — dưới độ phân giải của 196 mẫu;
chạy mô phỏng cho kết quả 0 ở mọi k≤20.)

### Độ cứng negative (`negative_stats.json`, pool-100 scale)

| variant | category overlap (mean/median) | popularity gap (median) |
|---|---|---|
| uniform | 0.005 / 0.002 | **+889k** (target phổ biến hơn negative rất xa) |
| popneg | 0.005 / 0.002 | **−66k** (negative phổ biến hơn target → khó hơn cho popularity baseline) |
| catneg | **0.992 / 1.0** | +660k |

→ Negative uniform gần như toàn item tail không liên quan; target held-out
lệch mạnh về item phổ biến. Đây là lý do popularity baseline "miễn phí"
đạt HR@1≈0.5 trên pool-10.

### Lift so với random (HR@5, baseline/random)

| giao thức | popularity | same_category |
|---|---|---|
| pool10_uniform | 1.53× | 1.53× |
| pool20_uniform | 2.82× | 2.82× |
| pool100_uniform | 9.86× | 9.18× |
| pool10_popneg | 0.64× | 0.66× |
| pool100_popneg | 0.24× | 0.37× |
| pool10_catneg | 1.49× | 1.49× |
| pool100_catneg | 8.71× | 8.71× |
| full_catalog | ≫ (random ≈ 0) | ≫ |

(Lưu ý: lift nhân với xác suất nền k/N — pool càng nhỏ lift "ảo" càng
lớn vì random đã cao.)

---

## 4. Đặt headline của họ vào thang của ta

So sánh **tham khảo** — khác dataset/domain (không có Beauty/Books trong
split của ta; chỉ Electronics/Toys/Video_Games, và Video_Games chỉ 13
target <30 → không đủ kết luận theo domain).

| Repo | Headline paper | Baseline tầm thường cùng giao thức trên data ta | Nhận định |
|---|---|---|---|
| ItemRAG | H@1 49–58 (pool 10) | popularity HR@1=**0.527**, same_cat 0.504 | Headline ≈ popularity baseline; không vượt baseline tầm thường nào đo được |
| MemRec | H@1 +29~34% vs baselines (pool 10) | popularity HR@1=0.527 | Số tuyệt đối `chưa xác minh`; pool-10 uniform quá dễ để phân biệt method |
| iAgent | HR@1 32–46 (pool ~10) | popularity HR@1=0.527 | Cùng nhận định; thêm request giàu instruction |
| InteRecAgent ranking | NDCG@20 0.40–0.64 (pool 20) | popularity NDCG@20=**0.654** | Baseline tầm thường ngang/vượt headline paper trên data ta |
| InteRecAgent retrieval | Recall@5 30–65% **full catalog** | popularity full-catalog HR@5=0.005 | Khác biệt lớn nhất — nhưng dataset của họ nhỏ hơn nhiều (Steam ~ games, MovieLens, Beauty cũ) và metric Recall@5 ≠ HR@5; **chưa so trực tiếp được**, chỉ nói protocol của họ ở bước retrieval vẫn là full-catalog → gần ta nhất |
| BiLLP/T-PRA | Rtraj/Acce custom | không áp dụng | Metric không top-k, không so được |

**Cạm bẫy diễn giải:** pool-10 uniform trên data ta cho popularity
HR@5=0.775 — cao hơn headline H@1 của hầu hết paper. Nếu một method đạt
H@1=0.5 trên pool-10, câu hỏi đúng là "nó có hơn popularity baseline
0.527 không?", không phải "nó tốt không".

---

## 5. Bảng độ khó

| | iAgent | MemRec | ItemRAG | BiLLP | T-PRA | InteRecAgent | Project |
|---|---|---|---|---|---|---|---|
| Không gian ứng viên | ~10 (ranked_list) | 10 | 10 | toàn catalog (grounding) | toàn catalog | retrieval: full; ranking: 20 | 2.0M |
| random HR@10 | ~1.0 (pool=10) | 1.0 | 1.0 | n/a | n/a | retrieval: ~0 | ~5e-6 |
| Baseline mạnh nhất (trên data ta) | popularity HR@1 .53 | popularity HR@1 .53 | popularity HR@1 .53 | n/a | n/a | popularity NDCG@20 .65 (pool20) | popularity HR@10 .005 |
| Độ cứng negative | `chưa xác minh` | uniform tail (dễ) | uniform toàn catalog, không loại history | n/a | n/a | `chưa xác minh` | n/a |
| Thông tin request (0-3) | 2 (instruction từ target + review history) | 2 | 1-2 (history + enriched text) | 1 (env tuần tự) | 1 | 2 (simulator biết target gián tiếp) | 0-1 (seed/category/filters) |
| Lỗi LLM làm tăng điểm? | Có thể (retry tới khi hit, MRR=−1 retry) | `chưa xác minh` | `chưa xác minh` | grounding luôn "cứu" item bịa | tương tự | miss=0 nhưng hit_judge fuzzy 80-90 → generous | miss=0 |
| Đo retrieval? | Không | Không | Không | Không (metric khác) | Không | Có (Recall@5) | Có (bottleneck #1) |

---

## 6. Điểm làm tăng điểm của họ so với ta (xếp theo ảnh hưởng ước lượng)

1. **Target nằm sẵn trong candidate pool** — model không phải retrieve;
   mọi metric chỉ đo re-rank 9–19 item. Bằng chứng: `evaluation.py:108-113`
   (ItemRAG), `trainer_memrec.py:309-315` (MemRec), `model.py:60`
   `ranked_list` cho sẵn (iAgent). Ảnh hưởng: lớn nhất — đây là lý do
   HR@1≈0.5 achievable bởi popularity baseline.
2. **Negative uniform = item tail** — 99.5% negative không cùng category
   target, phần lớn unpopular; target held-out lệch popular → popularity
   baseline thắng gần như miễn phí. Bằng chứng: `negative_stats.json`
   (cat_overlap 0.005, pop_gap +889k) + `protocol_emulation_results.json`
   pool10 popularity HR@1=0.527.
3. **Request giàu thông tin / rò rỉ nhẹ** — InstructRec instruction được
   sinh để mô tả target; iAgent còn cho review của history items
   (`model.py:73-78`); InteRecAgent user-simulator dẫn dắt user theo
   target. Ảnh hưởng: lớn với LLM ranker, nhưng baseline popularity không
   cần request → phần chênh lệch method-vs-method bị che.
4. **Metric forgiving** — hit_judge fuzzy partial_ratio>80
   (`one_turn_eval.py:205-211`, `user_turn`... `user_simulator.py:387`),
   NDCG@20 trên pool 20 (k=pool → HR@20 luôn=1), iAgent retry khi miss.
   Ảnh hưởng: trung bình.
5. **Dataset nhỏ + dense** — MemRec/InstructRec, ItemRAG 1000 users,
   InteRecAgent Beauty/Steam catalog nhỏ hơn 2.6M của ta nhiều bậc;
   catalog nhỏ → negative "ngẫu nhiên" vẫn gần nghĩa hơn. Ảnh hưởng:
   trung bình (không định lượng được trên data ta).
6. **Không đo retrieval** — 4/6 repo (iAgent, MemRec, ItemRAG + ranking
   của InteRecAgent) không đánh giá khả năng tìm item; điểm retrieval
   của ta (0 target tới rank_input) vô hình trong protocol của họ.
   Ảnh hưởng: lớn về mặt so sánh, không phải về metric.

---

## 7. Đề xuất khung đánh giá 2 Protocol cho project

1. **Thiết kế 2 Protocol bổ trợ (thay vì phụ thuộc vào sampled negative pool):**
   - **Protocol 1 — Full-Catalog Evaluation (Hard / Deployment Setting):**
     Giữ nguyên toàn bộ visible universe (`first_seen_ts <= as_of`, ~2.00M items)
     làm không gian tìm kiếm. Đo đồng thời khả năng retrieval toàn cục,
     chọn công cụ của agent và chống nhiễu liên miền.
   - **Protocol 2 — Category-Constrained Evaluation (Category-level Setting):**
     Giới hạn tập ứng viên theo **toàn bộ visible items thuộc một category
     xác định** (loại bỏ `fit` history, **không dùng random negative sampling**),
     tránh hoàn toàn bias `uniform` vs `popneg`. Trong `protocol_emulation.py`
     đã chuẩn hóa 3 biến thể kiểm soát bias:
     - `category_coarse`: toàn bộ `(domain, main_category)` của target chính
       (fallback `domain` nếu thiếu). Phù hợp cho bài toán constraint-given.
     - `category_fine_min100`: leaf category (`item_categories`), tự động lùi
       lên `(domain, main_category)` rồi `domain` khi `|pool| < 100` để tránh
       các category siêu nhỏ cho `Recall@10 = 1.0` một cách tầm thường.
     - `category_history_coarse`: biến thể **non-oracle** (zero target leakage)
       chỉ suy ra `(domain, main_category)` từ lịch sử `fit` của user (cold
       user fallback về `full_catalog`).
     Mỗi biến thể đều ghi kèm `pool_stats` (`min`, `p25`, `median`, `mean`, `max`
     và `targets_in_pool_rate`).
2. **Baseline bắt buộc đi kèm mọi con số:** `popularity` (causal fit-count,
   đúng proxy dc100d1) và `same_category_as_history` — cả hai đã có
   implementation tham chiếu trong `protocol_emulation.py` (tính theo request
   với loại `fit` history và `std` theo seed). Báo cả "lift vs popularity" lẫn
   "lift vs random-expected".
3. **Khi trích số paper (sampled-pool):** luôn kèm (a) kích thước pool, (b) cách
   sample negative, (c) metric có đo retrieval không, (d) cỡ catalog. Một dòng
   checklist đủ — vd "ItemRAG H@1=49.1 trên pool-10 uniform, không đo
   retrieval, catalog ~vài chục nghìn".
4. **Cảnh báo cụ thể:** mọi claim "HR@1 > 0.4" trên pool ≤20 uniform
   nên mặc định nghi ngờ — trên data ta popularity baseline đã đạt 0.43–0.53.
   Ngưỡng có nghĩa chỉ xuất hiện khi method vượt popularity baseline rõ
   rệt (vd >0.7 trên pool-10) hoặc khi negative khó hơn (`popneg`/`catneg`
   hoặc `category_constrained` ở Protocol 2).
5. **Với InteRecAgent nói riêng:** chỉ bước retrieval (Recall@5 full
   catalog) là so được với project; ranking NDCG@20 của họ đo re-rank
   trên pool 20 — tương đương "oracle retrieval" của ta, không phải
   end-to-end.

---

## 8. `chưa xác minh` (gộp)

- **iAgent:** độ dài `ranked_list`/`pure_ranked_list` trong InstructRec
  (prompt yêu cầu output length 10 — `model.py:208` gợi ý pool≈10 nhưng
  không xác nhận); negative sampling của ranked_list; exact LLM model.
- **MemRec:** số tuyệt đối H@K/N@K trong Tables 2–3 (dump chưa parse);
  Amazon version của InstructRec; chi tiết xử lý case LLM lỗi.
- **ItemRAG:** citation version "latest Amazon Reviews"; xử lý LLM output
  sai format; `self.total_items` có loại item đã interact không (code
  `evaluation.py:111` không thấy exclusion → có thể **có** trùng history).
- **BiLLP/T-PRA:** script eval cụ thể (metric trong training loop);
  exact LLM backbone size trong paper.
- **InteRecAgent:** cách `simulator_test_data.jsonl` được sinh (pool
  ranking 20 suy ra từ `--k 20` + paper Table 5, code sample bị comment);
  negative sampling của retrieval eval; Recall@5 retrieval không thấy
  code tính (có thể trong notebook ngoài repo).
- **Emulation:** `same_category` dùng deepest category = node cuối
  `item_categories` (browse-path order giả định root→leaf — chưa verify
  trên mọi domain); user majority category trên fit history, 56/152 user
  không có history → fallback popularity; popularity-sampled negatives
  không rút được item count=0 (chiếm đa số universe) — đây là semantics
  "sample ∝ popularity" chuẩn nhưng làm pool popneg thiên về head items.
- **Domain subset:** chỉ có Electronics(141)/Toys(42)/Video_Games(13);
  không có Beauty/Books → không emulation same-domain cho ItemRAG/
  MemRec/iAgent; Video_Games 13 < 30 → không kết luận per-domain.
