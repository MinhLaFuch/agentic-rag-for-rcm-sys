# Cách tính điểm của từng repo — công thức + ví dụ

Bổ sung cho `REPORT.md`. Mọi công thức trích từ code (file:dòng); chỗ nào
không đọc được ghi `chưa xác minh`.

## 0. Ký hiệu chung

- `pos` = vị trí **0-based** của target trong danh sách xếp hạng
  (pos=0 → rank 1).
- `k` = cutoff.
- Hit/HR@k: binary — target có nằm trong top-k không.
- NDCG@k ở tất cả repo đọc được đều là **binary relevance, 1 relevant item**:
  `DCG@k = 1/log2(pos+2)` nếu `pos<k`, ngược lại 0; `IDCG@k = 1`
  (target ở rank 1 → `1/log2(2)=1`). Vì chỉ 1 relevant item nên
  **NDCG@k = 1/log2(pos+2) khi hit, else 0** — không cần chia IDCG.
- Metric báo cáo = trung bình trên các case (user/request/target).

Bảng giá trị tham chiếu (dùng cho mọi ví dụ dưới):

| pos (0-based) | rank | HR@5 | NDCG@5 | MRR |
|---|---|---|---|---|
| 0 | 1 | 1 | 1.000 | 1.000 |
| 1 | 2 | 1 | 0.631 | 0.500 |
| 2 | 3 | 1 | 0.500 | 0.333 |
| 3 | 4 | 1 | 0.431 | 0.250 |
| 4 | 5 | 1 | 0.387 | 0.200 |
| 5 | 6 | 0 | 0 | 0.167 |
| 9 | 10 | 0 | 0 | 0.100 |

## 1. iAgent — `iAgent/model.py:21-35`

```python
def cal_ndcg_hr_single(answer, ranking_list, topk=10):
    rank = ranking_list.index(answer)          # exact match, 0-based
    HIT = NDCG = 0
    MRR = 1.0 / (rank + 1.0)                   # tính TRƯỚC khi check topk
    if rank < topk:
        NDCG = 1.0 / np.log2(rank + 2.0)
        HIT = 1.0
    # ValueError (answer không có trong list) -> HIT=NDCG=MRR=-1
```

- `answer` = asin của target; `ranking_list` = output LLM (rerank list).
- **Quirk 1:** `MRR = 1/(rank+1)` tính trên **toàn list**, không cắt topk —
  khác MRR chuẩn (thường cũng vậy, nhưng ở đây rank có thể > topk vẫn tính).
- **Quirk 2:** miss → cả 3 metric = **−1** (không phải 0), rồi retry tối đa
  3 lần (`model.py:201-203`). Nếu vẫn miss, case được ghi với giá trị âm —
  cần xem cách aggregate cuối (có thể bị loại khỏi trung bình → **inflate**).
  `chưa xác minh` đoạn aggregate.
- Eval gọi với topk=1,3,5 (`model.py:197-199`) → HR@1/3/5, NDCG@1/3/5, MRR.
- **Ví dụ:** rerank_list = [a,b,c,d,...], answer=d → rank=3.
  HR@5=1, NDCG@5=1/log2(5)=0.431, MRR=0.25. Nếu answer không có trong list
  → (−1,−1,−1) → retry.

## 2. MemRec — `memrec/src/train/trainer_memrec.py:1128-1146`

```python
positions = np.array(ranking_positions)       # pos 0-based của target
Hit@k  = mean(positions < k)
NDCG@k = mean( where(positions<k, 1/log2(positions+2), 0) )
```

- Eval candidate = 1 target + `n_eval_candidates-1` (=9) negative,
  `negative_pool = all_items - user_history - {target}` (`:309`) →
  **uniform, có loại history**.
- topk = [1,3,5,10] (`configs/common.yaml:6`); MRR bị comment/disable
  (`:1145-1146`) — "for consistency with baseline models".
- **Ví dụ:** pool 10, target pos=2 → Hit@5=1, NDCG@5=1/log2(4)=0.5.
  Trung bình trên users.

## 3. ItemRAG — `ItemRAG/evaluation.py:9-25`

```python
top_k = ranking[:k]
hr   = 1 if ground_truth in top_k else 0
ndcg = 1/math.log2(rank_index+2) if gt in top_k else 0   # rank_index 0-based
```

- `ranking` = output LLM sắp xếp **10 candidates**; `ground_truth` = test_item
  (luôn nằm trong input candidates — `evaluation.py:108-113`).
- k ∈ {1,3,5}; báo cáo HR/NDCG ×100 trên 1000 users × 3 runs.
- **Ví dụ:** LLM trả ranking [c9, c3, target, ...] → pos(target)=2:
  HR@1=0, HR@3=1, HR@5=1; NDCG@3=1/log2(4)=0.5, NDCG@5=0.5.
- **Quirk:** candidate = `np.random.choice(total_items, 9)` **không loại
  item trong history** → negative có thể là item user đã mua (dễ bị LLM
  loại đúng → vừa làm khó vừa hơi leak-free may mắn).

## 4. InteRecAgent — `RecAI/InteRecAgent/eval/`

Hai tầng metric khác nhau:

**(a) Conversation/simulator eval** (`user_simulator.py:387-477`,
`one_turn_eval.py:205-229`):
- `hit_judge(msg, target, thres)`: normalize (lowercase + strip non-alnum)
  rồi `rapidfuzz.partial_ratio(msg, target) > thres` → **fuzzy match**,
  thres=80 (one-turn) / 90 (ranking). Title gần giống cũng tính hit.
- `hit_ratio = hit_num / N`; `AT` = trung bình turn đạt hit.
- **Không phải top-k** — đo "agent có nhắc target trong output không".

**(b) Ranking eval** (`one_turn_eval_ranking.py:255-320`):
- LLM trả JSON `{item_name: rank}` (rank do **LLM tự gán**, 1-based).
- `get_rank`: parse fail / target không có trong dict → thử fuzzy-match key
  (thres 90) → vẫn không → **rank = −1**.
- `NDCG@k = mean( 1/log2(rank+1) nếu rank>0 else 0 )`, k=20 mặc định
  (`--k 20`, `:330`) = đúng pool size → **NDCG@20 gần như = HR@20**
  (mọi case parse được đều "hit").
- **Quirk:** metric phụ thuộc LLM tự đánh số rank. Công thức
  `1/log2(rank+1)` với rank 1-based tương đương chuẩn
  `1/log2(pos0+2)`: rank=1 → 1.0; rank=2 → 0.631; rank=3 → 0.5.
- **Ví dụ:** pool 20, LLM trả `{itemA:1, target:3, ...}` →
  NDCG@20 = 1/log2(4) = 0.5. Nếu target vắng trong JSON → 0.

**(c) Retrieval eval (Recall@5 full catalog, Table 5 paper):**
- `chưa xác minh` — grep `recall` trong `eval/*.py` không thấy code tính;
  nhiều khả năng tính offline từ tool-track/buffer logs hoặc notebook.

## 5. BiLLP / T-PRA — metric custom, không phải top-k

- **BiLLP** (paper Table 3): `Len` = độ dài trajectory, `Reach` = reward
  trung bình mỗi round, `Rtraj` = tổng reward tích lũy. Agent đề xuất
  `recommend[item]` tuần tự trong env mô phỏng; reward từ
  `reward_mat` + distance penalty. **Công thức chính xác `chưa xác minh`**
  trong phần code đọc được (nằm trong env/training loop).
- **T-PRA**: `Acce` (accuracy tới target?), `IoR`, `Coh` — cùng họ
  sequential/proactive; `chưa xác minh` công thức.
- **Hệ quả:** không có HR/NDCG/Recall@k → không đặt chung bảng so với
  top-k metrics của project/paper khác.

## 6. Project — 2 chỗ tính điểm

**(a) Agent eval** (`experiments/.../run_1/scored.jsonl`, `metrics.json`,
k=10):
- Mỗi request có `targets` = tập item_idx held-out (1–3 target).
- Metric chính = **recall@k**: tỉ lệ target xuất hiện trong top-k item
  agent recommend cuối cùng (k=10). `n_recommended`, `task_success`...
  là các chỉ số phụ (tool calls, latency, cost).
- Khác biệt căn bản: agent **tự sinh danh sách** từ toàn catalog qua
  tools — không có candidate list cho sẵn.

**(b) Offline ranking eval** (`scripts/evaluation/ranking_eval.py:143-159`):
- `ranking_metrics_at_k(hits, n_rel, k)` — multi-relevant chuẩn:
  `recall@k = |relevant ∩ top-k| / n_rel` per user, trung bình; hits là
  binary matrix pred×k. Dùng cho ItemKNN/CF baselines, không phải agent.

## 7. Emulation của chúng ta (`protocol_emulation.py`)

```python
pos = vị trí 0-based của target trong pool/ranking
HR@k  = 1 nếu pos < k else 0          # per case, rồi trung bình
NDCG@k = 1/log2(pos+2) nếu pos<k else 0
```

- Pool protocols: `pos` = thứ hạng của target sau khi baseline sắp xếp
  pool (random shuffle / popularity / same_category).
- Full-catalog: `pos` = rank toàn cục trong popularity order
  (pop desc, item_idx asc) hoặc category-boosted order.
- Giống hệt công thức MemRec/ItemRAG/iAgent (trừ MRR và retry quirks).

## 8. Vì sao các con số "nhìn cao" của literature

Tổng hợp từ công thức + protocol:

1. **Pool nhỏ → pos nhỏ sẵn:** pool-10, kể cả xếp ngẫu nhiên cũng có
   HR@5≈0.5 kỳ vọng (5/10). Metric chỉ đo "xếp đúng trong 10", không đo
   "tìm được trong 2 triệu".
2. **NDCG@k với k=pool_size mất nghĩa:** InteRecAgent NDCG@20 trên pool 20
   → mọi case parse được đều có pos<20 → HR@20=1; NDCG phân biệt theo
   *vị trí LLM tự gán*, không phải vị trí thực trong catalog.
3. **Fuzzy hit_judge:** partial_ratio>80 → title gần-đúng tính hit,
   inflate thêm vài %.
4. **Retry-on-miss (iAgent):** miss → −1 → retry; nếu aggregate loại case
   fail thì mẫu số chỉ còn case "dễ" (`chưa xác minh` đoạn cuối).
5. **Negative uniform = tail items:** target lệch popular (pop_gap +889k
   trên data ta) → popularity baseline đạt HR@1=0.53 "miễn phí".

Ví dụ tổng hợp: ItemRAG báo Beauty H@1=49.1 trên pool-10. Đặt lên data
của ta, popularity baseline (không LLM, không history) đạt HR@1=0.527 —
tức method của họ chỉ cần **ngang một sort theo độ phổ biến** là đã tái
hiện headline, trước khi tính bất kỳ khả năng reasoning nào.
