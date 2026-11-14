# Case proposal — tuần 47 (Phase 3, chỉ đề xuất — CHƯA thêm dữ liệu)

Phạm vi: điều tra cách thêm test case dựa trên lỗi thật của campaign_001 (Phase 2).
Không sửa code `package/`, không thêm dòng nào vào dataset. Mọi đáp án kỳ vọng dưới
đây tính tay từ fixture, không lấy từ đầu ra hệ thống.

Bằng chứng nền: `docs/investigation_week47.md` (Phase 2), artifacts
`experiments/agent_eval/campaigns/campaign_001/`.

---

## 3.1 Hiện trạng benchmark (đếm bằng lệnh thật)

Lệnh: `wc -l package/evaluation/component/benchmarks/*_dataset*.jsonl
package/evaluation/multi_turn/conversations.jsonl` (chạy 2026, cwd=`src/`):

| File | Số dòng | Ghi chú |
|---|---|---|
| executor_dataset.jsonl | 18 | exec_001–exec_018 |
| integration_dataset.jsonl | 12 | int_001–int_012 |
| planner_dataset.jsonl | 26 | planner_001–planner_032 (thiếu vài số) |
| planner_dataset_backlog.jsonl | 6 | planner_002, 011, 020, 022, 027, 028 — `metadata.backlog=true` + `limitation` |
| grounding_dataset.jsonl | 35 | grounding_001–grounding_035 |
| memory_correctness_dataset.jsonl | 29 | correctness_001–correctness_031 |
| multi_turn/conversations.jsonl | 11 | 20 turns tổng |

### Loại phép đo

Tất cả benchmark component chấm **theo từng case** rồi aggregate thành tỷ lệ —
đây là **ước lượng tỷ lệ, cần CI**, không phải kiểm tra chức năng dạng đếm:

- planner: `PlannerBenchmark.score_component` trả 8 metric dạng rate
  (`planner_benchmark.py:91-178`); có sub-check chức năng (`plan_validity`,
  `step_validity_rate`) nhưng cũng là tỷ lệ trung bình.
- executor: `error_kind_accuracy`, `step_count_match`, `data_correctness`
  (`executor_benchmark.py:89-113`) — tỷ lệ.
- integration: `presented_ids_exact`, `item_fields_match`, `grounded_rate`
  (`integration_benchmark.py:130-166`) — tỷ lệ.
- grounding: `label_agreement` so với ngưỡng Jev (`grounding_benchmark.py:127-140`).
- memory_correctness: so khớp trường MemoryTool (`memory_correctness_evaluator.py:76`).
- multi_turn: tỷ lệ trên 20 turns / 11 hội thoại (`multi_turn_evaluator.py`).

### Độ rộng CI — Wilson 95% (tính bằng script, không ước lượng)

```python
# z=1.959964; lo,hi = (p + z²/2n ∓ z·sqrt(p(1-p)/n + z²/4n²)) / (1 + z²/n)
```

| n | p=0.5 | p=0.8 | p=0.9 |
|---|---|---|---|
| 26 (planner) | [0.321, 0.679] rộng 0.359 | [0.613, 0.910] rộng 0.297 | [0.729, 0.968] rộng 0.239 |
| 35 (grounding) | [0.343, 0.657] rộng 0.314 | [0.641, 0.900] rộng 0.258 | [0.758, 0.963] rộng 0.205 |

Kết luận: ở n=26–35, một tỷ lệ 0.8 có CI rộng ~0.26–0.30 — **chênh lệch nhỏ giữa
hai cấu hình không phân biệt được**; case mới chỉ nên thêm khi phân biệt được
cấu hình (đúng tinh thần mục 3.4), không phải để tăng n đơn thuần.

### Dữ kiện fixture dùng để tính tay (đã đối chiếu nhiều dataset)

`fixtures/create_test_meta.py`: 15 item `vg_a`–`vg_o` (Video_Games) + 2 item giá
null (`vg_null_a` Action, `vg_null_b` Puzzle) + 1 outlier `vg_outlier` $1000.
Bảng giá/category (index i → price ∈ {1,150,300} tuần hoàn; category):

| item | a | b | c | d | e | f | g | h | i | j | k | l | m | n | o |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| price | 1 | 150 | 300 | 1 | 150 | 300 | 1 | 150 | 300 | 1 | 150 | 300 | 1 | 150 | 300 |
| category | Action | Puzzle | RPG | Action | Puzzle | RPG | Action | Puzzle | RPG | Action | Strategy | Simulation | Sports | Racing | Adventure |

Đã kiểm chứng bảng này khớp `exec_001`: `price_max=50` → đúng 5 item giá $1
{vg_a,d,g,j,m}, ORDER BY rating_number DESC → [m,j,g,d,a] (`rating_number=50+i*10`,
`create_test_interactions.py`).

`FILTER_KEYS` (`package/tools/_schema.py:8-20`): domain, price_min, price_max,
include_missing_price, min_rating, min_rating_number, categories_any,
categories_all, store, title_contains, exclude_item_ids — **không có** negative
category filter → mọi case "exclude category X" phải vào backlog (tiền lệ:
`planner_011` limitation "no negative category filter").

User fixture liên quan (`create_test_interactions.py:60-90` + memory dataset):
- `u_null_prices`: 2 item `vg_null_a`(Action), `vg_null_b`(Puzzle), cả hai price
  NULL → MemoryTool `price_range=None` (memory_correctness dataset đã có expected
  `price_range: null` cho user này — case correctness tương ứng tồn tại).
- `u_equal_prices`: vg_a,d,g đều $1 → price_range suy biến [1,1].
- `u_outlier_price`: vg_a($1), vg_b($150), vg_outlier($1000) → price_range bị
  outlier kéo thành [1,1000] — hữu ích cho case "soft constraint".

Phân loại lỗi ref-null ở executor: `_resolve_path(None, ["max"])` → `KeyError`
→ `ValueError("...Step 1 ... returned: ...")` (`_helper.py:12-29,60-71`) → chứa
"step"+"not found" → `error_kind="bad_reference"` (`plan_executor.py:267-272`).

---

## 3.2 Case hồi quy từ 3 nguyên nhân Phase 2B

### Case R1 — ref tới trường null (`$1.price_range.max`)

| Trường | Giá trị |
|---|---|
| id dự kiến | `exec_019` |
| benchmark | **executor** (KHÔNG phải planner: plan `$1.price_range.max` hợp lệ về cú pháp nên planner benchmark không phạt được — `plan_validity` chỉ kiểm format/step tồn tại, `planner_benchmark.py:115-121`) |
| mục đích | Hồi quy cho nhóm lỗi lớn nhất của exp_9: 20 step-error do `$1.price_range.max` ref→null, quy thành 18/30 task-fail (investigation_week47.md:117; analyze_campaign_001_planner_errors.py): MemoryTool trả `price_range=None` (`memory_tool.py:112`) nhưng plan vẫn deref `.max` |
| input.steps | `[{"tool":"MemoryTool","args":{"user_id":"u_null_prices"}}, {"tool":"FilterTool","args":{"filters":{"price_max":"$1.price_range.max","domain":"Video_Games"},"limit":10}}]` |
| expected | `all_steps_ok=false`, `step_error_kinds=[null,"bad_reference"]`, `num_steps=2` |
| cách tính tay | Bước 1: `u_null_prices` có 2 item đều price NULL (`create_test_meta.py` vg_null_a/b) → `price_range=None` (đã có expected sẵn trong memory_correctness dataset). Bước 2: `_resolve_path(None,["max"])` → KeyError → ValueError chứa "step"/"not found" → `bad_reference` (`plan_executor.py:270-272`). Không dùng output hệ thống. |
| test hồi quy | `tests/evaluation/component/benchmarks/` — case-scoring test assert `error_kind_accuracy=1.0` cho exec_019; sau này nếu chọn phương án "bỏ arg khi ref=None" (Phase 2B 2B-a-i) thì expected đổi thành `step_error_kinds=[null,null]` + step_outputs không chứa price_max — test này chính là điểm chuyển đổi kỳ vọng. |
| tầm công cụ | **Nằm trong tầm** — executor chạy steps cho sẵn, MemoryTool/FilterTool có trong fixture (`planner_benchmark.py:61-64` dùng cùng `build_tools` + `for_planner_memory`). |

Bổ sung (backlog, không chấm): planner-level case "personalized cho
u_null_prices" với expected là plan **không chứa** `$1.price_range.max`. Lý do
backlog: `argument_correctness` chỉ so các key có trong expected
(`planner_benchmark.py:134-141`) — không biểu đạt được "cấm dùng ref này"; cần
metric mới (vd `forbidden_refs`) → ghi backlog kèm limitation.

### Case R2 — query quá rộng / dạng "NOT" planner tự chế

| Trường | Giá trị |
|---|---|
| id dự kiến | `exec_020` (SearchTool đã có exec_017 — case mới phải khác nhánh) |
| benchmark | executor |
| mục đích | SearchTool là nhánh gây timeout 5.3–5.4s trong campaign; trên fixture 18 item không tái hiện được timeout nhưng kiểm được nhánh **no-match** và **OR-token** |
| input.steps | `[{"tool":"SearchTool","args":{"query":"zzznomatch","limit":5}}]` |
| expected | `all_steps_ok=true`, `step_error_kinds=[null]`, `step_outputs=[{"item_count":0,...}]` — SearchTool trả ok với 0 kết quả (không throw) |
| cách tính tay | FTS5 query "zzznomatch" không token nào khớp title nào trong `create_test_meta` (mọi title chứa "Game") → 0 hit. Cần xác minh SearchTool không raise khi 0 match — CHƯA XÁC MINH, kiểm `search_tool.py` trước khi chốt expected (nếu raise → expected đổi `tool_error`). |
| test hồi quy | assert `data_correctness`/`step_outputs` item_count=0; phân biệt "empty result" vs "tool_error" — nhánh này chưa có case nào (exec chỉ có 1 SearchTool success). |
| tầm công cụ | Trong tầm nếu SearchTool ok-on-empty; nếu không → backlog. |

Case planner cho phát biểu "không dùng keyword NOT": `"show me games but not
Puzzle"` — planner thật đã viết `"toys NOT dolls"` vào query thay vì dùng
filter. Nhưng FilterTool **không có** negative category filter → expected đúng
không biểu đạt được → **backlog** (cùng limitation với planner_011/020/022/027;
ghi thêm observation rằng planner nên refuse/clarify thay vì nhét "NOT" vào
query — cần metric mới, vd cấm `query` chứa "not").

Timeout thật (FTS OR match ~200-400k docs trên corpus 678k items) **không thể
hồi quy trên fixture 18 item** — chỉ guard được gián tiếp (query ngắn hơn,
limit nhỏ hơn). Ghi rõ giới hạn; regression thật thuộc effort retrieval/corpus,
không thuộc benchmark này.

### Case R3 — câu không trả lời được (category không tồn tại)

| Trường | Giá trị |
|---|---|
| id dự kiến | `planner_033` |
| benchmark | planner |
| mục đích | Hồi quy 6 task-fail "unanswerable" của exp_9 (reflect=1 sửa được cả 6 bằng ask_user); hiện planner dataset chỉ có 1 case tag `unanswerable` |
| input.user_request | `"Show me games in the Underwater_Basket_Weaving category"` |
| expected | `steps=[]`, `question=<câu hỏi làm rõ>`, `requires_clarification=true` |
| cách tính tay | Tập category hợp lệ của fixture = {Action, Puzzle, RPG, Strategy, Simulation, Sports, Racing, Adventure} (`create_test_meta.py` categories list). `Underwater_Basket_Weaving` ∉ tập → không item nào thuộc category đó → câu hỏi không trả lời được bằng dữ liệu → planner phải clarify/empty steps. `refusal_to_guess=1` khi question≠null và steps rỗng (`planner_benchmark.py:148-151`). |
| test hồi quy | `refusal_to_guess` và `clarification_recall` trên case này; case mới phải fail trên hành vi cũ (planner_009-style: bịa FilterTool categories_any=["Underwater_Basket_Weaving"] → plan_validity vẫn 1 vì schema hợp lệ → chỉ `clarification_recall=0` phạt được — đúng kỳ vọng: metric phân biệt nằm ở clarification, không ở validity). |
| tầm công cụ | Trong tầm — planner benchmark có `requires_clarification`/`question` scoring sẵn. |

---

## 3.3 Bổ sung multi-turn: tiêu chí fail mới + hội thoại âm

### Trạng thái schema hiện tại

`TurnInput` (`multi_turn/_schema.py:20-76`) chỉ có: `expected_items`,
`expected_exclusions`, `absent_exclusions`, `expected_tool_calls`,
`expected_behavior` (text, không chấm). **Không có** `expect_no_result`,
`expect_clarification`, `max_steps_per_turn`, `turn_timeout_seconds`.
Evaluator chỉ tính `item_match_rate` khi `expected_items` non-empty
(`multi_turn_evaluator.py:174`) → turn mong đợi "không có kết quả" hiện **không
chấm được gì cả** (item_match bỏ qua, exclusion có thể vẫn check nhưng không đủ).

→ Bốn tiêu chí mới đòi hỏi sửa `_schema.py` (fields) + `multi_turn_evaluator.py`
(metrics) + `_agent_runner.py` (đếm steps/timeout per turn). Đây là **thay đổi
code**, không phải thêm data → các hội thoại dưới đây là **đề xuất thiết kế**,
chỉ thêm vào `conversations.jsonl` sau khi evaluator hỗ trợ; trước đó nếu thêm
sẽ là case "không chấm" → theo rule tuần 46 phải để ngoài dataset (hoặc backlog).

### Hội thoại âm đề xuất (2–3 cái, tính tay được trên fixture)

1. `conv_neg_clarification_trap` — t1: `"Recommend something nice"` (mơ hồ)
   `expect_clarification=true`; t2: user trả lời `"video games"` → expected_items
   tính từ fixture như conv_m1. Phân biệt được planner biết ask vs đoán.
   (Lưu ý conv_m5_clarification đã cover ý tưởng này ở mức text — case mới chỉ
   có giá trị khi `expect_clarification` thành metric thật; nếu không sẽ trùng.)
2. `conv_neg_no_result` — t1: `"Show me games under $0.50"` →
   `expect_no_result=true`. Tính tay: min price fixture = $1.0 (vg_a,d,g,j,m)
   → feasible set rỗng → agent phải trả "no results" chứ không bịa items.
   Hiện int_003 đã cover no_result ở component level; multi-turn version kiểm
   tra agent **giữ** trạng thái no-result qua turn sau (t2: `"ok what about
   under $2"` → 5 item $1 xuất hiện — kiểm session không bị poison bởi kết quả
   rỗng).
3. `conv_neg_runaway_steps` — t1: request tổng hợp ("find me something cheap
   and popular similar to what I like") với `max_steps_per_turn=4` — planner
   thật trong campaign sinh plan dài/retry; metric mới đếm steps thực thi.
   Tính tay: không cần expected_items chính xác — chỉ cần assert steps≤N và
   turn không timeout. CHƯA XÁC MINH agent hiện có vượt ngưỡng nào — cần số
   steps/turn từ trajectory campaign làm căn cứ chọn N.

`turn_timeout_seconds`: per-turn budget (đề xuất 60–120s, nhỏ hơn nhiều so với
experiment timeout 7200s) — cần `_agent_runner.py` đo per-turn; hiện chỉ có
per-conversation `timeout_seconds` (`_eval_step.py:138`).

---

## 3.4 Bổ sung executor / integration / grounding — ưu tiên phân biệt cấu hình

### Executor (hiện 18 case)

Coverage map (đếm bằng script): FilterTool 11, LookupTool 7, SimilarTool 2,
SearchTool 1, NoSuchTool 1; error kinds đã có: unknown_tool, unknown_args,
tool_error, bad_reference (nhiều vị trí), invented_id. **Thiếu:**

- **`exec_021` — chuỗi $ref THÀNH CÔNG qua FilterTool.candidates** (nhánh quan
  trọng nhất còn thiếu: exec_009 có `$1.candidates.*.item_id` nhưng step 2 bị
  bad_reference; exec_005 Similar→Lookup thành công nhưng không qua FilterTool).
  input: `[{"tool":"SimilarTool","args":{"items":["Video_Games::vg_a"],"top_k":5}},
  {"tool":"FilterTool","args":{"filters":{"price_max":100},"candidates":"$1.candidates","limit":10}}]`.
  expected: `step_error_kinds=[null,null]`; step_outputs step2 `item_count` và
  membership tính từ KNN fixture — **cách tính tay**: chạy `ItemKNNRecommender(10)`
  trên `create_test_interactions()` (deterministic, không LLM) lấy top-5 candidates
  của vg_a, giao với {price≤100} = loại vg_c,f,i,l,o ($300) → giữ phần còn lại.
  Đây là case phân biệt được cấu hình vì planner_memory/ref-resolution là nơi
  lỗi campaign xảy ra. **Lưu ý**: đáp án "tính tay" ở đây là tính bằng fixture
  script độc lập (oracle-style), không phải output hệ thống — chấp nhận được theo
  rule (tiền lệ `compute_memory_oracle.py`, `memory_oracle.py` đã làm đúng mẫu này).
- **`exec_022` — RankTool**: 0 case nào chạm RankTool dù planner dataset expect
  RankTool 2 lần. input: `[{"tool":"RankTool","args":{"user_id":"u_long", ...}}]`
  — cần đọc schema RankTool trước khi viết expected; CHƯA XÁC MINH args chính xác.
- **`exec_023` — empty-result success**: `FilterTool price_max=0.5` → ok +
  `item_count=0`. Tính tay: không item nào ≤$0.5 (min=$1.0). Phân biệt "empty ok"
  vs "tool_error" — int_003 đã cover ở integration nhưng executor-level chưa có.

### Integration (hiện 12 case)

Status coverage: ok×7, tool_error×3, no_result×2. Thiếu:

- **`int_013` — multi-step $ref chain thành công end-to-end** (exec_021 +
  compose): expected_status `ok`, `presented_item_ids` = tập giao KNN∩price đã
  tính tay, `min_items≥1`. Phân biệt được inference_mode template vs llm vì
  compose_answer là chỗ hai mode khác nhau (`integration_benchmark.py:18`).
- Không đề xuất thêm no_result/tool_error — đã đủ nhánh (int_003,004,006,009,011).

### Grounding (hiện 35 case)

**Ràng buộc cứng**: `grounding_benchmark.py:41-46` raise nếu thiếu Jev hoặc
evidence rỗng; `run_component` gọi `evaluate_product_reply_with_jev` (judge thật)
và `compose_answer` — **toàn bộ grounding benchmark cần credential Jev + (mode llm)
LLM**. Trong môi trường không credential, mọi case grounding mới đều **CHƯA chạy
được** — không thể verify.

Đề xuất (ghi nhận, hoãn triển khai tới khi có Jev):
- `grounding_036` — hallucination-bait trên evidence thiếu field (`null_fields`
  pattern đã có 1 case; mở rộng: evidence có `price=None` → answer không được bịa
  giá). expected: `hallucination_rate=0.0` — tính tay: claim về giá là unsupported
  vì evidence.price=null.
- `grounding_037` — prompt-injection trong user_request (đã có 3 case tag này;
  đề xuất variant injection yêu cầu bịa item không có trong evidence).

Hai case này chỉ nên thêm khi có Jev; nếu không sẽ là case không chấm được.

### Memory correctness (hiện 29 case)

Coverage user đã rộng: nonexistent, empty, null_prices, equal_prices,
outlier_price, dup_items, leakage×nhiều, love/hate variants. **Không đề xuất
thêm** — đã đủ nhánh tương ứng 3 nguyên nhân Phase 2B (u_null_prices chính là
fixture cho R1).

---

## 3.5 Bảng tổng hợp đề xuất

| id | benchmark | mục đích | expected (tóm tắt) | tính tay từ | test hồi quy | tầm công cụ |
|---|---|---|---|---|---|---|
| exec_019 | executor | ref→null price_range | step2 `bad_reference` | u_null_prices→price_range=None + `_resolve_path` KeyError | case-score test; điểm chuyển đổi nếu chọn phương án "bỏ arg" | ✅ trong tầm |
| exec_020 | executor | SearchTool no-match | ok + item_count=0 | FTS "zzznomatch" ∉ mọi title | assert empty-ok vs tool_error | ⚠️ cần verify SearchTool ok-on-empty |
| planner_033 | planner | category không tồn tại | steps=[] + question + requires_clarification | category set fixture ∌ requested | refusal_to_guess/clarification_recall | ✅ trong tầm |
| planner backlog mới | planner (backlog) | cấm `$1.price_range.max` / cấm "NOT" trong query | n/a — không chấm | — | cần metric mới (forbidden_refs) | ❌ backlog |
| conv_neg_* ×3 | multi_turn | tiêu chí fail mới | cần schema+evaluator | fixture như trên | metric mới | ❌ cần code trước |
| exec_021 | executor | $ref chain thành công qua candidates | [null,null] + item_ids | KNN fixture ∩ price≤100 | data_correctness | ✅ trong tầm |
| exec_022 | executor | RankTool coverage | theo schema RankTool | fixture interactions | error_kind/outputs | ⚠️ cần đọc schema trước |
| exec_023 | executor | empty-result ok | ok + item_count=0 | min price=$1.0 > 0.5 | data_correctness | ✅ trong tầm |
| int_013 | integration | multi-step $ref end-to-end | status ok + presented ids | như exec_021 | presented_ids_exact | ✅ trong tầm |
| grounding_036/037 | grounding | hallucination/injection mở rộng | rate=0.0 | evidence fields | label_agreement | ❌ cần Jev credentials |

Ưu tiên đề xuất nếu phải chọn ít: **exec_019** (hồi quy trực tiếp 18 task-fail
lớn nhất), **planner_033** (hồi quy 6 task-fail, chấm được ngay), **exec_021**
(nhánh $ref chưa có case thành công). Ba case này đều tính tay được và phân biệt
được hành vi cấu hình.

---

## Câu hỏi cần người dùng quyết

1. Chọn subset case nào để triển khai (khuyến nghị exec_019 + planner_033 +
   exec_021)?
2. exec_020 phụ thuộc SearchTool ok-on-empty — có muốn tôi verify hành vi đó
   trước (chỉ đọc code, không chạy) rồi mới chốt?
3. Tiêu chí multi-turn mới (expect_no_result v.v.) là thay đổi code evaluator —
   có nằm trong scope tuần này không, hay chỉ ghi backlog?
4. Grounding: có Jev credential để verify không? Nếu không, có nên thêm case
   "mù" (không chấm) không — theo rule thì không nên.
