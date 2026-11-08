# Phase 1 Report — Sửa lỗi che giấu kết quả

Ngày: 2026-11-09. Nhánh: `tools-building`. Baseline trước sửa: 1327 passed / 8 skipped / 2 xfailed.

## 1. File đã đổi (diff stat)

```
 package/config/_schemas.py                                   |   1 +
 package/evaluation/campaign/campaign_runner.py               |  16 +-
 package/evaluation/component/_run_all.py                     | 104 ++++++----
 .../component/benchmarks/grounding_benchmark.py              | 165 +++++++-------
 .../product_reply/evaluate_product_reply_with_jev.py         |  73 ++++---
 scripts/evaluation/run_agent_eval.py                         |  11 +-
 tests/evaluation/campaign/test_campaign.py                   |  55 +++++
 tests/evaluation/test_jev_reliability.py                     |   4 +-
```
File test mới (untracked): `tests/evaluation/test_judge_error_handling.py`,
`tests/evaluation/component/test_run_all.py`,
`tests/evaluation/component/benchmarks/test_grounding_phase1.py`.

Impact analysis GitNexus đã chạy trước khi sửa: cả 4 nhóm symbol LOW risk;
index stale 44 commit (tên file cũ `jev_product_evaluator.py`/`run_all.py`/`campaign/runner.py`),
đã đối chiếu bằng grep trước khi sửa.

## 2. Chi tiết từng mục

### 1.1 evaluate_product_reply_with_jev.py

- `JevProvider(...)` khởi tạo ngoài try → bọc trong try; thiếu `TYPESAFE_API_KEY`/lỗi init
  trả dict với `evaluation_state="provider_error"`, `judge_error_count=total_claims`,
  `claims=[]`, vẫn đúng hợp đồng "luôn trả dict". Caller `jev_smoke_test.py:61` đã in
  `evaluation_state` và chỉ coi `"success"` là pass → provider_error tự động exit 1.
- Batch Jev exception trước đây gán mọi claim `verdict="unsupported"` → nay gán
  `verdict="judge_error"`, đếm riêng `judge_error_count`, thêm
  `evaluation_state ∈ {success, partial_error, provider_error}`.
- Summary/hallucination chỉ tính trên `judged_claims` (loại `judge_error`).
- **Bug latent phát hiện khi viết test**: `JevProvider.evaluate()` trả tuple
  `(result, usage)` nhưng code cũ gọi `result.get("answers")` như dict → mọi faithfulness
  call luôn AttributeError → trước đây bị nuốt thành "unsupported" cho MỌI claim.
  Đã sửa thành `result, usage = jev.evaluate(...)`. Đây chính là lỗi judge bị tính như
  kết quả — test cũ mock cùng tuple nên không lộ.

Test hồi quy (FAIL trên code cũ → PASS sau sửa):
`test_judge_error_handling.py` (7 test: provider_error, partial_error, judge_error
không vào unsupported_count/hallucination_rate, tuple unpack),
`test_jev_reliability.py` (cập nhật expectation usage 10→20 vì cả faithfulness lẫn
communication giờ đều được gọi đúng).

### 1.2 grounding_benchmark.py

- Bỏ rule-based fallback cho `grounding_rate`: Jev lỗi/thiếu key → `success=False`,
  `error` ghi rõ, case FAIL (chạy thật không TYPESAFE_API_KEY: 32/32 fail,
  `success_rate: 0.0000`, trước đây fake `1.0000`).
- `score_component` đọc `evaluation_state`/`judge_error`; provider_error không còn ra
  `total_claims=0, hallucination_rate=0, success=True`.
- Answer tự sinh từ evidence được gắn nhãn `evidence_kind: "synthetic_answer_judge_only"`
  trong output + docstring (thay bằng inference thật để Phase 4).
- `prompt_injection_detected` tính thật từ request text thay vì hardcode 0.0.

Test mới: `test_grounding_phase1.py` (Jev exception → case fail không fallback;
provider_error → success=False; evidence_kind label; prompt injection detection).
Cập nhật `test_grounding_benchmark.py` (fake Jev giờ trả đúng shape tuple).

### 1.3 campaign_runner.py

- `run_campaign()` truyền `comparison_pairs` tự sinh xuống `_run_comparisons`
  (trước đọc `self.config.comparison_pairs` → auto-compare bị bỏ rơi khi config rỗng).
- `campaign_id` ghi vào overlay config → `config.yaml` của từng exp
  (`_schemas.py` thêm field `campaign_id`, `run_agent_eval.py` propagate khi có).
  Verify: `load_config('agent/agent_eval')` có key `campaign_id`.
- `_load_experiment_metrics` loại key không phải metric (`n`, count...) khỏi so sánh
  qua `_NON_METRIC_KEYS`.

Test mới trong `test_campaign.py`: `test_auto_comparison_pairs_are_actually_used`,
`test_build_config_overlay_includes_campaign_id`,
`test_load_experiment_metrics_excludes_sample_count`.

### 1.4 _run_all.py

- `main()` trả exit code 1 khi có component failed/not_implemented (trước luôn 0).
- Bỏ default `success_rate = 1.0`: `success_rate` nằm trong `result["metrics"]` chứ
  không phải top-level → code cũ **luôn** rơi vào default (fake PASS nặng hơn audit
  ghi). Nay thiếu key → `None` + đánh dấu failed.
- Executor: trạng thái riêng `not_implemented` (tính failed trong tổng, không che lỗi).
  Không xóa dataset/config/dòng liệt kê — chờ D1.
- Báo cáo tổng hiển thị số case fail cạnh mean metric.
- Parse "Results saved to:" thiếu → cảnh báo + `results_path=None`, và `None` được
  tính là failed trong tổng (đã kiểm chứng trong code + test).

Test mới: `test_run_all.py` (exit code, not_implemented, missing success_rate → fail,
fail count trong report).

## 3. Kết quả pytest

```
PYTHONPATH=. python -m pytest tests/ -q
========== 1341 passed, 8 skipped, 2 xfailed, 13 warnings in 48.67s ==========
```

1327 baseline + 14 test hồi quy mới = 1341. Skip/xfail không tăng.

## 4. Xác minh thêm (ngoài audit)

- Consumers của `evaluate_product_reply_with_jev`: chỉ `jev_smoke_test.py` (in
  `evaluation_state`, chỉ `"success"` là pass → an toàn) và docstring của
  `evaluate_product_reply.py` (rule-based path riêng, không liên quan). Không còn
  chỗ nào coi judge_error là kết quả.
- `generate_example_report.py`: không có caller trong pipeline thật (chỉ là CLI
  thủ công) — ghi nhận, chưa đụng (Phase 3.5).
- `_run_all.py` parse "Results saved to:": thiếu → warning + None → tính failed. OK.
- `except Exception` mới thêm: không có; các sửa đổi đều gắn cờ lỗi vào kết quả
  (`error` field, `evaluation_state`, `success=False`).

## 5. Báo cáo phương án D1 — Executor (CHỈ BÁO CÁO, chờ quyết định)

### (a) Nguyên nhân executor mất evaluator

Commit `89116e8` "Phase 10.1 Step 5: benchmarks real-only" (2026-11-08) **cố ý xóa**
`executor_benchmark.py` (114 dòng) vì "entirely built on ScriptedLLM + Controlled*
failure injection; failure-injection scenarios move to tests/ in a later phase".
Cùng commit xóa `controlled_filter_tool.py`, `controlled_similar_tool.py`,
`get_controlled_tools.py` khỏi package; `run_benchmark_cli.py` bỏ nhánh executor →
giờ raise `NotImplementedError`. `executor_dataset.jsonl` (35 case) và entry trong
`configs/eval/component_benchmarks.yaml` còn sót → `_run_all.py` liệt kê executor
nhưng luôn fail.

### (b) Phân tích 35 case executor_dataset.jsonl

- 5 case không có `tool_config` (tags: normal×5? — thực tế normal/reference/empty):
  `executor_001, 002` + 3 case khác — tái hiện được bằng tool thật
  (FilterTool/SimilarTool trên fixture corpus).
- 30 case có `tool_config` với key fault-injection: `sql_fail, sql_empty,
  itemcf_empty, sql_timeout, sql_rate_limit, itemcf_fail, sql_partial×3,
  sql_malformed, sql_random_error×2, sql_network_error×2, sql_auth_error×2,
  sql_schema_error×2, sql_data_error×2, sql_concurrent_error×2, sql_resource_error×2,
  sql_validation_error×2, sql_permission_error×2, sql_generic_error×2` — đây là lỗi
  hạ tầng KHÔNG tái hiện được bằng tool thật; cần ScriptedLLM/Controlled* (đã bị xóa
  khỏi package, còn bản trong `tests/`).
- `reflection_*` keys (retries, network_retry, query_fix, retry_delay, reduce_load,
  args_fix, fallback): cấu hình hành vi reflection của PlanExecutor — một phần tái
  hiện được bằng plan lỗi thật (SQL sai cú pháp, item_id không tồn tại, `$N.path`
  hỏng), một phần cần fault injection.

Ước lượng: ~5–8 case "normal/reference/empty/reference_error" chạy được thật;
~27 case còn lại chủ yếu cần fault injection hoặc reflection kịch bản.

### (c) Hai phương án

**Phương án 1 — Benchmark thật + unit test cho fault injection**
- Viết `ExecutorBenchmark` mới chỉ cho case tái hiện được (tool thật trên fixture);
  case lỗi hạ tầng chuyển thành unit test `PlanExecutor` trong `tests/` dùng
  `controlled_*_tool` (đã có sẵn trong tests/).
- Ưu: đúng nguyên tắc B (benchmark = đo thật, không fake); tái dùng fakes đã được
  phân loại đúng chỗ (tests/); dataset nhỏ gọn, không còn case "chết".
- Nhược: mất coverage benchmark cho 27 case fault-injection ở tầng eval; phải viết
  lại evaluator + có thể cần LLM thật cho reflection path (tốn LLM nếu chạy đầy đủ);
  effort trung bình.

**Phương án 2 — Giữ 35 case bằng fault injection, gắn nhãn `mock_execution`**
- Khôi phục Controlled* dưới dạng eval-double được gắn nhãn rõ `evidence_kind:
  "mock_execution"` trong mọi output; `pass` chỉ có nghĩa trong phạm vi fault-injection.
- Ưu: giữ nguyên coverage 35 case; effort thấp (tái dùng code đã xóa trong git history
  + doubles trong tests/).
- Nhược: vi phạm nguyên tắc B (benchmark không được fake tool/LLM); rủi ro số liệu
  benchmark bị đọc nhầm là chất lượng thật; phải duy trì nhãn mock_execution xuyên suốt
  reporting — đúng loại "che giấu" Phase 1 vừa dọn.

**Đề xuất của agent**: Phương án 1 — phù hợp quyết định Phase 10.1 đã cố ý xóa
ScriptedLLM/Controlled* khỏi benchmark, và nhất quán với nguyên tắc phân vùng mock/fake
mới. Nhưng cần người dùng chốt vì Task 3.2 audit liệt kê executor là 1 trong 5 component.

## 6. Việc chưa làm và vì sao

- Executor: chờ D1 (mục 5).
- Phase 2–6: ngoài phạm vi phase này.
- Chưa commit gì (theo quy tắc, chờ duyệt phase).
