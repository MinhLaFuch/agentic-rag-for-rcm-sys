# Đánh giá tích hợp Opik cho agentic-rag-for-rcm-sys

Ngày: 2026-11-09. Phạm vi: NGHIÊN CỨU — không sửa code. Bằng chứng đọc từ code hiện tại
(branch `tools-building`, HEAD `58628a4`) và tài liệu Opik chính thức (nguồn ghi ở §1).
Mọi claim về repo có dẫn `file:dòng`; claim chưa kiểm chứng được ghi "chưa xác minh".

## 0. Xác minh các điều "đã biết"

| Điều đã biết | Kết quả xác minh |
|---|---|
| `opik_phase_0/1/2*.md` không có trong repo | **Đúng.** `find` toàn repo chỉ ra `scripts/evaluation/opik_poc.py`; các phase doc chỉ được tóm tắt trong `repo reading.md:450-454` và `docs/audit_week46_report.md:55-64`. |
| Chỉ có `scripts/evaluation/opik_poc.py`, dry-run, metric 0.95 placeholder | **Đúng.** Docstring "DRY-RUN ONLY" (`opik_poc.py:13-15`), `value = 0.95  # PLACEHOLDER` (`opik_poc.py:61`), mọi thao tác dataset/experiment chỉ `print("Would create...")` (`opik_poc.py:116,139`). |
| Package `opik` đã cài, chưa có `@opik.track` | **Đúng một nửa.** `opik 2.2.143` cài trong **system Python** (`C:\Users\ph181\AppData\Local\Python\pythoncore-3.12-64`), KHÔNG có trong `.venv` của project và KHÔNG có trong `pyproject.toml` dependencies (`pyproject.toml:6-14`). Grep `opik` trong `package/`+`scripts/` chỉ ra `opik_poc.py`. |
| Lệch tên Option B / Option C | **Repo chỉ ghi "Option B: Complementary Integration"** (`repo reading.md:451`, `opik_poc.py:2`). Không tìm thấy chuỗi "Option C" ở bất kỳ file nào trong repo — nhãn "Option C" của backlog nhiều khả năng là cách đánh số khác (A/B/C xếp khác thứ tự). **Bản chất kết luận giống nhau: Complement.** |

## 1. Chức năng Opik (nguồn chính thức, truy cập 2026-11-09)

Nguồn: `https://www.comet.com/docs/opik/` (trang chủ), `/docs/opik/evaluation/overview.md`,
`/docs/opik/tracing/getting-started.md`, `/docs/opik/self-host/architecture.mdx`,
repo `github.com/comet-ml/opik`.

- **Tracing/observability**: ghi mọi LLM call, tool invocation, agent step thành trace/span
  tree; decorator `@opik.track` cho code tự viết, hoặc integration sẵn cho 30+ framework
  (LangChain, LlamaIndex, Anthropic, Bedrock, Gemini...). Cost tracking, dashboard,
  annotation queues, online evaluation rules cho production.
- **LLM evaluation**: Datasets + Experiments (chạy task function trên dataset items, chấm
  bằng metrics); 30+ pre-built metrics (hallucination, context recall/precision,
  answer relevance...); **custom metrics** qua `BaseMetric` (Python SDK); Test Suites với
  natural-language assertions; LLM-as-a-judge.
- **Experiment tracking**: so sánh nhiều experiment runs side-by-side trên cùng dataset.
- **Dataset management**: dataset versioning, items `{input, expected_output, metadata...}`.
- **Prompt/version tracking**: Prompt Library lưu và version prompts, Prompt Playground.
- **Triển khai**: Opik Cloud (Comet, cần `OPIK_API_KEY`+`OPIK_WORKSPACE`) hoặc self-host
  Apache-2.0 (Docker local / Kubernetes; stack gồm Java backend + Python backend +
  ClickHouse + MySQL + Redis + MinIO + Nginx — khá nặng). `OPIK_URL_OVERRIDE` trỏ về
  self-hosted instance.

## 2. Đối chiếu với framework đánh giá hiện tại

Bằng chứng đọc trực tiếp từ `package/evaluation/` và `scripts/evaluation/`.

| Chức năng RCM | Bằng chứng repo | Tương đương Opik | Đánh giá |
|---|---|---|---|
| **5-layer scoring** (L1 outcome ranking metrics, L2 interaction/task_success, L3 grounding/answer_status, L4 process/plan-valid/tool-selection, L5 deployment/token-latency-cost) | `score_trajectory.py:47-51` gọi 5 scorer; định nghĩa metric ở `layer1_outcome/score_layer1_outcome.py:15-42`, `layer2_interaction/...:10-28`, `layer3_grounding/...:10-21`, `layer4_process/...:12-26`, `layer5_deployment/...:11-25` | Opik metrics chấm **per dataset item** (input/output → score). Không có khái niệm "trajectory → 5 lớp metric phụ thuộc corpus ground-truth (item2id, targets, seen_item_ids)" | **Không đáp ứng** — metric RCM gắn chặt vào `ItemCorpus`, `request.targets`, `item2id`; port sang Opik custom metric phải tự viết lại toàn bộ logic chấm (xem `opik_poc.py:41-66` mới chỉ là placeholder). |
| **Component benchmarks** (memory, planner, executor, grounding, integration) | `configs/eval/component_benchmarks.yaml:9-14` (5 dataset); evaluators `component/benchmarks/{memory_correctness_evaluator,planner_benchmark,executor_benchmark,grounding_benchmark,integration_benchmark}.py`; runner `component/_run_all.py`, `_evaluator.py` | Opik Datasets + Experiments + custom metrics | **Bổ sung một phần** — Opik quản lý dataset items + per-case results tốt, nhưng metric chấm (oracle memory correctness, plan validity...) vẫn phải là RCM code gọi qua `BaseMetric`. |
| **Campaign** (nhiều experiment + parameter grid + repetition + auto comparison pairs) | `campaign/campaign_runner.py:28-93` (`run_campaign`, `expand_parameter_grid` `:37`, auto pairs `:49-53`, `_run_comparisons` `:291`), schema `campaign/_schema.py:44-65` | Opik Experiments = nhiều runs trên cùng dataset, so sánh side-by-side | **Bổ sung** — Opik UI so sánh experiments tốt hơn đọc `campaign_result.json` thủ công, nhưng campaign còn gắn `repetition_count`, `random_seed`, `campaign_hash` (`_schema.py:34-35`, `campaign_runner.py:34`) mà Opik không có khái niệm tương đương trực tiếp. |
| **Bootstrap CI / paired comparison** | `statistics/_bootstrap.py:14-58` (`bootstrap_confidence_interval`, `paired_bootstrap_difference`); campaign dùng ở `campaign_runner.py:14`; ablation `ablation/_statistics.py:9-27` (`bootstrap_ci`) | Chưa thấy trong docs đã đọc — Opik hiển thị metric diff giữa experiments, **chưa xác minh** có significance testing | **Không đáp ứng (chưa xác minh)** — rất có thể phải giữ code RCM cho CI. |
| **Ablation** (so 2 agent/groups theo request_id, trung bình nhiều runs, McNemar test, markdown report) | `ablation/_compare.py:12-76` (`pair_by_request_id`, `average_across_runs`), `ablation/_statistics.py:30-58` (`mcnemar_test`), `ablation/_report.py`, config `configs/agent/ablation.yaml` qua `_limits.py` | Không có tương đương — Opik không ghép cặp theo request_id hay test thống kê | **Không đáp ứng.** |
| **Provenance** (hash prompt/tool-schema, git sha+dirty, limits, overlay) | `provenance/build_run_provenance.py:40-127` (sha256 prompt `:68,76,79`, tool schema `:91`, git `:94`, limits `:97-115`); `save_experiment.py:17-35` (`_source_fingerprint` hash toàn bộ package/scripts/configs), record `:63-72` | Opik version prompts (Prompt Library) + experiment metadata tags | **Bổ sung một phần** — Opik giữ prompt versions, nhưng `source_fingerprint` + git dirty + config overlay hash là cơ chế reproducibility riêng của RCM, không có trong Opik. |
| **Jev** (LLM judge faithfulness, TypeSafe AI, structured Noul/Score) | `judge/jev_client.py` (deprecated wrapper), `product_reply/evaluate_product_reply_with_jev.py:52-61` (`JevProvider`, config `eval/judge.yaml`), CLI `scripts/evaluation/evaluate_with_jev.py` | Opik LLM-as-a-judge + custom metrics | **Song song, không thay thế trực tiếp** — Jev trả structured decision (Noul/Score + confidence) theo API TypeSafe; Opik judge dùng LLM provider riêng với prompt templates của Opik. Có thể gọi Jev *bên trong* một Opik custom metric nếu muốn hiển thị trên UI. |
| **Trajectory JSONL** | ghi ở `run_agent_eval.py:483` (`trajectories.jsonl`), `:485` (`scored.jsonl`), requests `:484`; load lại bởi `opik_poc.py:69-95` | Opik traces/spans | **Bổ sung** — trajectory JSONL là artifact local phục vụ scoring; Opik trace là dạng quan sát runtime. Hai thứ bổ sung nhau, không trùng. |
| **Thresholds pass/fail** | `component/_schema.py:133-135` (`thresholds_result`), `configs/eval/component_benchmarks.yaml:24-30` (memory min/max); regression thresholds 5%/10% ở `component/_regression.py:11-16` | Opik Test Suites assertions (pass/fail) + online eval rules | **Bổ sung** — Opik assertions hợp cho pass/fail ngôn ngữ tự nhiên trên traces; threshold dạng số trên aggregate metrics của RCM vẫn là config YAML riêng. |
| **Aggregation/summary** | `trajectory/summarize.py` (mean + percentiles theo agent→kind→segment) | Opik experiment dashboard | **Bổ sung** — Opik hiển thị trực quan hơn `metrics.json`/markdown report. |

## 3. Chi phí / độ phức tạp / bảo trì

- **Self-host vs Cloud**: self-host cần Docker stack nặng (Java + Python backend, ClickHouse,
  MySQL, Redis, MinIO — theo `self-host/architecture.mdx`). Cloud đơn giản nhưng **mọi trace
  (gồm user request, item title/price, câu trả lời) gửi ra Comet** — cần quyết định dữ liệu.
  Opik SDK có module `anonymizer` (thấy trong `dir(opik)` bản 2.2.143) — chưa xác minh mức
  độ cấu hình.
- **Dependency risk**: `opik` hiện chỉ cài ngoài project, chưa pin trong `pyproject.toml`.
  Thêm vào sẽ kéo theo phụ thuộc nặng (opik client + integrations). Version 2.2.143 đã cài
  sẵn nhưng không tái lập được trên máy khác nếu không khai báo.
- **Điểm gắn `@opik.track`** (nếu instrument): `PlanExecutor.plan()`/`run()`/`_execute`
  (`package/agents/planner/plan_executor.py:105,146`), từng tool call trong `_execute`,
  inference (`package/inference/`), và/hoặc `LLMProvider.complete`
  (`package/api/openai_compatible_provider.py`) để bắt mọi LLM call. Mỗi điểm cần quyết định
  log gì — log full prompt/response sẽ gửi nội dung user + dữ liệu item ra server Opik.
- **Tương thích Jev/TypeSafe**: không xung đột về code (Jev là HTTP client riêng,
  `jev_provider.py`), nhưng Opik LLM-as-a-judge cần LLM provider riêng — nếu self-host Opik
  vẫn gọi LLM ra ngoài qua Opik proxy. Jev giữ nguyên vai trò faithfulness judge; Opik judge
  chỉ nên bổ sung cho metric chủ quan khác.

## 4. Kiểm chứng thực tế (đã chạy trên máy này, 2026-11-09)

| Việc | Kết quả |
|---|---|
| `import opik` (system Python) | **Chạy được** — v2.2.143. Lưu ý: import xong SDK tự init client, in warning "No project name configured... Default Project", trỏ `http://localhost:5173`. |
| `Opik()` client | **Khởi tạo được** (lazy, chưa cần server ngay). |
| Custom `BaseMetric` + `ScoreResult` | **Chạy local hoàn toàn** — `score("a","b")` trả `ScoreResult(value=1.0)` không cần server. |
| `get_or_create_dataset` + `insert` | **Không chạy được** — không có Opik server ở localhost:5173; call treo retry (timeout 25s không trả về). Tức dataset/tracing/experiment **bắt buộc có server** (self-host hoặc cloud+key). |
| `.venv` project | `import opik` → `ModuleNotFoundError`. opik không nằm trong deps project. |
| `opik_poc.py` chạy thật | Không chạy — cần `experiments/agent_eval/exp_002` (không tồn tại; `experiments/agent_eval/` chỉ có `component_benchmarks/`) — khớp `audit_week46_report.md:64,279`. |

## 5. Kết luận: **Complement** (điều kiện: có Opik server)

**Lý do:**
- Toàn bộ giá trị cốt lõi của framework RCM (5-layer metrics gắn corpus ground-truth,
  bootstrap CI, McNemar, provenance hash, thresholds YAML, trajectory schema) là
  **domain-specific, deterministic, không thể thay bằng Opik metric có sẵn** — Opik
  custom metric cuối cùng vẫn phải gọi code RCM (đúng pattern `opik_poc.py` đã phác).
- Opik bổ sung đúng phần RCM thiếu: **tracing/span tree runtime** (hiện không có gì —
  `plan_executor.py` chỉ ghi `last_*` attributes, `run_agent_eval.py` mới là nơi ghi
  trajectory sau khi chạy xong), **UI so sánh experiments/datasets**, prompt versioning,
  production monitoring.
- Replace = viết lại toàn bộ scoring layer trong Opik metric wrappers + mất thống kê
  (CI/McNemar/provenance) → chi phí lớn, lợi ích âm. Keep Current = bỏ lỡ observability
  đang là gap đã được audit ghi nhận (`audit_week46_report.md:33,266`).

**Điều kiện đổi sang Keep Current:** nếu không deploy được Opik server (self-host quá nặng /
không chấp nhận cloud / không có key) — khi đó Opik chỉ là dependency chết, PoC dry-run đã đủ.

### Kiến trúc đề xuất (nếu Complement)

```
PlanExecutor.plan/run ──@opik.track──► Opik trace (span tree: plan → từng tool → inference)
        │                                    │
        ▼                                    ▼
trajectories.jsonl / scored.jsonl      Opik Server (self-host :5173 hoặc cloud)
        │                                    │
        ▼                                    ▼
score_trajectory (5 layers, GIỮ NGUYÊN)  Opik Dataset + Experiments
        │                                    │
        ▼                                    ▼
bootstrap CI / ablation / thresholds    Custom metrics = wrapper gọi RCM scorers
(GIỮ NGUYÊN trong package/evaluation)   (BaseMetric như opik_poc.py:41-66, nhưng
                                        implement thật, không placeholder)
```

### Thứ tự tích hợp đề xuất

| # | Bước | Rủi ro | Tốn LLM? |
|---|---|---|---|
| 1 | Deploy Opik self-host local (Docker) hoặc lấy cloud workspace + key | Hạ tầng nặng nếu self-host; cloud cần duyệt data egress | Không |
| 2 | Thêm `opik` vào `pyproject.toml` deps + `opik.configure()`/`OPIK_URL_OVERRIDE` | Version pin, import-time auto-init (đã thấy warning khi import) | Không |
| 3 | `@opik.track` lên `PlanExecutor.run`/`_execute` + inference compose; log metadata (request_id, agent, kind) — **không log full prompt/item text nếu chưa duyệt egress** | Làm chậm/bẩn trace nếu log quá nhiều; cần bọc try/except để eval không fail vì Opik | Không |
| 4 | Export `scored.jsonl`/`trajectories.jsonl` → Opik dataset items; implement `BaseMetric` wrapper gọi `score_trajectory`/summarize thật (thay placeholder 0.95) | Phải map request→item2id/corpus trong metric context; metrics phụ thuộc nhiều input ngoài input/output | Không (metric deterministic) |
| 5 | (Tùy chọn) Opik LLM-as-a-judge cho metric chủ quan; giữ Jev cho faithfulness | Tốn LLM call; Opik judge cần provider config riêng | **Có** |

### KHÔNG nên đưa sang Opik

- `score_layer1-5`, `score_trajectory`, `summarize` — metric gắn corpus/ground-truth.
- `statistics/_bootstrap.py`, `ablation/_statistics.py` (McNemar) — thống kê so sánh.
- `build_run_provenance.py`, `save_experiment.py` (`source_fingerprint`) — reproducibility.
- `component_benchmarks.yaml` thresholds + `_regression.py` — quality gate nội bộ.
- `evaluate_product_reply_with_jev.py` — Jev/TypeSafe judge giữ nguyên (có thể gọi bên trong Opik metric nếu muốn hiển thị).

## 6. Việc cần người dùng quyết / chuẩn bị

1. **Self-host hay Cloud**: self-host = Docker + tài nguyên (ClickHouse/MySQL/Redis/MinIO);
   cloud = `OPIK_API_KEY` + `OPIK_WORKSPACE`, dữ liệu trace ra Comet.
2. **Phê duyệt data egress**: trace chứa user request (text review Amazon), item metadata,
   câu trả lời — quyết định có được gửi ra ngoài không, hay bắt buộc self-host/anonymize.
3. **API key**: `OPIK_API_KEY` (cloud) hoặc không cần key nếu self-host local.
4. **Dependency**: thêm `opik` vào `pyproject.toml` (hiện chỉ có trong system Python,
   `.venv` project thiếu — `ModuleNotFoundError` đã xác minh).
5. **`OPIK_PROJECT_NAME`/`opik.configure()`**: tránh mọi trace rơi vào "Default Project"
   (warning đã thấy khi import).
6. Quyết định có chạy `opik_poc.py` thật sau khi có server hay viết integration path mới
   (khuyến nghị path mới: PoC chỉ là pattern demo, `audit_week46_report.md:162`).

---
*Ghi chú phương pháp: mục 1 dựa trên docs chính thức fetch ngày 2026-11-09; mục 4 là chạy
thật trên Windows/system Python; các điểm "chưa xác minh" (Opik có significance testing
không, mức anonymizer, dataset versioning chi tiết) không kết luận thay vì đoán.*
