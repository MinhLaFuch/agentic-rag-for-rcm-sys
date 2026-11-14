# Investigation Week 47 — campaign_001

Phạm vi: điều tra, không sửa code `package/`. Mọi số liệu đều từ artifact có sẵn
hoặc script chỉ-đọc `scripts/eda_diagnostic/analyze_campaign_001_planner_errors.py`
(chạy: `cd src && PYTHONPATH=. python scripts/eda_diagnostic/analyze_campaign_001_planner_errors.py`).

---

## 2A. Multi-turn không phân biệt được cấu hình

### Bằng chứng

**Luồng chạy:** `run_agent_eval.py` → `run_optional_multi_turn` (`scripts/evaluation/run_agent_eval.py:238-254`)
→ `run_multi_turn_for_eval` (`package/evaluation/multi_turn/_eval_step.py:122-139`)
→ subprocess `python -m package.evaluation.multi_turn._run` (`_eval_step.py:86-96`, không truyền `env`
→ **thừa hưởng `CONFIG_OVERLAY_PATH`** do campaign_runner set ở `campaign_runner.py:165`).

**Tuyên bố tuần 46 "runner luôn dùng planner_memory + reflect_rounds mặc định, không đọc cấu hình
experiment" — ĐÚNG MỘT NỬA, cần chỉnh:**

- `_agent_runner.py:47`: `PlanExecutor(llm=self.llm, tools=agent_tools.for_planner_memory())` —
  **luôn** toolset planner_memory, `reflect_rounds=None` → lấy `get_agent_limits()`.
- `get_agent_limits()` đọc `load_config("agent/agent")` (`package/agents/_limits.py:30-34`) —
  load_config merge overlay (`package/config/_helper.py:41-72`), và subprocess multi-turn **thấy**
  overlay qua env inheritance → **`reflect_rounds` CÓ truyền vào** theo experiment (0 hay 1),
  không phải "mặc định agent.yaml" như ghi chú cũ. Đây là side-effect, không phải tham số tường minh.
- `inference_mode`: overlay `agent/inference` cũng merge được, nhưng multi-turn **không có bước
  compose answer** — `run_turn` chỉ trả `items/exclusions/trace` (`_agent_runner.py:66-75`),
  evaluator không gọi inference. → inference_mode không áp dụng (có thể là by-design: multi-turn
  đo hành vi tool/session, không đo câu trả lời).
- `agents`: mọi experiment (baseline+type1, planner, planner_memory) chạy **cùng một** agent
  planner_memory → agent choice không phân biệt được.
- `agent_config.multi_turn` chấp nhận key `limits` (`campaign_runner.py:218`) nhưng
  `run_multi_turn_for_eval` chỉ đọc `dataset/output_dir/timeout_seconds` (`_eval_step.py:135-138`)
  → **`limits` là key chết**, không tới được runner.
- Dataset: multi-turn luôn dùng `conversations.jsonl` cố định (11 hội thoại), không liên quan
  request set của experiment.

**Kết quả thực tế — 8 experiment có artifact đều giống hệt nhau:**
`multi_turn/*/multi_turn.json`: 11 conversations, 20/20 turns, `turn_success_rate=1.0`,
`conversation_success_rate=1.0`, `turn_completion_ratio=1.0`, `context_retention mean=1.0`
(kể cả exp_1 baseline_type1 lẫn exp_9 planner_memory).

### Vì sao 3 chỉ số chạm trần

- `turn_success` = `turn_output is not None` (`multi_turn_evaluator.py:153`) — chỉ = 0 khi
  `run_turn` raise. `PlanExecutor.run`/`_execute`/`plan` bắt gần hết lỗi (step error → `ok:false`,
  plan parse sai → retry rồi bỏ, `plan_executor.py:125-137,161-167`; `_helper.py` per-step try/except).
  → chỉ còn LLM provider sập mới làm turn fail. **Chỉ số này đo "không crash", không đo chất lượng.**
- `conversation_success` = mọi turn không crash (`:335`) → cùng tính chất.
- `context_retention` (`:357-371`): session.shown_items append-only, FIFO cap `max_shown_items=50`
  (`session.py:68-74`, `configs/agent/memory.yaml:15`); 20 turns × vài item « 50 → không bao giờ evict
  → luôn 1.0 về mặt cấu trúc với dataset này.
- `turn_completion_ratio` = executed/scheduled turns; chỉ <1 khi conversation fail sớm
  (`break` ở `:101-102`). Cả 8 experiment đều = 1.0.
- Chỉ số **có phân biệt** tồn tại trong `multi_turn.json.metrics.*`: `avg_item_match_rate_mean=0.70`,
  `exclusion_compliance_mean=0.95`, `tool_call_match_rate=1.0` — nhưng `extract_multi_turn_metrics`
  (`_eval_step.py:24-31,142-146`) chỉ trích 3 chỉ số bão hòa + totals → campaign_result không thấy
  phần phân biệt.
- Tiêu chí fail **chưa tồn tại**: không `max_steps_per_turn`, không `turn_timeout_seconds`, không
  `expect_no_result`/`expect_clarification` (conv_m5 clarification không được kiểm — expected_items
  rỗng + không exclusion → `exclusion_compliance=1.0` mặc định `:198-199`, item_match=1.0 `:177`).
  Turn trả sai item vẫn `success=1`.
- Hội thoại "không thể fail": cả 11 — expected_items đều recall-style hoặc rỗng; turn chỉ fail khi
  exception. `conv_recovery_after_error` kỳ vọng "xử lý item_x gracefully" nhưng không có tiêu chí
  kiểm (expected_items rỗng → mọi output đều pass).

### Cách truyền cấu hình experiment (thay đổi nhỏ nhất)

1. `campaign_runner.py`: `_MULTI_TURN_PARAM_KEYS` thêm `agent`, `inference_mode` (hoặc tái dùng
   `limits`); trong `_multi_turn_plans`/`_build_config_overlay`, copy `experiment.agent_config`
   vào fragment `multi_turn` (ví dụ `frag["agent"]=...`).
2. `_eval_step.run_multi_turn_for_eval`: forward các key mới thành CLI args.
3. `_run.py`: thêm `--agent`, `--inference-mode` (argparse) → `RealAgentRunner(config)`.
4. `_agent_runner.RealAgentRunner`: chọn `for_planner()` vs `for_planner_memory()` theo agent;
   truyền `reflect_rounds` tường minh (hiện dựa vào overlay side-effect — nên explicit);
   inference_mode chỉ có nghĩa nếu thêm bước compose answer (quyết định có cần không — multi-turn
   hiện không đo answer).
5. `run_agent_eval.run_optional_multi_turn` (`:238-254`): không cần đổi nếu fragment mang đủ key;
   `:564-576` chỉ truyền `cfg` block xuống.

### Rủi ro

- Multi-turn artifact cũ không ghi agent/inference đã dùng → không audit được sau khi đổi;
  nên ghi config đã resolve vào `multi_turn.json` (hiện chỉ có git_sha + dataset).
- Bật `inference_mode=llm` cho multi-turn sẽ nhân chi phí LLM (answer compose mỗi turn).

---

## 2B. Planner: ba nguyên nhân lỗi của planner_memory

Nguồn số liệu: `experiments/logs/multi_domain/campaign_001_parameter_grid_exp_*_trajectories.jsonl`
+ `experiments/agent_eval/campaigns/campaign_001/exp_*/run_1/scored.jsonl`.
Script: `scripts/eda_diagnostic/analyze_campaign_001_planner_errors.py` (read-only).

**Xác nhận "30/132":** exp_9 (planner_memory, template, reflect=0) có **đúng 30 task_success fail**
(trên 132 scored rows): personalized 18, exclusion 6, unanswerable 6. 29 trajectories có ≥1 step
lỗi (1 fail không qua step error). provider_error=0 toàn bộ.

Lưu ý quan trọng: planner **không** có MemoryTool → 40 rows `personalized` có
`task_success=None` (không chấm — `score_trajectory.py:77-79`), KHÔNG phải fail.
Fail thật: exp_5=8 (6 unanswerable+2 exclusion), exp_6=3, exp_9=30, exp_10=2.

### (a) Tham chiếu tới trường null — 20/30 lỗi gốc

- **Bằng chứng:** exp_9: 20 step errors `FilterTool: $1.price_range.max: 'max' not found.
  Step 1 (MemoryTool) returned: user_id, known, n_interactions, ...` — tất cả ở request
  `personalized-sparse-*`. exp_11 (llm, đang dở): 19 case tương tự.
- **Cơ chế:** `memory_tool.py:112` — `price_range = {"min":lo,"max":hi} if lo is not None else None`
  (None khi user không có giá hoặc `known=False`, `:88-93`). `_resolve_path`
  (`agents/planner/_helper.py:12-29`) gặp `None` + path `max` → KeyError → ValueError →
  step fail → mọi ref `$N` phía sau "skipped, step N failed" (cascade).
- **Planner bắt chước ví dụ ở đâu:** `SYSTEM_PROMPT` dạy tường minh `"$1.price_range.max" for price_max`
  (`_prompt.py:24`) và example plan dùng đúng pattern đó (`_prompt.py:35`);
  `memory_tool.py:36` output_schema cũng ghi `"$1.price_range.max" for filters.price_max`.
  `reference_plans.yaml` KHÔNG chứa ví dụ này (chỉ là nhóm tool sequence) — nguồn bắt chước là prompt.
- **Phân loại:** 20 step-error / ~18 task-fail (personalized-sparse; một số request có price_range
  khác None nên không fail — chỉ sparse segment thiếu giá).

**So sánh 3 phương án:**

| PP | Mô tả | Ưu | Nhược/rủi ro |
|---|---|---|---|
| (i) Bỏ arg tùy chọn khi ref→None + log | `_resolve_refs` trả sentinel, FilterTool bỏ `price_max` | Sửa 1 chỗ, cứu ~18 task_success ngay cả reflect=0 | **Ràng buộc mềm vs cứng:** price_range từ memory là mềm (an toàn bỏ); nhưng nếu user TỰ NÓI "dưới $50" thì bỏ = sai lệch im lặng → cần phân biệt nguồn ref (memory-step vs literal) — phức tạp hơn vẻ ngoài |
| (ii) Báo lỗi rõ → reflect sửa | Giữ nguyên; reflect=1 đã chứng minh sửa được | Không cần code mới; exp_10: 30→2 fail | reflect tốn thêm 1 LLM call/request lỗi; r0 vẫn fail |
| (iii) Sửa prompt | Đổi ví dụ: `price_max` chỉ khi `price_range != null`, hoặc dùng `recent_items`/top_categories | Rẻ | Prompt change → **đổi provenance hash** (`planner_prompt_sha256`), mọi trajectory cũ không còn so sánh trực tiếp; LLM vẫn có thể ignore |

Đề xuất thứ tự: (ii) là baseline đã có sẵn; (i) chỉ nên làm nếu chấp nhận logic
"ref→None trên arg optional = bỏ arg" VÀ phân biệt được soft/hard constraint;
(iii) là bổ sung, không thay thế. Lưu ý `_blocks_reflect` (`_helper.py:188-194`) không chặn
loại lỗi này nên reflect hoạt động đúng.

### (b) SearchTool vượt time budget — 3-6 lỗi/lượt

- **Bằng chứng:** exp_9: 3 (`exclusion-sparse-3,8,15`); exp_11: 3 (`-4,8,10`); exp_12:1;
  exp_8:1; exp_5:2; exp_6:1; exp_10:1. Tất cả `latency_seconds ≈ 5.3-5.46` vs budget 5.0s
  (`configs/agent/tools.yaml:8`).
- **Query gây lỗi (args đã resolve):**
  - `exclusion-sparse-3`: `query="toys NOT dolls"`, filters `{domain:Toys_and_Games, exclude_item_ids:[...]}`, `limit=100`
  - `exclusion-sparse-8`: `query="board game"`, domain Toys_and_Games, limit=100
  - `exclusion-sparse-15`: `query="electronics"`, domain Electronics, limit=100
  - exp_11 thêm: `"Electronics NOT Microcassette NOT Recorders"`, `'toys NOT "Yo-yos"'`
- **Cơ chế:** `_tokenize` (`retrieval/_helper.py`) — "not" **không** nằm trong STOPWORDS
  (`_schema.py:1-4`) → OR-join (`search_tool.py:125`) biến "NOT" thành token tìm kiếm;
  planner tưởng "NOT" là phủ định nhưng thực chất match mọi item chứa "not". OR trên token
  phổ biến ("game","electronics","toys") → FTS MATCH ~200-400k docs → bm25 + temp b-tree sort
  (`EXPLAIN QUERY PLAN`: `SCAN items_fts VIRTUAL TABLE` + `USE TEMP B-TREE FOR ORDER BY`).
  `limit=100` do planner tự đặt (default `SEMANTIC_DEFAULT_LIMIT=50`, `tools.yaml:17`;
  trần `MAX_CANDIDATES=1000`) — nhưng limit chỉ cắt output, **không giảm** chi phí scoring.
- **Benchmark chỉ-đọc trên corpus thật** (`resource/corpus/multi_domain/corpus_multi_domain.sqlite`,
  678,281 items, qua chính `ItemCorpus.select` + authorizer + progress handler):
  mọi query trên chạy **0.22-0.62s** — KHÔNG tái hiện được 5.3s. → Nguyên nhân quá ngân sách
  trong campaign run nhiều khả năng là môi trường (load máy/ngày 10-11, cold cache, AV) —
  **CHƯA XÁC MINH**; không có profiling artifact của run đó. Rủi ro cấu trúc vẫn thật:
  đây là dạng query nặng nhất của tool và chỉ cần máy chậm ~8x là chạm budget.
- **So sánh phương án:**
  - Hạ `default_limit`: **không giúp** (chi phí ở MATCH+sort toàn bộ, không ở LIMIT).
  - Siết filter / đổi token-join (AND thay OR, hoặc loại "not"): giảm match set → giúp thật,
    nhưng đổi semantics retrieval — cần eval recall.
  - Tăng `sql_time_budget_seconds`: chỉ che vấn đề — budget tồn tại để chặn query pathological;
    tăng = chấp nhận step 5-10s × nhiều request.
  - Sửa planner behavior (dạy dùng `categories_exclude`/`exclude_item_ids` thay "NOT" trong
    query text): đúng bản chất — "KHÔNG thuộc nhóm X" nên là filter, không phải keyword.

### (c) Câu hỏi không thể trả lời — 6 lỗi khi reflect=0, reflect sửa cả 6

- **Bằng chứng:** cả 6 request `unanswerable-none-*` đều là "Tìm sản phẩm giá dưới 1 đô thuộc
  nhóm NonExistentCategory999" (oracle kind=unanswerable). exp_9 r0: planner sinh plan
  FilterTool(`categories_any:["NonExistentCategory999"], price_max:1`) → `category ... not found
  in the catalog` → RankTool/LookupTool cascade fail → task_success=0.
  exp_10 r1: cùng request → reflect=1 → `ask_user="Danh mục ... không tồn tại. Bạn muốn tìm ...?"`,
  plan=[] → success.
- **Planner sai gì:** không nhận ra category không tồn tại là bất khả thi → cố "tra" thay vì
  ask_user/kết luận rỗng. FilterTool báo lỗi đúng; planner thiếu bước kiểm chứng.
- **Đề xuất:** (i) prompt rule "nếu category/item user nêu không có trong catalog → ask_user
  hoặc trả empty, không gọi FilterTool"; (ii tất định) pre-check category tồn tại trước khi
  execute (catalog category list đã load sẵn — FilterTool đã validate, chỉ là quá muộn);
  (iii) để reflect xử lý (đã chứng minh 6/6) nhưng tốn 1 vòng LLM.
- **Giới hạn:** n=6, cùng một template request (chỉ khác user_id) → kết luận yếu, không
generalize được sang dạng unanswerable khác.

### Bảng tổng hợp

| Nguyên nhân gốc | Task-fail (exp_9 r0) | Bước sửa | Độ khó | Δ task_success kỳ vọng (r0 planner_memory) |
|---|---|---|---|---|
| ref→null `price_range.max` | 18 (personalized) | (i) resolver+soft/hard-aware drop, hoặc (iii) prompt | TB | +18 nếu (i); +0 nếu chỉ (iii) |
| category không tồn tại (unanswerable) | 6 | prompt rule hoặc pre-check tất định | Thấp | +6 |
| SearchTool time budget | ~3 (exclusion) | planner dùng filter thay "NOT"-query; hoặc chịu rủi ro môi trường | TB | +2-3, không ổn định |
| cascade_skip / empty_candidates | (hệ quả, không tính riêng) | — | — | — |
| **Tổng exp_9** | **30/132** | | | **→ ~4-6 còn lại** nếu vá (a)+(c) |

**Hệ quả bảng reflect 0 vs 1:** exp_9=30 fail vs exp_10=2 fail — reflect đang gánh gần hết
sửa lỗi. Sau khi vá (a)+(c) ở tầng planner/prompt, r0 sẽ xuống ~6-9 fail → **khoảng cách
reflect thu hẹp mạnh**; giá trị đo được của reflect chủ yếu còn ở exclusion/search-timeout
và các lỗi chưa lường. Kế hoạch: giữ cả kết quả trước-sửa (exp_9/10 hiện có) và sau-sửa
(phải chạy campaign mới với trajectory_file mới hoặc chấp nhận resume invalid do prompt hash
đổi — `_source_fingerprint`/prompt sha256 nằm trong provenance; trajectory cũ không resume
được nếu code prompt đổi? — CHƯA XÁC MINH: prompt nằm trong `build_run_provenance` hash,
resume_identity chứa `protocol`+`source_fingerprint`(chỉ root pyproject.toml) — prompt đổi
KHÔNG đổi resume_identity → trajectory cũ vẫn resume được nhưng provenance hash mới sẽ lệch
giữa record cũ/mới trong cùng file → cần kiểm chứng thêm trước khi chạy).

---

## 2C. Ablation — cái gì ĐÃ có

### Contrasts định nghĩa trong `configs/agent/ablation.yaml`

6 contrasts: `planner_reflect0_vs_reflect1`, `planner_memory_reflect0_vs_reflect1`,
`memory_vs_no_memory` (kinds=[similar, constrained, cold_text]),
`planner_memory_template_vs_llm`, `planner_template_vs_llm`, `type1_template_vs_llm`.
Groups trỏ `exp_012/exp_013/exp_011` — **placeholder** ("lần 1 (id thật của bạn)").

**Trạng thái chạy được: KHÔNG.** `_loader.load_group_data` resolve
`experiments_dir/agent_eval/<exp_name>` (`_loader.py:39-58`); `experiments/agent_eval/`
chỉ có `campaigns/` + `component_benchmarks/` — không có exp_011/012/013 → loader raise
ConfigError. Kể cả trỏ vào campaign dirs, `kinds=[similar, constrained, cold_text]`
**không khớp kinds thật** của dataset (`similar, personalized, exclusion, unanswerable,
ambiguous`) → filter chỉ còn 'similar', 2/3 kinds là no-op.

### Đối chiếu ablation một phần có sẵn trong grid campaign_001

| Ablation | Cặp experiment | Cân bằng? | Trạng thái |
|---|---|---|---|
| Memory (planner vs planner_memory) | exp_5↔9 (template r0), exp_6↔10 (r1), exp_7↔11, exp_8↔12 (llm) | Cùng 132 requests/seed; NHƯNG `personalized` của planner có `task_success=None` (`score_trajectory.py:77-79`) → phải loại kind đó khỏi so sánh (còn 92 rows: similar 40 + exclusion 40 + unanswerable 6 + ambiguous 6) | số liệu có cho template; llm đang dở |
| Reflect 0 vs 1 | exp_5↔6, exp_9↔10 (template); exp_7↔8, exp_11↔12 (llm) | Cân bằng hoàn toàn (cùng agent, inference_mode, requests) | template đủ; llm dở |
| inference template vs llm | exp_5↔7↔9↔11 v.v. | Cùng requests; inference_mode chỉ đổi answer composer, không đổi plan | llm dở; so sánh chỉ có ý nghĩa trên answer metrics |

### Campaign comparisons hiện có

`comparison_pairs: []` → auto-gen **11 cặp, tất cả vs exp_1** (baseline+type1, template, r0)
(`campaign_runner.py:49-54`). Không có cặp ablation sạch nào (exp_1_vs_exp_9 confound
cả agent set lẫn memory). Mỗi comparison chỉ có delta điểm — **không có CI**:
`_compare_experiments` chỉ tính `delta_ci`/`metric_stats` khi `len(values)>=2` mỗi phía
(`campaign_runner.py:607-627`); repetition_count=1 → `campaign_result.json` không chứa
`delta_ci`/`p_value` nào (đã kiểm: comparison entries chỉ có `deltas` + `statistics` config).
Bootstrap code (`statistics/bootstrap_*`) **đã unit-test** (`tests/evaluation/stats/test_bootstrap.py`)
nhưng chưa từng chạy thật trên campaign_001. Muốn CI phải `repetition_count>=2` hoặc
paired per-request analysis (ablation/_statistics.py có McNemar/paired diff — chưa dùng).

### E0–E9 (từ `experiment_plan.md`, commit fb306d2 — file đã bị xóa khỏi working tree)

| Ô | Trạng thái trong repo |
|---|---|
| E0 Random, E1 Popularity | Không thấy runner/experiment tương ứng trong agent_eval; CHƯA XÁC MINH có ở harness recommender khác |
| E2 Collaborative (ItemKNN) | Gần nhất: `baseline` agent trong campaign (ItemKNN/HybridScorer) — nhưng đó là agent-row trong agent eval, không phải E2 độc lập |
| E3 Sequential baseline | Không có module sequential nào trong repo |
| E4 Hybrid retrieval (collab+embedding) | `vector_store`/`query_encoder` tồn tại trong `SearchTool`/`build_tools` nhưng `run_agent_eval.py:427` không truyền → chưa chạy |
| E5-E9 | Không tương ứng; campaign chỉ phủ agent-layer (planner/planner_memory × inference × reflect) |

**Ablation rows của plan (−Memory, −Retrieval, −Reranking, −Planning, −Profile, −Explanation,
−Multi-agent):** chỉ −Memory có xấp xỉ (planner vs planner_memory, cần loại kind personalized);
−Retrieval/−Reranking/−Planning/−Profile/−Explanation/−Multi-agent **không có config surface**
trong repo hiện tại → báo cáo cuối không được claim các ablation này.

---

## Câu hỏi cần người dùng quyết

1. **2A:** Có muốn multi-turn phân biệt agent/inference_mode không, và nếu có thì inference_mode=llm
   có cần compose answer trong multi-turn (tốn thêm LLM calls)? Hay chấp nhận multi-turn chỉ đo
   planner_memory + reflect_rounds và sửa lại diễn giải báo cáo?
2. **2B(a):** Chọn phương án ref-null: (i) bỏ arg optional khi ref→None — có chấp nhận rủi ro
   "bỏ im lặng" cho ràng buộc mềm, và có muốn phân biệt soft(memory)/hard(user nói) không?
   Hay chỉ (iii) sửa prompt + giữ reflect sửa?
3. **2B(b):** SearchTool timeout: sửa prompt/planner (dạy dùng categories_exclude thay "NOT" query),
   thêm "not" vào STOPWORDS, hay điều tra thêm môi trường (vì benchmark giờ chỉ 0.3-0.6s)?
4. **2C:** Có chạy lại campaign với `repetition_count>=2` để có bootstrap CI không (tốn gấp đôi
   chi phí LLM), hay dùng paired per-request analysis từ scored.jsonl có sẵn (không cần chạy lại)?
   Và có muốn sửa `ablation.yaml` kinds + groups trỏ vào campaign dirs để contrast chạy được không?
5. Experiment_plan.md (E0-E9) đã bị xóa khỏi working tree — lấy từ git history fb306d2 được,
   nhưng E0-E9 phần lớn cần module chưa tồn tại (embedding retrieval, sequential) → xác nhận
   phạm vi báo cáo cuối chỉ claim phần agent-layer?
