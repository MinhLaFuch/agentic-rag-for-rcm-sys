# Eval + Demo check — tuần 47

Phạm vi: (1) kiểm kê eval chưa nối vào campaign, (2) kiểm tra demo UI Gradio.
Mọi nhận định kèm file#dòng hoặc lệnh + output thật. "CHƯA XÁC MINH" = thiếu bằng chứng.

---

## PHASE A — Eval chưa nối vào campaign

### A1. Bảng eval surface

| Eval | Entry point | Trong campaign? | Cần LLM/Jev | Artifact | Thư mục ghi |
|---|---|---|---|---|---|
| Agent eval 5 layer + multi_turn | `scripts/evaluation/run_agent_eval.py` | Có — campaign gọi subprocess duy nhất `campaign_runner.py:232-236` | LLM cho planner / inference_mode=llm; multi_turn cần LLM | `metrics.json`, `scored.jsonl`, `trajectories.jsonl`, `multi_turn.json` | `experiments/agent_eval/campaigns/<id>/<exp>/run_N/` + `campaigns/<id>/multi_turn/` |
| Campaign orchestration | `scripts/evaluation/run_campaign.py` → `CampaignRunner` | Chính nó | theo experiment | `campaign_result.json` (+ `campaign_result_backup_*.json` khi `--only`) | `campaigns/campaign_001/` |
| Component benchmarks ×5 | `scripts/evaluation/run_component_benchmarks.py` → `component/_run_all.py` → subprocess `component.run` (`_run_all.py:90-96`) | **Không** | memory/executor/integration: không; planner: LLM; grounding: Jev | `<comp>_benchmark_<ts>.json` + `unified_report_<ts>.{json,md}` | `experiments/agent_eval/component_benchmarks/` |
| Multi-turn (bản trong unified report) | `_run_all.py:149-186` → `python -m package.evaluation.multi_turn._run` | **Không** (artifact riêng) | LLM | `multi_turn_conversations_<ts>.json` | outputs.multi_turn (data_paths) |
| Ablation statistics | `scripts/experiments/compare_experiments.py` (config `configs/agent/ablation.yaml`), `pairwise_ablation.py` | **Không** — đọc `scored.jsonl` sẵn có (`ablation/_loader.py:15-18`) | không | md/csv/json | `experiments/agent_eval/ablation/` |
| Jev / product-reply judge | `evaluate_with_jev.py`, `jev_smoke_test.py`, `jev_negative_control.py`, `evaluate_product_reply*.py` | Không | **Jev** | tuỳ script | — |
| Recommender/retrieval offline | `ranking_eval.py`, `candidate_recall.py`, `tune_item_knn_hybrid.py`, `retrieval_loss_diagnostic.py`, `sparse_*.py`, `semantic_candidate_*.py`, `policy_chain_eval.py`… | Không | tuỳ | `experiments/agent_eval/<tên>/` | effort khác (scope: `docs/ablation_scope.md`) |
| Diagnostics / reporting | `package/evaluation/diagnostics/`, `reporting/`, `generate_example_report.py` | Không | không | md | — |

Dataset counts (`wc -l`, khớp inventory): executor 22, grounding 35, integration 13,
memory 29, planner 29, planner_backlog 6, conversations 13.

### A2. Hai hệ metric không tham chiếu nhau

- `campaign_result.json` keys (artifact thật): `campaign_id, campaign_hash, runs,
  comparisons, summary, timestamp, git_sha, multi_turn, subset`. Không có component
  benchmark nào.
- `unified_report_*.json` chỉ có `components` + `summary`. Không đọc campaign_result.
- Grep `unified_report|campaign_result` trong `package/`+`scripts/`: chỉ self-reference.
- Ngoại lệ: cả hai hệ đều chạy multi-turn nhưng ghi **hai file khác nhau** (A3.1).

### A3. Điểm nối dở (mới so với inventory)

1. **Multi-turn chạy 2 lần, 2 artifact.** `_run_all._run_multi_turn`
   (`_run_all.py:149-186`) gọi `_run` không `--output`, không `--limits-json` → file
   timestamped ở outputs.multi_turn, `resolved_config.limits={}`. Campaign đi qua
   `_eval_step.py:87-95` có `--output` + `--limits-json` (từ
   `agent_eval.multi_turn.limits`, hiện `{}`, "recorded, not enforced" —
   `_agent_runner.py:66`). Cùng dataset `conversations.jsonl`
   (`_run_all.py:165` = `agent_eval.yaml:42`), cùng runner stack. `_run_all` không có
   resume/idempotency (`_eval_step.py:63-75` mới có) → trả LLM cost mỗi lần chạy lại.
2. **Grounding thiếu Jev: inventory ĐÃ CŨ.** `_run_all.py:43-51` check
   `_jev_configured()` trước → `skipped_no_credentials`, không chạy subprocess.
   Chạy trực tiếp `run_benchmark_cli` thì `GroundingBenchmark.run_component` vẫn raise
   `ValueError` từng case (`grounding_benchmark.py:45-49`) → mọi case success=False.
   Skipped **không** bị tính pass: `aggregate_results` đếm `skipped_components` riêng
   (`_run_all.py:220-228`), `quality_gate="not_evaluated"`; không thresholds →
   `evaluate_thresholds` trả `None` (`_evaluator.py:33-34`), `passed=None` khi metric
   missing (`_evaluator.py:46-51`), `_run_all.py:322-329` map None → `not_evaluated`.
   **`not_evaluated` không bao giờ thành PASS — xác nhận.**
3. **Quality gate:** chỉ `memory` có thresholds (`component_benchmarks.yaml:35-41`:
   `all_fields_match_mean≥0.95`, `success_rate≥1.0`, `future_leakage_max≤0.0`).
   4 component còn lại + multi_turn = `not_evaluated` (khớp artifact unified_report
   thật 20261110: memory=pass, còn lại not_evaluated).
4. **Provenance:**
   - Campaign: `campaign_result.git_sha` (`run_campaign.py:31-42,124`); per-run
     `config.yaml` chứa `provenance` (git_commit+dirty, prompt/tool-schema sha256,
     limits, config_overlay — `build_run_provenance.py:117-127`).
   - Component: `run_benchmark_cli.py:240-245` ghi `metadata.git_sha` +
     `metadata.provenance` (dataset_sha256, config hash, llm/judge hash). **NHƯNG
     top-level `git_sha` rỗng**: `run_benchmark` gọi không truyền `git_sha`
     (`run_benchmark_cli.py:237`) → `_schema.py:130` default `""`. unified_report đọc
     `result.get("git_sha")` (`_run_all.py:344`) → rỗng cho cả 5 component (xác nhận
     trên artifact; chỉ multi_turn có sha vì `_run.py` ghi top-level). Provenance
     LLM/judge nằm trong `metadata.provenance` nhưng unified_report không surface.
   - Ablation: kế thừa provenance từ `scored.jsonl`/`metrics.json` của campaign run;
     `ablation.yaml` seed=42, bootstrap=10000.

### A3b. Bản đồ "con số → lệnh tái hiện"

| Con số | Lệnh |
|---|---|
| Component benchmark | `PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py` → `unified_report_<ts>.{json,md}`; lẻ: `python -m package.evaluation.component.run --component X --dataset <path>` |
| Campaign | `PYTHONPATH=. python scripts/evaluation/run_campaign.py`; subset `--only 7,8,11,12` (dry-run đã verify: in đúng 12 experiments) |
| Multi-turn campaign | tự chạy khi experiment opt-in (`campaign.yaml:25-26,62`, policy `all`); standalone `python -m package.evaluation.multi_turn._run --dataset package/evaluation/multi_turn/conversations.jsonl --output <path>` |
| Ablation | `PYTHONPATH=. python scripts/experiments/compare_experiments.py`; pairwise `python scripts/experiments/pairwise_ablation.py --a <scored.jsonl> --a-agent X --b <scored.jsonl> --b-agent Y --out <md>` |
| Recommender/retrieval offline | mỗi script một lệnh riêng — **không có lệnh tổng hợp** |

Không có báo cáo tổng duy nhất: campaign_result.json / unified_report / ablation md /
reporting (chỉ `generate_example_report.py` dùng — demo).

### A4. Phương án nối — đã chốt (a)+(c)

- (a) Script bọc ngoài `run_all_evals`: component → campaign → ablation → jev_on_trajectories; in bảng chỉ mục, skipped_no_credentials rõ. Công sức thấp, rủi ro thấp, không đụng resume_identity/metrics.json.
- (b) Nối vào campaign: **loại** — `_build_config_overlay` chỉ map
  `_AGENT_CONFIG_KEYS`/`_EVALUATION_CONFIG_KEYS` (`campaign_runner.py:298-299`); đổi
  `resume_identity` (`run_agent_eval.py:475-484`) → mất hiệu lực --resume toàn bộ
  trajectory đang chạy; `metrics.json` đổi shape → `_load_experiment_metrics`
  (`campaign_runner.py:470-509`) và ablation loader vỡ.
- (c) Bảng chỉ mục eval→số→lệnh: rủi ro 0, không tự động.

---

## PHASE B — Demo UI (Gradio)

### B1. Luồng một request + session_key

`run_demo.py` (chỉ cờ `--domain/--host/--port` — xem B2):

- `main()` L299-352: parse args → đọc `demo.yaml` (eval_on, use_prebuilt_corpus,
  allow_missing_corpus_sources) + `inference.yaml` mode → `LiveBackend(...)` →
  `backend.initialize()` (L322, luôn `initialize_planner=True`) → `get_profiles()` →
  `build_ui()` → `demo.launch(127.0.0.1:7860, share=False)`.
- UI (`build_ui` L55-296): Profile dropdown, request textbox, toggles
  (memory/multiturn/reflect/mode/inference), Submit → `on_submit` (L178-257) →
  `backend.respond(DemoRequest(...))` (L215) → format status/items/trace/memory →
  cập nhật `turn_history_state`.
- `DemoRequest.session_key` = `session_key if multiturn else None` (L212) — tắt
  Multi-turn → single-turn.
- `LiveBackend.respond` (`live_backend.py:246-292`): `self._lock` serialize toàn bộ
  (L248) → validate mode → lazy `initialize` nếu chưa → `_respond_planner` /
  `_respond_type1`.
- `_respond_planner` (L294-390): `_ensure_planner()` → chọn executor theo
  `use_memory` → inject identity (`IDENTITY_INJECTION_VI`, L311-314) → gán
  `executor.reflect_rounds` + `executor.session = self._session_for(request)`
  (L317-324) → `executor.run(effective_text)` trong try/finally reset
  reflect_rounds + `executor.session = None` (L338-340) → snapshot memory →
  `outcome_from_plan_results` → `compose_answer` (inference) →
  `adapt_from_inference` → `DemoResult` (+ `session_turns = len(session.turns)`).
- `_session_for` (L392-409): `session_key` → `Session(**get_session_limits())` trong
  `self._sessions` dict; LRU evict khi `>= max_sessions` (demo.yaml:23 = 100);
  falsy key → None (single-turn).
- `session_key` sinh/reset ở UI: `gr.State(value=uuid.uuid4().hex[:12])`
  (run_demo.py:159); `on_clear_history` trả `[], uuid.uuid4().hex[:12]` mới
  (L174-176) — gắn cho nút Clear history (L271-275), New conversation
  (L277-281), **và** `profile_dropdown.change` (L265-269: đổi profile = hội thoại
  mới). `on_submit` truyền key vào `session_key_state` qua inputs (L285).
- Type1 (`_respond_type1` L458-562): không session; intent path gated bởi
  `demo.intent_path_enabled` (demo.yaml:33, mặc định false); inference llm →
  `compose_answer(outcome, self._llm, mode=...)`.

### B2. `--mock` đã bị xóa — xác nhận

- `run_demo.py --help` output thật: chỉ `--domain --host --port` — **không có --mock**.
- `mock_backend.py` không còn trong package/demo; bản offline sống ở
  `tests/demo/fakes/offline_backend.py` (`OfflineDemoBackend`).
- Chỗ docs/config còn nhắc (code đã bỏ flag):
  - `docs/report_update_log.md:197` — `run_agent_eval.py ... --mock false`
    (sai 2 lần: run_agent_eval không có `--agents`/`--mock`; flag cấu hình qua YAML).
  - `docs/report_update_log.md:58,102,109` — "multi-turn mock-only" (đã lỗi thời:
    `RealAgentRunner` chạy LLM thật, `_agent_runner.py:28-56`).
  - `configs/agent/demo.yaml:25` — comment "run_demo.py không --mock" (mô tả, không
    phải hướng dẫn sai, nhưng tham chiếu flag đã xóa).
  - `docs/repo_reading_update_log.md:115` — chỉ liệt kê file, không nhắc --mock.
- Không có README ở root repo.

### B3. Khởi động UI không credential — KHÔNG được, chặn thật

Lệnh đã chạy (output thật, rút gọn):

```
set PYTHONPATH=. && python scripts/demo/run_demo.py --domain Video_Games --domain Toys_and_Games --domain Electronics
```

```
Mode: LIVE (LiveBackend) / Dataset tag: multi_domain / Eval-on: validation
Đang tải dữ liệu... Đang nạp corpus...
Corpus: loaded ... corpus_multi_domain.sqlite (840.8 MB, 5.03s)
Đang nạp ItemKNN... ItemKNN: loaded ... item_knn_multi_domain_validation.npz
Đang kiểm tra LLM...
ERROR: LIVEBACKEND INITIALIZATION FAILED
Reason: ValueError: openai_compatible provider requires 'base_url' and 'model' in config
```

- Data (`resource/corpus|item_knn|mapped|splits/multi_domain`) **đã sẵn sàng** — nạp
  thành công ~6s.
- Chặn ở `live_backend.py:223-225` (`_ensure_planner` → `build_llm_provider` +
  `health_check`); `run_demo.main` luôn `initialize_planner=True` (L322) nên **demo
  không khởi động được kể cả khi chỉ định dùng Type1** — LLM là bắt buộc lúc boot.
- `configs/agent/llm.yaml`: `base_url: ${LLM_BASE_URL:-}`, `api_key: ${LLM_API_KEY:-}`
  — cần export 2 biến này.

### B4. Rủi ro trạng thái — đánh giá

- `respond()` giữ `self._lock` suốt request (`live_backend.py:248`) → mọi request
  tuần tự; Gradio `demo.launch` không set concurrency nhưng queue mặc định + lock
  backend là đủ.
- Executor là singleton dùng chung (`_executor_planner`, `_executor_planner_memory`,
  L59-60, tạo một lần L227-228). Mỗi request gán `executor.session`/`reflect_rounds`
  rồi **reset trong `finally`** (L338-340) → không rò session/reflect khi exception.
  `executor.session = None` sau mỗi request (L340) — single-turn không thấy session cũ.
- `self._sessions` tách theo `session_key`; LRU evict đúng (`_session_for` L392-409).
  Hai key đồng thời **không lẫn** vì (a) lock serialize, (b) mỗi key một Session
  object — đã có test `test_two_keys_do_not_share_state`.
- `session_key` là `uuid4().hex[:12]` per browser-state → 2 tab trình duyệt có key
  khác nhau → không đụng nhau; nhưng `_sessions` là state **server-side chia sẻ**
  giữa mọi client — key đoán được sẽ đọc được session người khác (rủi ro thấp vì
  uuid ngẫu nhiên + bind 127.0.0.1, `share=False`).
- Edge nhỏ: type1 + inference_mode=llm sau khi backend init bằng type1+template →
  `self._llm=None` → `compose_answer` fallback `no_llm` (`compose_answer.py:36-37`),
  không crash — degrade êm.
- `executor.last_plan/last_usage/...` đọc sau finally (L345-363) — an toàn vì lock.

### B5. tests/demo — 80 passed (19.0s), log `experiments/test_logs/test_results_20261114_212404.md`

Đã cover headless: `test_live_backend_session.py` kiểm đúng session_turns tăng
(1,2,3), key mới → hội thoại mới, hai key không lẫn, LRU evict, không key →
single-turn; `test_gradio_ui.py` chỉ build UI + gọi backend trực tiếp.

**Hành vi CHƯA có test (tầng UI/handler):**
- `on_clear_history` trả key uuid mới + xóa history (run_demo.py:174-176).
- `profile_dropdown.change` → key mới (đổi profile = reset hội thoại) (L265-269).
- Nút New conversation / Clear history → key mới (L271-281).
- `multiturn_toggle=False` → `session_key=None` tới backend (L212).
- `session_turns` hiển thị trên status_md (L229-230).

**Đề xuất test (D4, chưa viết):** các closure handler nằm trong `build_ui` — test qua
`demo.fns`/dependencies của Gradio Blocks hoặc monkeypatch `backend.respond` ghi lại
`DemoRequest.session_key` nhận được; double = `OfflineDemoBackend`/
`MagicMock` executor như `test_live_backend_session.py`. Fake chỉ trong `tests/`.

### B6. Kịch bản kiểm tay (cần LLM thật)

Chuẩn bị: `LLM_BASE_URL`, `LLM_API_KEY`; data multi_domain đã có trong `resource/`;
`pip install gradio` (đã có — pytest importorskip pass). Ảnh lưu
`docs/demo_screenshots/yyyyMMdd-HHmm-demo-<tên>.png`.

PowerShell:
```powershell
cd C:\Users\ph181\Documents\Repositories\agentic-rag-for-rcm-sys\src
$env:PYTHONPATH="."
$env:LLM_BASE_URL="<endpoint>"; $env:LLM_API_KEY="<key>"
python scripts/demo/run_demo.py --domain Video_Games --domain Toys_and_Games --domain Electronics
```
bash:
```bash
cd <repo>/src && PYTHONPATH=. LLM_BASE_URL=<endpoint> LLM_API_KEY=<key> \
  python scripts/demo/run_demo.py --domain Video_Games --domain Toys_and_Games --domain Electronics
```

3 hội thoại đề xuất:
1. **Multi-turn planner** (profile blank, Multi-turn ON, Memory OFF):
   - Turn 1: "Gợi ý 5 game hành động" → kỳ vọng status ok, plan+steps trong tab
     Trace, items có giá/rating, badge "Conversation turn: 1".
   - Turn 2: "Bỏ các game bắn súng, chỉ giữ game dưới 300k" → turn 2, exclusions
     xuất hiện trong trace args.
   - Ảnh: `demo-01-planner-turn1.png`, `demo-02-planner-turn2.png`.
2. **Memory ON + profile warm**: chọn profile non-blank, bật Memory → turn 1 hỏi
   gợi ý → tab Memory hiện snapshot before/after, "MemoryTool called?" ✓/✗;
   turn 2 tham chiếu context turn 1.
   - Ảnh: `demo-03-memory-tab.png`, `demo-04-memory-turn2.png`.
3. **Type1 + template vs llm inference**: mode Type1, profile warm → 1 request;
   đổi Inference llm → request tiếp; request mơ hồ ("gợi ý gì đó") → ask_user;
   bấm New conversation → turn counter reset, session mới.
   - Ảnh: `demo-05-type1.png`, `demo-06-askuser.png`, `demo-07-new-conversation.png`.

---

## PHASE C — Ba điểm nối dở

### C1. `_run_all` có gọi LLM thật cho multi-turn? — CÓ, và không có cách tắt

- `_run_all.py:82` luôn `results["multi_turn"] = _run_multi_turn()`;
  `_run_multi_turn` (L149-186) chỉ skip khi `load_config("agent/llm").base_url`
  rỗng (`_llm_configured` L140-146 → `skipped_no_credentials` L158-163). Khi có
  `LLM_BASE_URL` → subprocess `python -m package.evaluation.multi_turn._run`
  (L166-167) → `RealAgentRunner` gọi LLM thật (`_agent_runner.py:33-56`).
- **Không có flag/config tắt**: `component_benchmarks.yaml` chỉ có
  `runs/datasets/run_backlog/backlog_datasets/configs` — không key nào cho
  multi_turn; `run_all_benchmarks()` không nhận tham số bỏ qua.
- Quan trọng: planner benchmark cũng cần LLM (`planner_benchmark` raise nếu
  thiếu base_url) → **mỗi lần chạy component benchmarks có LLM là multi-turn
  chạy thêm một lần nữa**, song song với multi-turn của campaign → duplicate
  LLM cost + 2 artifact có thể lệch số.
- Mức sửa nhỏ nhất (đề xuất, Phase E): thêm `component_benchmarks.multi_turn.enabled`
  (default true giữ hành vi cũ) đọc trong `run_all_benchmarks` trước L82; hoặc
  `run_all_evals` truyền override qua `CONFIG_OVERLAY_PATH`. Không ảnh hưởng
  campaign/resume_identity (component bench không đụng run_agent_eval).

### C2. provider_error / judge_error trong unified_report

- `judge_error_count`: **CÓ** trong unified_report — là metric per-case của
  grounding (`grounding_benchmark.py:103,120`) → aggregate mean
  (`_run_all.py:286-304`). Xác nhận trên artifact
  `unified_report_20261110_210732.json`: `components.grounding.metrics` chứa
  `judge_error_count, unsupported_count, total_claims, grounding_rate,
  hallucination_rate, claims_supported, label_agreement`.
- `provider_error`: **KHÔNG có field riêng** trong unified_report. Component
  benchmark không emit metric này — `run_case` bắt mọi exception →
  `success=False` + `error` string (`_evaluator.py:114-121`); unified_report chỉ
  surface `failed_cases` count + `error` khi cả component fail
  (`_run_all.py:239-246, 288-289, 331-345`). Chi tiết lỗi từng case chỉ nằm trong
  `<comp>_benchmark_<ts>.json` → `per_case_results[].error`.
- Phía campaign thì `provider_error` LÀ cột scored/trajectory
  (`run_agent_eval.py:97`, `scored.jsonl` 87 cột có `provider_error` — xác nhận
  trên artifact exp_9 run_1: 132 dòng, provider_error=0).
- multi_turn: `failure_distribution` + `failed_conversations` được surface
  (`_run_all.py:254-281`).

### C3. Trajectory có đủ cho Jev chấm? — Đủ sau khi join corpus

`trajectories.jsonl` (per-run, copy của log — `run_agent_eval.py:637`) mỗi record có:

- `text` (request gốc), `answer` (câu trả lời cuối), `answer_status`,
  `answer_composer`, `answer_fallback`, `recommended` (item ids),
  `steps[].args/output_summary`, `provider_error`, `usage`, …
- `scored.jsonl` (87 cột) **không chứa `answer` text** — phải đọc trajectories.

Thiếu: **item evidence đầy đủ**. `recommended` chỉ là list item_id;
`steps[].output_summary` là summary (vd `candidates.first_ids` + `keys`,
không có price/rating/title). → jev_on_trajectories **làm được mà không chạy lại
agent** bằng cách join ngược: `recommended` ids → `SELECT item_id, domain, title,
store, price, average_rating, rating_number, main_category FROM items WHERE
item_id IN (...)` trên `resource/corpus/<tag>/corpus_<tag>.sqlite` — đúng bộ
`ITEM_FIELDS` Jev cần (`evaluate_product_reply_with_jev.py:31-32`,
`inference/_schema.py:3-5`; live_backend.py:138 select cùng các cột).

Lưu ý/giới hạn:
- Answer composer chỉ trình bày outcome items (= recommended) → evidence =
  recommended là đúng phạm vi; claim về item trong candidates không nằm trong
  answer thường không bị chấm (trừ khi LLM tự bịa — đó là hallucination cần bắt).
- `answer=None`/rỗng (baseline agent, ask_user/no_result/tool_error) → bỏ qua
  hoặc chấm với items rỗng — cần quyết trong config D2.
- Template-mode answer in verbatim evidence → khó hallucinate; llm-mode mới là
  đối tượng chính của Jev.

### C4. Grounding raise khi thiếu Jev (chạy trực tiếp)

Xác nhận: `use_jev: true` trong `component_benchmarks.yaml:27-28`. Thiếu
credential → `JevProvider` raise → `evaluate_product_reply_with_jev` trả
`evaluation_state="provider_error"` (`evaluate_product_reply_with_jev.py:55-74`)
→ `GroundingBenchmark.run_component` raise `RuntimeError` (L78-79) → **mọi
case success=False** khi chạy `run_benchmark_cli` trực tiếp.
Qua `_run_all` thì bị chặn sớm hơn: `_jev_configured()` (`_run_all.py:125-137`,
check `judge.yaml api_key`=`${JEV_API_KEY}` hoặc env
`TYPESAFE_API_KEY`/`OPENROUTER_API_KEY` — khớp `jev_provider.py:29-37`) →
`skipped_no_credentials` (`_run_all.py:43-51`). **Đừng nhầm hai đường này.**

---

## PHASE D — Kế hoạch chi tiết (chưa viết code)

Ảnh hưởng chung: D1/D2/D3/D5 **không** đụng `resume_identity`/`metrics.json` của
run_agent_eval (component bench, script ngoài campaign, demo là các đường riêng);
riêng D3 có 1 thay đổi nhỏ trong `_run_all.py` (thêm config key) — cũng ngoài
resume path. Kỳ vọng: metrics.json byte-identical cho cùng input.

### D1. Sửa git_sha rỗng + surface provenance trong unified_report

**Đã duyệt kèm chỉnh sửa**: thêm `provider_error_count` vào unified_report
(cùng `judge_error_count` vốn đã là metric mean — C2).

- Sửa `package/evaluation/component/run_benchmark_cli.py:237`:
  `evaluator.run_benchmark(cases, component_name=..., runs=runs, git_sha=git_sha)`
  → top-level `git_sha` trong `<comp>_benchmark_<ts>.json` có giá trị.
- Sửa `package/evaluation/component/_run_all.py` `aggregate_results`: đọc thêm
  `result["metadata"]["git_sha"]` làm fallback và surface
  `metadata.provenance` (llm/judge/dataset_sha256/config hash) vào
  `aggregated["components"][c]["provenance"]`; thêm `provider_error_count`
  (đếm per-case có cờ provider_error — component bench hiện không emit metric
  này, case fail do provider error chỉ nằm trong `error` string; implementation
  chốt cách đếm: cờ `provider_error` trên case result hoặc pattern error);
  markdown renderer in thêm dòng provenance + provider_error_count.
- Test hồi quy: `tests/evaluation/component/test_run_all_provenance.py` (ĐÃ VIẾT,
  chưa commit — đang ĐỎ chờ Phase E): git_sha fallback từ metadata, provenance
  surface, provider_error_count=1/0.
- Rủi ro: thấp — chỉ đọc thêm field, không đổi shape bắt buộc.
- Công sức: ~0.5 ngày.

### D2. `jev_on_trajectories` (script ngoài campaign)

- File mới `scripts/evaluation/jev_on_trajectories.py` + config mới
  `configs/eval/jev_on_trajectories.yaml`:
  - `runs`: list glob/đường dẫn `trajectories.jsonl` (mặc định
    `experiments/agent_eval/campaigns/campaign_001/*/run_*/trajectories.jsonl`).
  - `sample.per_kind`: n mỗi request kind — **mặc định 10 cho lần chạy thử**
    (chỉnh trong YAML), `seed` cố định, `min_answer_status: ["ok"]`,
    `agents` filter (mặc định planner, planner_memory), `skip_empty_answer:
    true`. Báo cáo phải in **n thực tế sau lọc** (answer rỗng/None bị loại).
  - `corpus`: tag/dataset để resolve corpus sqlite (mặc định multi_domain).
  - `output_dir`: `experiments/agent_eval/jev_on_trajectories/<ts>/`.
- Luồng: đọc trajectories → join `kind` từ `scored.jsonl` (cùng run dir, key
  request_id) hoặc `requests.jsonl` → stratified sample theo kind (seed cố
  định) → lấy `recommended` ids → SELECT ITEM_FIELDS từ corpus sqlite →
  `evaluate_product_reply_with_jev(request=traj["text"], items=rows,
  answer=traj["answer"])` → ghi `jev_trajectories_<ts>.json` (per-case +
  aggregate: supported/unsupported/judge_error counts, grounding_rate,
  evaluation_state) + `.md`.
- Thiếu credential (check giống `_jev_configured`): ghi status file
  `skipped_no_credentials`, **không** tính pass, exit code riêng (0 với note,
  hoặc 2 — chốt khi viết). Báo cáo bắt buộc ghi: judge model
  (`judge.yaml.model`), số mẫu thực tế, câu "đây là MẪU phân tầng, không phải
  toàn bộ trajectory", tên file nguồn.
- Test (`tests/evaluation/`): fake JevProvider/monkeypatch
  `evaluate_product_reply_with_jev`; sample stratification đúng seed; join kind
  đúng; skipped_no_credentials path.
- Rủi ro: corpus sqlite phải cùng tag với run (config ghi rõ); item_id trong
  trajectories là namespaced `Domain::asin` khớp items.item_id.
- Chi phí: ~1 Jev call-set/case (claims × Noul + 4 Score). **Trước khi người
  dùng chạy thật, script phải in ước lượng**: số case sẽ chấm (sau lọc), số
  claim ước tính (đếm sơ bộ trên answer mẫu hoặc dry-run dem claims), số Jev
  call ≈ claims + 4 Score/case, token ước tính — để người dùng quyết n/kind.
- Công sức: ~1 ngày.

### D3. `run_all_evals` (wrapper ngoài campaign)

- File mới `scripts/evaluation/run_all_evals.py`: subprocess tuần tự
  1. component benchmarks — `python -m package.evaluation.component._run_all`
     **với multi_turn tắt**: thêm `component_benchmarks.multi_turn.enabled`
     trong `component_benchmarks.yaml` + check ở `_run_all.py:82`.
     **Mặc định FALSE** (đã duyệt chỉnh sửa) — tránh gọi LLM trùng với campaign;
     `run_component_benchmarks.py` chạy tay cũng không còn bước multi-turn trừ
     khi bật explicit `enabled: true`.
  2. campaign — `python scripts/evaluation/run_campaign.py` (resume-aware sẵn).
  3. ablation — `python scripts/experiments/compare_experiments.py` (+ optional
     pairwise_ablation theo config).
  4. jev_on_trajectories (D2) — chỉ khi có JEV credential; không thì in
     skipped_no_credentials.
- In **bảng chỉ mục** cuối: eval → con số chính → file artifact → lệnh tái
  hiện → trạng thái (success/skipped_no_credentials/failed/not_evaluated).
  `not_evaluated` hiển thị "không có ngưỡng", không xanh/đỏ.
- `--dry-run` in kế hoạch không chạy; `--skip <step>` cho từng bước.
- Không đổi resume_identity/metrics.json (wrapper chỉ gọi subprocess).
- Test: dry-run output; parse bảng chỉ mục từ fake step outputs.
- Công sức: ~0.5–1 ngày (phụ thuộc D1/D2 xong trước).

### D4. Test headless tầng UI handler (demo)

Handlers là closure trong `build_ui` (`run_demo.py:162-294`) nhưng `gr.Blocks`
lưu chúng trong `demo.fns`/dependencies — test lấy `BlockFunction.fn` và gọi
trực tiếp với giá trị thường (closure nhận plain args, trả tuple). Double:
`OfflineDemoBackend`/`MagicMock` như `test_live_backend_session.py`; fake chỉ
trong `tests/demo/`.

Danh sách test đề xuất:
1. `test_clear_history_returns_new_session_key` — gọi fn của
   clear_history_btn/new_conversation_btn/profile change → key mới khác key cũ,
   history reset [] (run_demo.py:174-176, 265-281).
2. `test_profile_change_issues_new_key` — đổi profile_id → session_key_state mới.
3. `test_multiturn_off_sends_none_session_key` — gọi on_submit với
   multiturn=False → DemoRequest nhận được `session_key=None`; multiturn=True →
   giữ key (run_demo.py:212). Backend double ghi lại request nhận được.
4. `test_submit_shows_session_turns` — backend trả `session_turns=2` → status_md
   chứa "Conversation turn: 2" (run_demo.py:229-230).
5. `test_submit_updates_turn_history` — history tăng 1 dòng, tool_sequence từ
   trace.steps (run_demo.py:244-255).

Rủi ro: phụ thuộc cấu trúc `demo.fns` của Gradio version đang pin — test cần
skip/fail rõ nếu API đổi. Không sửa package/demo; nếu handler không với tới
được từ `demo.fns` thì báo cáo, không workaround bằng sửa package.

**Đã viết + PASS**: `tests/demo/test_ui_handlers.py` (7 test, chạy được ngay vì
handler là closure nhận plain args — gọi trực tiếp `BlockFunction.fn` từ
`demo.fns`, Gradio 6.30). Kết quả: 7 passed in ~3s
(`experiments/test_logs/test_results_20261114_213828.md`). Phát hiện khi viết:
status_md dùng format `**Conversation turn:** N` (bold), không phải
`Conversation turn: N`.

### D5. Demo chạy được khi thiếu LLM ở chế độ Type1 (thiết kế, chưa code)

Hiện `run_demo.main` gọi `backend.initialize()` mặc định
`initialize_planner=True` (run_demo.py:322 → live_backend.py:77-82 →
`_ensure_planner` L216-228 raise khi thiếu LLM). `initialize()` đã hỗ trợ
`initialize_planner=False` và `respond()` lazy-init đúng
(`live_backend.py:266`: `initialize_planner = mode != "type1" or
inference_mode == "llm"`).

Thiết kế nhỏ nhất đề xuất:
- `run_demo.py`: `backend.initialize(initialize_planner=False)` luôn (planner dựng
  lười), hoặc đọc `demo.yaml` key mới `require_llm_at_boot: false`.
- `live_backend._ensure_planner`: khi LLM fail → set
  `self._planner_available = False` + lưu lỗi, không raise (hoặc raise loại riêng
  `PlannerUnavailable`); `_respond_planner` bắt → trả `DemoResult(status=
  "tool_error", text="Planner không khả dụng: <lý do>")` thay vì exception.
- UI (`build_ui`): thêm `gr.Markdown` cảnh báo "Planner (LLM) không khả dụng — chỉ
  Type1/template" khi backend báo planner unavailable (truyền flag vào build_ui
  hoặc component update sau init), và/hoặc disable option planner trong
  mode_radio.
- Mặc định không đổi hành vi khi có LLM: planner vẫn lazy-init ở request đầu tiên
  (chậm hơn ~vài giây ở turn đầu) hoặc giữ eager khi credential tồn tại — chọn
  một, ghi rõ. Đề xuất: giữ eager khi `LLM_BASE_URL` non-empty, lazy-fail khi
  trống → boot không cần credential chỉ khi thực sự không có.
- Type1 + inference_mode=llm khi `self._llm=None` đã fallback êm
  (`compose_answer.py:36-37`, fallback_reason="no_llm") — UI hiển thị fallback
  sẵn có (run_demo.py:224-228).
- Test hồi quy: LiveBackend với `_ensure_planner` raise → respond planner trả
  tool_error rõ ràng, respond type1+template vẫn ok; run_demo build_ui với
  planner unavailable → warning component tồn tại.
- Công sức: ~0.5 ngày. File sửa: `package/demo/backend/live_backend.py`,
  `scripts/demo/run_demo.py`, có thể `configs/agent/demo.yaml` (+1 key).

### D6. Docs lỗi thời — danh sách + nội dung sửa đề xuất (chưa sửa)

| Chỗ | Hiện trạng | Sửa đề xuất |
|---|---|---|
| `docs/report_update_log.md:58` | "Multi-turn … mock-only; chưa có artifact" | Cập nhật: multi-turn chạy `RealAgentRunner` + LLM thật; artifact `campaigns/campaign_001/multi_turn/*/multi_turn.json` đã tồn tại (12 runs, status success trong campaign_result.json) |
| `docs/report_update_log.md:102` | bullet "multi-turn (mock-only)" | Đổi thành "multi-turn (real LLM, fixture corpus)" |
| `docs/report_update_log.md:109` | "multi-turn (mock-only)" trong status table | Tương tự; bỏ tag mock-only |
| `docs/report_update_log.md:197` | `run_agent_eval.py --eval-on validation --agents planner,planner_memory --mock false` | Sai flag: run_agent_eval không có `--agents`/`--mock`; agents qua `configs/agent/agent_eval.yaml` + CONFIG_OVERLAY_PATH. Sửa thành lệnh đúng hoặc xóa dòng |
| `configs/agent/demo.yaml:25` | comment "run_demo.py không --mock" | Flag đã xóa tuần 46; sửa comment thành "LiveBackend là backend duy nhất (offline double nằm trong tests/demo/fakes)" |
| `docs/eval_surface_inventory.md` §3 + open-question 2 | nói grounding raise khi thiếu Jev | Đã lỗi thời sau `_jev_configured` gate (`_run_all.py:43-51`) — cần cập nhật |
| `docs/repo_reading_update_log.md` | log lịch sử | Giữ nguyên (là log, không sửa) |

---

## R1–R3 — Phân tích reflection trên artifact thật (read-only)

Script: `scripts/eda_diagnostic/analyze_reflection_campaign_001.py` (mới, chỉ-đọc,
chạy `PYTHONPATH=. python scripts/eda_diagnostic/analyze_reflection_campaign_001.py`).
Nguồn: `experiments/agent_eval/campaigns/campaign_001/exp_{6,8,10,12}_*/run_1/{trajectories,scored}.jsonl`,
join theo (request_id, agent); reflect_succeeded lấy từ scored.jsonl
(`score_layer4_process.py:228-238`).

### R1. Đếm + phân loại

| Exp | Agent/mode | Trajectories | Reflect invoked | Rescued | NOT rescued |
|---|---|---|---|---|---|
| exp_6 | planner/template/r1 | 132 | 26 | 16 | 10 |
| exp_8 | planner/llm/r1 | 132 | 18 | 9 | 9 |
| exp_10 | planner_memory/template/r1 | 132 | 34 | 27 | 7 |
| exp_12 | planner_memory/llm/r1 | 132 | 34 | 27 | 7 |

Tổng: 112 invoked → 79 rescued (**70.5%** theo metric `reflection_succeeded` —
ĐÍNH CHÍNH ở mục F3: không dùng làm số báo cáo vì đếm nhầm unanswerable và trộn
process-metric; exp_8 fail thật ~4/18). 33 không cứu được.
Rescued theo kind: chủ yếu `personalized` (+ ít `exclusion` ở exp_8/10/12).

**Not-rescued — phân loại theo FINAL attempt** (lỗi persist; error_kind + bucket):

- `all_steps_ok_but_no_rec` (mọi step ok nhưng recommended rỗng): exp6=6,
  exp8=5, exp10=6, exp12=6 → **23/33 (~70%)** — reflect không tạo ra item vì
  upstream (FilterTool/SearchTool) trả candidates rỗng.
- `empty_candidates` (RankTool `candidates` is empty → tool_error): exp6=4,
  exp8=3, exp10=1 — cùng họ "empty upstream".
- `cascade_skip` (LookupTool `$N.ranked.*.item_id: skipped, step N failed`):
  hệ quả của step trước fail.
- **Lỗi tất định thấy được**: exp_12 `ref_null_price_range` —
  `$1.price_range.max: 'max' not found` (MemoryTool trả price_range=null) đúng
  case "C1 ref null"; exp_8 `other` — FilterTool `exclude_item_ids must be
  string(s), got non-string values: [[...]]` (LLM truyền list lồng — arg-shape
  bug, sửa tất định được).

**Giới hạn artifact (quan trọng)**: trajectories chỉ lưu plan/steps CUỐI
(`executor.last_plan` + best_results; `plan_executor.py:171` giữ
`last_attempt_plans` trong RAM, không ghi file). → **loại lỗi của lần chạy ĐẦU
không phục hồi được từ artifact**, kể cả cho request được cứu. Phân loại trên là
"lỗi còn tồn tại sau reflect", không chắc trùng lỗi ban đầu.

**Chi phí reflect (L5, `usage` đã gồm mọi LLM call kể cả reflect —
`plan_executor.py:47`)**:

- Request invoked: attempts mean=2.0 (đúng 1 reflect round), prompt_tokens
  ~5.5–6.4k, llm_latency ~19–21.5s vs no-reflect ~2.7–3.0k tokens, ~11–13s.
- Paired delta vs exp r0 cùng request_id (seed=42 → cùng request set):
  toàn exp: prompt_tokens +377→+869/request; **chỉ request invoked**:
  prompt_tokens +2.9k→+3.4k, llm_latency +4.9→+11.1s, attempts +1.0.
- Tức mỗi reflect tốn ~1 LLM call (~3k prompt tokens); tỷ lệ "cứu" theo
  `reflection_succeeded` là 70.5% nhưng con số này không dùng làm headline
  (đính chính F3 — unanswerable artifact + process-metric).

### R2. Bao nhiêu request được cứu thuộc loại "sửa tất định được"?

**KHÔNG ĐẾM ĐƯỢC từ artifact hiện tại** — trigger của reflect
(`_reflect_problem`, `_helper.py:197-224`) và step report lần đầu
(`_step_report`) không được persist. Cận dưới/bằng chứng gián tiếp:

- Trong 33 not-rescued có ít nhất 2 lớp lỗi tất định-rõ-ràng: ref null
  (`price_range.max` từ MemoryTool) và arg-shape (`exclude_item_ids` list lồng)
  — chứng tỏ các lớp này TỒN TẠI trong population reflect-invoked; bao nhiêu
  trong số 79 rescued thuộc lớp đó thì không biết.
- Muốn đếm chính xác: cần persist `first_attempt_report` (problem string +
  error_kind step fail đầu tiên + `last_attempt_plans`) vào trajectory — thay
  đổi nhỏ ở `run_planner`/`empty_trajectory` (ngoài resume_identity vì chỉ là
  field log mới; cần xác nhận lại khi implement).

### R3. Đề xuất hướng tối ưu reflect (chưa làm)

1. **Persist first-attempt diagnostics** (đề xuất gốc cho R2 chính xác lần sau):
   ghi `first_attempt_problem` + error_kind + `attempt_plans` vào trajectory.
   Chi phí ~0, mở khoá phân tích này vĩnh viễn.
2. **Short-circuit reflect khi vấn đề là "empty upstream"**: ~70% not-rescued là
   candidates rỗng → `_reflect_problem`/`_blocks_reflect` có thể nhận diện
   "không step nào trả item vì candidates=0" là không-reflectable (reflect LLM
   không tạo ra data) → tiết kiệm ~1 call/request trong nhóm này, hoặc route
   sang fallback ItemKNN/baseline thay vì plan mới.
3. **Sửa tất định trước LLM** (không cần reflect):
   - ref null: `_resolve_refs`/prompt quy ước "bỏ filter khi field null" hoặc
     MemoryTool không trả `price_range` khi null → chặn `ref_null_price_range`.
   - arg-shape: normalize `exclude_item_ids` (flatten list lồng → set string)
     trong `_execute`/tool validation → chặn lỗi exp_8.
   - `empty_candidates`: RankTool/LookupTool downstream tự skip hoặc fallback
     khi upstream trả 0 → tránh cascade_skip.
4. **Giữ reflect_rounds=1 + quality gate hiện tại** — tỷ lệ cứu theo
   `reflection_succeeded` ~70% với ~+1 call/invoked (xem đính chính F3: không
   trích làm headline); chỉ tối ưu phần "reflect vô ích" (empty upstream)
   và "lỗi tất định" (mục 3) thay vì tắt reflect.

---

# PHASE R (tiếp): R4–R7 — chỉ đọc, chưa sửa package/

## R4. exp_10 vs exp_12 — trajectory riêng, không lẫn

- `trajectory_file` per-exp: `campaign_runner.py:411` đặt
  `{campaign_id}_{experiment.name}_run{N}_trajectories.jsonl` → exp_10 và exp_12
  có file riêng (`exp_10_agents_planner_memory_inference_mode_template_...` vs
  `exp_12_..._llm_...`).
- Resume cross-check: `resume_identity` chứa `inference_mode` + `agent_config`
  (`run_agent_eval.py:478-479`); `is_resumable` so `evaluation_protocol_hash`
  (`run_agent_eval.py:116-126,501-503`) → record của exp_10 không thể resume
  sang exp_12 kể cả cùng file.
- Đếm trên artifact (script inline, lệnh `python -c` đọc trực tiếp):
  invoked exp_10=34, exp_12=34, **overlap request_id chỉ 19/34**; trong 19
  request cùng reflect, final plan giống nhau 12, khác 7 (LLM nondeterminism —
  inference_mode chỉ đổi answer composition, planner vẫn gọi LLM riêng mỗi run).
- Kết luận: trùng số 34/27/7 là **trùng hợp**, không phải lẫn trajectory.

## R5. Vì sao exp_8 chỉ cứu 9/18 — phân loại 9 not-rescued (per-request)

| Nhóm | n | kind | Mô tả |
|---|---|---|---|
| Unanswerable "đúng nhưng metric tính fail" | 5 | `unanswerable-none-0..4` | Không step fail, `recommended` rỗng = **đúng** (unanswerable → không gợi ý), `task_success=True`, nhưng `reflection_succeeded=False` vì `final_has_rec=False` (`score_layer4_process.py:234-236`). |
| Cascade empty-candidate | 3 | `personalized-sparse-2`, `personalized-warm-3`, `personalized-warm-6` | `RankTool tool_error` → `LookupTool bad_reference`, rec rỗng, `task_success=None` (planner không có MemoryTool → personalized không được chấm, `score_trajectory.py:77-79`). |
| Arg-shape | 1 | `exclusion-warm-6` | `FilterTool tool_error` (nested list `exclude_item_ids`) → cascade `RankTool/LookupTool bad_reference`; rec có nhưng `task_success=False`. |

→ Trong 9 "not rescued" chỉ **4 là fail thật** (3 cascade + 1 arg-shape); 5 là
artifact của định nghĩa `reflection_succeeded` đòi `recommended` non-empty —
request unanswerable trả lời đúng (rỗng) vẫn bị đếm là reflect thất bại.

## R6. Định nghĩa "rescued" trong script/phân tích

`rescued` = cột `reflection_succeeded` trong `scored.jsonl`, định nghĩa tại
`score_layer4_process.py:230-236`:

```
reflection_invoked AND (first_attempt_ok == False)
AND all(final steps ok) AND recommended non-empty
```

Đây là **process metric** ("right after fixing" — `score_trajectory.py:32`),
KHÔNG phải `task_success`. Hệ quả đo được:
- exp_6/exp_8 (`planner`, không MemoryTool): `task_success=None` trên mọi
  personalized row (`score_trajectory.py:77-79`) → không thể nói reflect có
  cứu đúng item hay không từ artifact; chỉ biết process đã sạch.
- exp_8: trong 9 rescued có 8 `task_success=None` + 1 `True`.
- exp_10/12 (`planner_memory`): rescued=27, `task_success` invoked=33 → phần
  lớn reflect-cứu cũng đạt task_success, nhưng vẫn có thể rescued∧¬task_success
  (chưa đếm riêng — CHƯA XÁC MINH, cần query thêm nếu cần).

## R7. Kế hoạch persist first-attempt (C2/C4) — CẢNH BÁO resume_identity

**Phát hiện then chốt**: `_source_fingerprint()` hash TOÀN BỘ `package/`,
`scripts/`, `configs/` (`.py/.yaml`, `save_experiment.py:24-47`) và nằm trong
`resume_identity` → `protocol_hash` (`run_agent_eval.py:474-484`).

→ **Mọi thay đổi code dưới 3 thư mục đó đều đổi `source_fingerprint` →
`protocol_hash` đổi → `--resume` trên trajectory file cũ raise
`SystemExit("Resume protocol mismatch")` (`run_agent_eval.py:501-502`).**

Hệ quả ngay bây giờ: script `scripts/eda_diagnostic/analyze_reflection_campaign_001.py`
đã tạo trong phase R **đã nằm trong scripts/ → fingerprint đã đổi** so với lúc
exp 7/8/11/12 ghi trajectory. Nếu campaign cần `--resume` các file đó, lần chạy
tới sẽ mismatch. (tests/, docs/, experiments/ KHÔNG bị hash — an toàn.)

Phương án cho C2 (persist first-attempt diagnostics):
- Dữ liệu cần: first-attempt step results (tool/ok/error_kind — hiện KHÔNG lưu;
  `run()` ghi đè `results`, `plan_executor.py:147-184` chỉ giữ `last_attempt_plans`
  = plans, không giữ step outcomes, và `problem` string là biến local không
  persist). Cần thêm `last_first_attempt_steps`/`last_reflect_problems` vào
  executor + ghi vào traj dict tại `run_agent_eval.py:179-181`.
- **resume_identity: SẼ ĐỔI** (fingerprint). Không có cách nào persist mà
  không đổi fingerprint — mọi .py edit đều bị hash.
- an toàn về schema: `score_trajectory`/`is_resumable` đọc key tên cụ thể,
  key mới trong trajectory không ảnh hưởng metrics.json/scored.jsonl.
- Khuyến nghị: chỉ làm SAU khi campaign_001 hoàn tất và không cần --resume nữa,
  hoặc chấp nhận re-run. Tương tự C4 (normalize `exclude_item_ids` trong
  package/) cũng đổi fingerprint → cùng ràng buộc.
- Rủi ro phụ: `last_attempt_plans` bị reset trong `plan()` (L142) — nếu thêm
  capture phải đặt TRƯỚC `_execute` đầu hoặc copy steps ngay sau L147.

---

# PHASE F-check (chỉ đọc): F1–F3

## F1. Mâu thuẫn `_source_fingerprint` — đã giải trình

- **Code đã commit (HEAD)**: `project_root = parents[5]` = repo root; các folder
  `package/scripts/configs` được tìm dưới repo root → **không tồn tại** (chúng
  nằm dưới `src/`) → `base.exists()` False → **chỉ hash `pyproject.toml`**.
  → Nhận định Phase 1 ("chỉ root pyproject.toml") **ĐÚNG với code committed**.
- **Working tree (chưa commit)**: `save_experiment.py` đang bị sửa — root đổi
  thành `parents[4]` = `src/` → giờ **thật sự hash package/+scripts/+configs**.
  Diff ghi rõ lý do: "parents[5] is the repo root where package/, scripts/ and
  configs/ do NOT exist — the old code silently hashed only pyproject.toml".
- **Tác giả/thời điểm**: thay đổi **uncommitted**, không thuộc commit nào
  (`git log -S` không thấy trong history; `git status` = ` M`). mtime file
  **2026-11-14 12:38** — SAU khi exp_12 ghi trajectory cuối (12:34). Cùng đợt
  uncommitted với `exclude_tools` ablation trong `run_agent_eval.py` (mtime
  12:50). Không xác định được phase nào tạo ra (nhiều khả năng session trước
  trong engagement này); **CHƯA XÁC MINH 100%** nội dung file đúng tại thời
  điểm các exp chạy.
- **Vì sao `experiment_timeout_seconds` 3600→7200 không gây mismatch** — hai
  lý do độc lập:
  1. Timeout là tham số **campaign-level** (`campaign.yaml:39` →
     `CampaignConfig`, `_schema.py:122,156`), chỉ dùng làm subprocess timeout
     (`campaign_runner.py:261,278`). Nó **không đi vào** `run_agent_eval` →
     không nằm trong `resume_identity`/`protocol_hash` dù fingerprint có hash
     configs/ hay không.
  2. Dưới fingerprint cũ (pyproject-only), configs/ vốn không được hash → mọi
     thay đổi yaml đều vô hình với resume.
- **RỦI RO RESUME HIỆN TẠI**: exp 7/8/11/12 trajectories ghi 11:42–12:34 hôm nay,
  fingerprint fix land ~12:38 + `run_agent_eval.py` sửa 12:50 + script
  `eda_diagnostic` mới thêm sau đó → **fingerprint hiện tại khác fingerprint
  lúc chạy → `--resume` trên mọi trajectory campaign_001 sẽ raise "Resume
  protocol mismatch" (`run_agent_eval.py:501-502`)**. Tương tự mọi exp 1-6,9,10.
  Nếu cần chạy lại: phải đổi `trajectory_file` name hoặc chấp nhận chạy mới.
  Đây là lý do F4: không thêm file vào `scripts/` cho tới khi chốt.

## F2. Tỷ lệ reflect theo định nghĩa đúng (task_success)

`rescued` = `reflection_succeeded` (process metric, `score_layer4_process.py:236`);
`task_ok` = final `task_success==True` trong scored (None = không chấm được —
planner không MemoryTool trên kind personalized, `score_trajectory.py:77-79`).

| Exp | Agent | invoked | refl_succeeded | task_success invoked (True/False/None) | refl_succeeded ∧ task_success=True |
|---|---|---|---|---|---|
| exp_6 | planner/template | 26 | 16 (61.5%) | 6 / 0 / 20 | 0 (16 rescued đều task_success=None) |
| exp_8 | planner/llm | 18 | 9 (50.0%) | 6 / 1 / 11 | 1 |
| exp_10 | planner_memory/template | 34 | 27 (79.4%) | 33 / 1 / 0 | 27 |
| exp_12 | planner_memory/llm | 34 | 27 (79.4%) | 33 / 1 / 0 | 27 |

Đọc đúng:
- **exp_6/exp_8 không đo được rescue ở mức task** cho personalized — 20/26 và
  11/18 invoked có `task_success=None` theo thiết kế (planner thiếu MemoryTool
  "cannot honestly personalize"). Chỉ kết luận được process-level.
- **exp_10/12**: invoked 34 → 33 kết thúc `task_success=True`; 27/34 vừa
  refl_succeeded vừa task_success. Reflect cứu process VÀ task ở đây.
- exp_8: 1 invoked có `task_success=False` (exclusion-warm-6 — case arg-shape).
- **Giới hạn**: trajectory chỉ lưu plan/steps CUỐI → không tách được "lần đầu
  fail loại gì" hay "task_success trước reflect" — mọi con số trên là final-state.

## F3. Đính chính diễn giải (đã sửa trong doc)

- ~~"70.5% rescue rate"~~ → **không dùng làm số báo cáo**: tử số/mẫu số trộn
  process-metric với request unanswerable bị đếm nhầm (xem R5: 5/9 not-rescued
  của exp_8 là unanswerable-trả-lời-đúng). Số đúng hơn cho exp_8: fail thật
  ~4/18 invoked.
- rescue rate chỉ nên trích kèm định nghĩa `reflection_succeeded` và lưu ý
  unanswerable artifact; headline an toàn là exp_10/12: 27/34 invoked
  refl_succeeded ∧ task_success.

---

# PHASE G (chỉ đọc): G1–G3

## G1. `exclude_tools` + toàn bộ uncommitted changes

### exclude_tools là gì
- `configs/agent/agent_eval.yaml` (+`exclude_tools: []`), schema
  `AgentEvalConfig.exclude_tools` (`_schemas.py:114-117`).
- `agent_tools.py`: `validate_tool_names()` + `for_planner(exclude_tools)` /
  `for_planner_memory(exclude_tools)` lọc theo `type(t).__name__`.
- `run_agent_eval.py:287-291,447-455`: đọc cfg → truyền vào toolset +
  `build_run_provenance`. `campaign_runner.py:298` thêm `exclude_tools` vào
  `_AGENT_CONFIG_KEYS` → campaign yaml có thể set per-experiment
  (`campaign_ablation_norank.yaml` mới: exp planner_memory -RankTool).
- **Test đã có**: `tests/agents/test_tool_subset.py` (untracked) — default
  không đổi, exclude RankTool/MemoryTool, tên sai → ValueError.
- **resume_identity**: CÓ đổi khi `exclude_tools != []` — key nằm trong
  `_resume_agent_config` (chỉ trừ `multi_turn`/`campaign_id`,
  `run_agent_eval.py:235`). Với `[]` default: giá trị giống nhau nhưng **key
  mới xuất hiện trong agent_config → protocol_hash vẫn khác run cũ** (giống
  mọi thay đổi identity). Đây là hành vi đúng cho ablation (arm khác phải
  không resume lẫn nhau), nhưng làm mọi trajectory cũ non-resumable — đã nằm
  trong rủi ro fingerprint ở F1.
- **metrics.json**: không đổi shape; `[]` → hành vi y hệt (test
  `test_default_unchanged` pin điều này).

### Toàn bộ uncommitted (120 entries `git status`; diff --stat 37 file, +2217/−693)

Nhóm theo mục đích:

| # | Nhóm | Files | Ghi chú |
|---|---|---|---|
| 1 | Campaign `--only` subset + merge/backup + `subset`/`git_sha` schema | `campaign_runner.py`, `_schema.py`, `run_campaign.py`, `test_only_subset.py` | Đã dùng để rerun exp 7,8,11,12 |
| 2 | `exclude_tools` ablation | `agent_tools.py`, `agents/__init__.py`, `toolkit/__init__.py`, `_schemas.py` (1 phần), `agent_eval.yaml`, `run_agent_eval.py`, `campaign_runner.py` (1 phần), `test_tool_subset.py`, `campaign_ablation_norank.yaml` | `_schemas.py` lẫn cả `max_sessions` → tách cần `git add -p` |
| 3 | Multi-turn hardening | `multi_turn/_run,_eval_step,_agent_runner,_schema,multi_turn_evaluator,conversations.jsonl` + 3 test files | limits plumbed-not-enforced, negative expectations, resolved_config provenance |
| 4 | Component benchmarks | `_run_all.py` (grounding skip + backlog + refactor `_run_component_cli`), `component_benchmarks.yaml`, `executor_benchmark.py`, 3 dataset jsonl, `test_run_all.py`, `test_week47_cases.py`, `test_run_all_provenance.py` (D1 red-test của tôi) | `test_run_all_provenance.py` CHƯA nên commit trước Phase E |
| 5 | Demo LRU session cap | `demo/_limits.py`, `live_backend.py`, `demo.yaml`, `test_live_backend_session.py`, `test_ui_handlers.py` (D4 của tôi) | `test_ui_handlers.py` chạy được, có thể commit riêng |
| 6 | Ablation stats/pairwise | `ablation/_statistics.py` (wilson), `_pairwise.py` (mới), `__init__.py`, `pairwise_ablation.py`, `ablation.yaml`, `test_pairwise.py`, `docs/ablation_scope.md` | |
| 7 | Fingerprint fix | `save_experiment.py` + `test_source_fingerprint.py` | **commit riêng, message phải nêu resume impact** |
| 8 | Docs + artifacts | `docs/*.md` mới, `campaign_001_summary.md` xóa, `experiments/` artifacts + `test_logs/` | artifacts có thể không commit hoặc commit riêng |
| 9 | EDA scripts | `scripts/eda_diagnostic/*` (3 file) | liên quan G2 |

Đề xuất thứ tự commit (mỗi commit một nhóm, message gợi ý):
1. `campaign: add --only subset runs with result merge/backup` (nhóm 1)
2. `multi_turn: plumb limits, resolved_config provenance, negative expectations` (nhóm 3)
3. `component benchmarks: skip grounding without Jev creds, backlog datasets, CLI refactor` (nhóm 4, tách `test_run_all_provenance.py` ra)
4. `demo: LRU cap on LiveBackend sessions` (nhóm 5, tách `test_ui_handlers.py` nếu muốn Phase F)
5. `ablation: wilson interval + pairwise report` (nhóm 6)
6. `agents: exclude_tools tool-subset ablation` (nhóm 2 — cần `git add -p` cho `_schemas.py`/`campaign_runner.py`)
7. `save_experiment: fix _source_fingerprint root so package/scripts/configs are hashed` (nhóm 7 — **ghi rõ trong message: invalidates --resume của mọi trajectory cũ**)
8. `docs: week47 eval/demo investigation + ablation scope` (nhóm 8 docs; artifacts tùy user)
9. `scripts: read-only EDA diagnostics for campaign_001` (nhóm 9 — sau khi chốt G2)

## G2. Đề xuất loại `scripts/eda_diagnostic/` khỏi `_source_fingerprint`

- **Vấn đề**: script chẩn đoán chỉ-đọc không ảnh hưởng hành vi eval nhưng vẫn
  làm đổi fingerprint → phá `--resume`.
- **Đề xuất**: trong `_source_fingerprint`, thêm loại trừ theo path part:
  `and "eda_diagnostic" not in path.parts` (hoặc hằng
  `_FINGERPRINT_EXCLUDED_PARTS = {"eda_diagnostic"}` để mở rộng sau). Phạm vi
  loại trừ tối thiểu = đúng thư mục chẩn đoán; `scripts/evaluation`,
  `scripts/experiments`, `scripts/demo` vẫn bị hash.
- **Test** (mở rộng `tests/evaluation/recommender/test_source_fingerprint.py`):
  - probe file trong `scripts/eda_diagnostic/` → fingerprint **không đổi**;
  - probe trong `package/` → fingerprint **đổi** (đã có test);
  - probe trong `scripts/evaluation/` → fingerprint **đổi** (thêm để chứng
    minh chỉ eda_diagnostic được miễn).
- **Ảnh hưởng**: resume sống sót qua thay đổi script chẩn đoán; rủi ro = ai
  đó đặt code ảnh-hưởng-hành-vi vào eda_diagnostic sẽ vô hình với fingerprint —
  giảm thiểu bằng convention tên thư mục + ghi chú trong docstring hàm.
- **Alternative đã cân nhắc**: hash allowlist scripts/ — chặt hơn nhưng dễ vỡ
  khi thêm thư mục script mới; loại trừ theo tên đơn giản và đủ cho nhu cầu.

## G3. Ghi nhận vào docs (đã thêm)

- 12 experiment campaign_001 là bản **trước sửa**, đóng băng, **không resume**
  (fingerprint hiện tại đã khác — F1).
- Tác dụng reflect phải đo bằng **so cặp r0 vs r1** (cùng agent/config trừ
  reflect_rounds), không bằng `reflection_succeeded` đơn lẻ — metric đó trộn
  unanswerable artifact và chỉ đo process, không đo task (F2).

---

# PHASE H (chỉ đọc): H1–H3 — chuẩn bị tách commit

## H1. Hunk-level map cho file chạm 2 nhóm

### `package/config/_schemas.py` (2 hunk)
- `@@ -111,6 +111,10` → `AgentEvalConfig.exclude_tools` → **nhóm 2** (exclude_tools)
- `@@ -542,6 +546,7` → `DemoConfig.max_sessions` → **nhóm 5** (demo LRU)
- Tách sạch bằng `git add -p` (2 hunk riêng, không lẫn dòng).

### `scripts/evaluation/run_agent_eval.py` (3 hunk — toàn bộ nhóm 2)
- `@@ -41` import `validate_tool_names`
- `@@ -284` đọc `exclude_tools` từ cfg
- `@@ -440` truyền vào `for_planner/for_planner_memory` + `build_run_provenance`
- Không lẫn nhóm khác → commit nguyên file trong nhóm 2.

### `package/evaluation/campaign/campaign_runner.py` (6 hunk)
- `@@ -5` `import shutil` → **nhóm 1**
- `@@ -26,28 +27,71` `_select_experiments` + `run_campaign(only=...)` → **nhóm 1**
- `@@ -78,9 +122,9` comparisons skip trên subset run → **nhóm 1**
- `@@ -95,15 +139,56` `result.subset` + `_merge_subset_result` + backup → **nhóm 1**
- `@@ -206,10 +291,11` **MIXED**: `git_sha=self.git_sha` (provenance → nhóm 1)
  + `_AGENT_CONFIG_KEYS` thêm `"exclude_tools"` (→ nhóm 2) — cùng một hunk,
  `git add -p` phải dùng `e` (edit) để tách, hoặc commit nhóm 1 lấy cả hunk rồi
  nhóm 2 không còn gì ở file này ngoài hunk `@@ -361`.
- `@@ -361,6 +447,10` overlay `agent_eval["exclude_tools"]` → **nhóm 2**

### `package/evaluation/campaign/_schema.py` (6 hunk — toàn bộ nhóm 1)
`git_sha` field trên `ExperimentRun`/`CampaignResult` + `subset` field +
serialization — commit nguyên file trong nhóm 1.

### `scripts/evaluation/run_campaign.py` (2 hunk — toàn bộ nhóm 1)
`--only` arg + resolve/merge logic.

### pytest cần chạy trước mỗi commit (đề xuất)
| Commit | Lệnh |
|---|---|
| 1 campaign --only | `pytest tests/evaluation/campaign/` |
| 2 multi_turn | `pytest tests/evaluation/multi_turn/` |
| 3 component | `pytest tests/evaluation/component/` |
| 4 demo LRU | `pytest tests/demo/` |
| 5 ablation | `pytest tests/evaluation/ablation/` |
| 6 exclude_tools | `pytest tests/agents/test_tool_subset.py tests/evaluation/campaign/` |
| 7 fingerprint | `pytest tests/evaluation/recommender/test_source_fingerprint.py` |
| 8 docs | không cần |
| 9 eda scripts | không cần (G2 test thêm sau) |

## H2. `exclude_tools: []` có đổi protocol_hash — XÁC NHẬN

- `_resume_agent_config` trả về **toàn bộ** key của `cfg` trừ `multi_turn` và
  `campaign_id` (`run_agent_eval.py:228-235`). `cfg` load từ
  `configs/agent/agent_eval.yaml` — giờ chứa `exclude_tools: []`.
- `resume_identity["agent_config"]` → `json.dumps(sort_keys=True)` →
  `protocol_hash` (`run_agent_eval.py:475-484`). Key `"exclude_tools": []` mới
  xuất hiện → JSON khác → **hash khác** kể cả giá trị rỗng.
- Đã ghi nhận: **mọi experiment chạy sau commit nhóm 2 đều không resume được
  từ trajectory campaign_001** (cộng thêm fingerprint fix nhóm 7 — cùng chiều
  mất resume, đã cảnh báo F1). Hành vi này đúng cho ablation (các arm phải có
  identity riêng) nhưng phải ghi rõ trong commit message nhóm 2.

## H3. Tag `campaign_001_frozen` — đề xuất

- **Không tag được ngay**: tag phải trỏ commit, mà trạng thái artifacts hiện
  tại là working tree uncommitted → phải commit trước.
- **Đề xuất**: sau khi commit xong nhóm 1–7 (code eval), tạo annotated tag:
  `git tag -a campaign_001_frozen -m "campaign_001 artifacts frozen: 12 exps
  ran on working tree 2026-11-14 11:42-12:34; pre fingerprint-fix; do not
  --resume"` đặt trên **commit cuối của nhóm code** (trước commit docs/artifacts
  nếu tách được, hoặc HEAD sau nhóm 7).
- **Lý do chọn**: tag đánh dấu "điểm không còn resume" — ai checkout tag này
  reproduce đúng behavior đã sinh artifacts (trừ chi tiết fingerprint timing
  12:38 đã nêu — artifacts sinh trước fix, nên lý tưởng nhất là tag trên commit
  chứa code tại thời điểm chạy; vì code đó chưa từng commit nguyên trạng, tag
  trên HEAD-sau-commit là gần nhất và phải ghi chú divergence trong message).
- Ghi vào docs: SHA tag + ngày + danh sách exp + cảnh báo non-resumable.
