# Campaign `campaign_001_parameter_grid` — Kết quả 12 experiments

- Git SHA: `77bec0156851cc422764883b0664942acc09f3b9`
- Timestamp: 2026-11-10T22:57:50.100007+00:00
- Dataset: validation split, domains Video_Games + Toys_and_Games + Electronics (tag `multi_domain`)
- Grid: agents × inference_mode(template/llm) × reflect_rounds(0/1) × multi_turn(true) = 12 experiments

## Tổng quan

| Exp | Agents | Infer | Reflect | Traj records | Expected | Run status | Duration | Multi-turn |
|---|---|---|---|---|---|---|---|---|
| exp_1 | baseline_type1 | template | 0 | 160 | 160 | success | 6m | ok tsr=1.00 csr=1.00 |
| exp_2 | baseline_type1 | template | 1 | 160 | 160 | success | 6m | ok tsr=1.00 csr=1.00 |
| exp_3 | baseline_type1 | llm | 0 | 160 | 160 | success | 21m | ok tsr=1.00 csr=1.00 |
| exp_4 | baseline_type1 | llm | 1 | 160 | 160 | success | 23m | ok tsr=1.00 csr=1.00 |
| exp_5 | planner | template | 0 | 132 | 132 | success | 34m | ok tsr=1.00 csr=1.00 |
| exp_6 | planner | template | 1 | 132 | 132 | success | 39m | ok tsr=1.00 csr=1.00 |
| exp_7 | planner | llm | 0 | 118 | 132 | TIMEOUT | 60m | not_run |
| exp_8 | planner | llm | 1 | 107 | 132 | TIMEOUT | 60m | not_run |
| exp_9 | planner_memory | template | 0 | 132 | 132 | success | 42m | ok tsr=1.00 csr=1.00 |
| exp_10 | planner_memory | template | 1 | 132 | 132 | success | 45m | ok tsr=1.00 csr=1.00 |
| exp_11 | planner_memory | llm | 0 | 114 | 132 | TIMEOUT | 60m | not_run |
| exp_12 | planner_memory | llm | 1 | 100 | 132 | TIMEOUT | 60m | not_run |

## Chi tiết từng experiment

### exp_1 — baseline_type1 / template / reflect=0

- **Run**: success (6 min)
- **Trajectories** (160 records, last=`exclusion-warm-19`): baseline: n=120, err=0, provider_err=0, wall=0.0m, steps=0, answers={}; type1: n=40, err=0, provider_err=0, wall=0.0m, steps=120, answers={'ok': 40}
- **task_success**: baseline/exclusion: 1.00, baseline/personalized: 1.00, baseline/similar: 1.00, type1/similar: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.70, exclusion_compliance=0.95, context_retention=1.00

### exp_2 — baseline_type1 / template / reflect=1

- **Run**: success (6 min)
- **Trajectories** (160 records, last=`exclusion-warm-19`): baseline: n=120, err=0, provider_err=0, wall=0.0m, steps=0, answers={}; type1: n=40, err=0, provider_err=0, wall=0.0m, steps=120, answers={'ok': 40}
- **task_success**: baseline/exclusion: 1.00, baseline/personalized: 1.00, baseline/similar: 1.00, type1/similar: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.82, exclusion_compliance=1.00, context_retention=1.00

### exp_3 — baseline_type1 / llm / reflect=0

- **Run**: success (21 min)
- **Trajectories** (160 records, last=`exclusion-warm-19`): baseline: n=120, err=0, provider_err=0, wall=0.0m, steps=0, answers={}; type1: n=40, err=0, provider_err=0, wall=0.0m, steps=120, answers={'ok': 40}
- **task_success**: baseline/exclusion: 1.00, baseline/personalized: 1.00, baseline/similar: 1.00, type1/similar: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.82, exclusion_compliance=0.91, context_retention=1.00

### exp_4 — baseline_type1 / llm / reflect=1

- **Run**: success (23 min)
- **Trajectories** (160 records, last=`exclusion-warm-19`): baseline: n=120, err=0, provider_err=0, wall=0.0m, steps=0, answers={}; type1: n=40, err=0, provider_err=0, wall=0.0m, steps=120, answers={'ok': 40}
- **task_success**: baseline/exclusion: 1.00, baseline/personalized: 1.00, baseline/similar: 1.00, type1/similar: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.77, exclusion_compliance=0.86, context_retention=1.00

### exp_5 — planner / template / reflect=0

- **Run**: success (34 min)
- **Trajectories** (132 records, last=`unanswerable-none-5`): planner: n=132, err=0, provider_err=0, wall=29.1m, steps=376, answers={'ok': 108, 'tool_error': 18, 'ask_user': 6}
- **task_success**: planner/ambiguous: 1.00, planner/exclusion: 0.95, planner/similar: 1.00, planner/unanswerable: 0.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.73, exclusion_compliance=0.95, context_retention=1.00

### exp_6 — planner / template / reflect=1

- **Run**: success (39 min)
- **Trajectories** (132 records, last=`unanswerable-none-5`): planner: n=132, err=0, provider_err=0, wall=32.9m, steps=354, answers={'ok': 113, 'tool_error': 5, 'ask_user': 14}
- **task_success**: planner/ambiguous: 1.00, planner/exclusion: 0.93, planner/similar: 1.00, planner/unanswerable: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.86, exclusion_compliance=0.95, context_retention=1.00

### exp_7 — planner / llm / reflect=0

- **Run**: FAILED — Experiment timed out after 3600 seconds (60 min)
- **Trajectories** (118 records, last=`exclusion-warm-11`): planner: n=118, err=0, provider_err=0, wall=23.5m, steps=333, answers={'ok': 92, 'tool_error': 19, 'ask_user': 7}

### exp_8 — planner / llm / reflect=1

- **Run**: FAILED — Experiment timed out after 3600 seconds (60 min)
- **Trajectories** (107 records, last=`exclusion-warm-0`): planner: n=107, err=0, provider_err=0, wall=21.7m, steps=303, answers={'ok': 97, 'tool_error': 4, 'ask_user': 6}

### exp_9 — planner_memory / template / reflect=0

- **Run**: success (42 min)
- **Trajectories** (132 records, last=`unanswerable-none-5`): planner_memory: n=132, err=0, provider_err=0, wall=37.5m, steps=447, answers={'ok': 96, 'tool_error': 29, 'ask_user': 7}
- **task_success**: planner_memory/ambiguous: 1.00, planner_memory/exclusion: 0.85, planner_memory/personalized: 0.55, planner_memory/similar: 1.00, planner_memory/unanswerable: 0.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.89, exclusion_compliance=0.95, context_retention=1.00

### exp_10 — planner_memory / template / reflect=1

- **Run**: success (45 min)
- **Trajectories** (132 records, last=`unanswerable-none-5`): planner_memory: n=132, err=0, provider_err=0, wall=39.4m, steps=437, answers={'ok': 118, 'ask_user': 12, 'tool_error': 2}
- **task_success**: planner_memory/ambiguous: 1.00, planner_memory/exclusion: 0.95, planner_memory/personalized: 1.00, planner_memory/similar: 1.00, planner_memory/unanswerable: 1.00
- **multi_turn**: 11 convs, turn_success=1.00, conv_success=1.00, avg_turns=1.82, item_match=0.86, exclusion_compliance=0.95, context_retention=1.00

### exp_11 — planner_memory / llm / reflect=0

- **Run**: FAILED — Experiment timed out after 3600 seconds (60 min)
- **Trajectories** (114 records, last=`exclusion-warm-7`): planner_memory: n=114, err=0, provider_err=0, wall=27.7m, steps=390, answers={'ok': 86, 'tool_error': 22, 'ask_user': 6}

### exp_12 — planner_memory / llm / reflect=1

- **Run**: FAILED — Experiment timed out after 3600 seconds (60 min)
- **Trajectories** (100 records, last=`exclusion-sparse-13`): planner_memory: n=100, err=0, provider_err=0, wall=25.1m, steps=334, answers={'ok': 93, 'ask_user': 6, 'tool_error': 1}

## Phân tích sâu từ `scored.jsonl` (per-request)

`campaign_result.json` chỉ ghi status/duration — phân tích dưới đây đọc trực tiếp `run_1/scored.jsonl` của từng experiment (8 run hoàn chỉnh; 4 run timeout không có file này vì chết trước bước scoring).

| Exp | n scored | task_success fails | answer tool_error | reflections invoked/succeeded |
|---|---|---|---|---|
| exp_1-4 (baseline+type1) | 160 | **0** | 0 | — (không planner) |
| exp_5 planner/template/r0 | 132 | 8 | 18 | — |
| exp_6 planner/template/r1 | 132 | 3 | 5 | 26/16 |
| exp_9 planner_memory/template/r0 | 132 | **30** | 29 | — |
| exp_10 planner_memory/template/r1 | 132 | 2 | 2 | 34/27 |

### task_success theo kind (fails = tổng - pass)

| Exp | similar | personalized | exclusion | ambiguous | unanswerable |
|---|---|---|---|---|---|
| exp_1-4 | 80/80 | 40/40 | 40/40 | — | — |
| exp_5 | 40/40 | **0/40** | 38/40 | 6/6 | **0/6** |
| exp_6 | 40/40 | **0/40** | 37/40 | 6/6 | 6/6 |
| exp_9 | 40/40 | 22/40 | 34/40 | 6/6 | **0/6** |
| exp_10 | 40/40 | 40/40 | 38/40 | 6/6 | 6/6 |

### Phát hiện từ scored.jsonl

- **exp_9 là run tệ nhất** (30 fails): `planner_memory` không reflect sinh ra lỗi `bad_reference` hàng loạt — RankTool/LookupTool/FilterTool đều ~29 bad_reference (plan tham chiếu `$step` sai). Reflect=1 (exp_10) giảm còn 2 fails → **reflect_rounds=1 cứu gần như toàn bộ lỗi planner_memory**.
- **unanswerable=0/6 ở exp_5 và exp_9**: agent vẫn recommend cho câu hỏi không trả lời được — vi phạm kỳ vọng "không được bịa". exp_6/exp_10 (reflect=1) sửa được → 6/6.
- **personalized=0/40 ở exp_5/exp_6** (planner không memory): không đọc được history nên không personalize được — consistent với việc kind này vốn chỉ nên score cho planner_memory (exp_9: 22/40, exp_10: 40/40).
- **exp_10 gần như hoàn hảo**: 130/132 task_success, chỉ 2 fails (exclusion), 34 reflections invoked / 27 succeeded.
- **Baseline/type1 (exp_1-4) hoàn hảo tuyệt đối**: 0 fails trên 160 records — nhưng lưu ý baseline/type1 không dùng LLM plan nên không có reflections; inference_mode (template/llm) không ảnh hưởng task_success, chỉ ảnh hưởng chất lượng câu trả lời (answer composer).
- **4 run timeout (exp_7/8/11/12) không có scored.jsonl** — chết trước scoring nên không biết task_success; trajectories partial vẫn dùng được để resume.

### Root-cause từ `trajectories.jsonl` (đọc plan + step errors của các request fail)

Đọc trực tiếp plan JSON và step errors của các record `task_success=false`. 30 fails của exp_9 quy về **3 root cause**:

**1. `$ref` tới field không tồn tại — 20/30 fails (personalized-sparse).**
Plan mẫu (exp_9, `personalized-sparse-2`):
```json
[{"tool":"MemoryTool","args":{"user_id":"..."}},
 {"tool":"FilterTool","args":{"filters":{"categories_any":"$1.love_categories","price_max":"$1.price_range.max"}}},
 {"tool":"RankTool","args":{"candidates":"$2.candidates",...}},
 {"tool":"LookupTool","args":{"item_ids":"$3.ranked.*.item_id"}}]
```
MemoryTool trả `price_range: null` cho user sparse (không có dữ liệu giá — `memory_tool.py:112` chỉ set `{min,max}` khi có interaction) → `$1.price_range.max` → `'<field>' not found` → FilterTool fail → RankTool/LookupTool cascade `skipped` → `answer_status=tool_error`. Planner copy nguyên example `"$1.price_range.max"` từ docstring của MemoryTool mà không check null. **exp_5/exp_6 cũng dính pattern này** nhưng ít hơn vì không có MemoryTool step.

**2. SearchTool vượt time budget — ~3-6 fails/run (exclusion-sparse).**
Plan dùng `SearchTool` với `query: "toys NOT dolls"` + `domain` filter + `limit: 100` trên catalog 678k items → `query exceeded the time budget` → cascade → tool_error. Đây là **fail hiệu năng**, không phải reasoning — BM25 query quá rộng chậm hơn budget. Reflect=1 retry với query hẹp hơn nên qua được.

**3. Unanswerable không short-circuit — 6 fails/run không reflect.**
Với request cố tình unanswerable, planner vẫn build plan `FilterTool{categories_any:["NonExistentCategory999"], price_max:1}` → tool báo `category not found` → tool_error apology. Đáng lẽ nên kết luận "không trả lời được" ngay từ plan. Reflect=1 sửa được (exp_6, exp_10 → 6/6) nhờ reflection nhận ra và đổi plan.

**Tại sao reflect=1 thắng áp đảo:** cả 3 root cause đều là *plan-level* mistakes (sai $ref, query quá rộng, không nhận diện unanswerable) — reflection round phát hiện step error/bad plan rồi replan. Verify trong trajectories exp_10: `reflections` = số lần replan, trigger đúng khi `first_attempt_ok=False` — 34 requests cần reflect (gồm cả 6/6 unanswerable, phần lớn personalized-sparse và exclusion-sparse), sau reflect chỉ còn 2 fails → 130/132 task_success. Tức **first-attempt plan của planner_memory có ~26% request cần cứu**, reflect bắt được gần hết.

**Đáng chú ý:** `answer_status=tool_error` luôn trả lời fallback "Xin lỗi, hệ thống chưa xử lý được..." — trung thực (không bịa) nhưng tính `task_success=false`. Tức fail chủ yếu là **robustness của plan**, không phải hallucination.

## Phát hiện

- **8/12 runs success**, 4 runs timeout đúng 3600s: exp_7, exp_8, exp_11, exp_12 — tất cả là tổ hợp `inference_mode=llm` + planner/planner_memory (LLM calls nhiều nhất).
- Trajectories của 4 run timeout **còn nguyên** trong `experiments/logs/multi_domain/` (exp_7: 118/132, exp_8: 107/132, exp_11: 114/132, exp_12: 100/132) — resume được bằng `--resume` khi fingerprint khớp.
- **0 trajectory errors, 0 provider_errors** trên toàn bộ records — không có LLM/provider failure; timeout là do tổng thời gian chạy vượt giới hạn, không phải crash.
- Multi-turn eval: 8 artifacts `success` (turn_success_rate=1.0, conversation_success_rate=1.0 trên cả 8), 4 `not_run` tương ứng các run timeout.
- exp_11 (partial, 114 records) đã có **22 answer_status=tool_error** — cao hơn hẳn các run khác; đáng xem lại khi resume xong.
- Baseline/type1 (exp_1-4): baseline task_success=1.0 mọi kind; type1 chỉ chạy `similar` (40 records) — by design.