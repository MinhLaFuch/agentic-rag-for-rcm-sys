# Executor benchmark — phân loại 35 case cũ (Phase 4.7 / D1)

Nguồn: `executor_dataset.jsonl` tại `89116e8~1` (commit xóa benchmark cũ).
Benchmark cũ build trên `ScriptedLLM` + `Controlled*Tool` fault injection —
đã bị xóa ở `89116e8` vì không phải real execution.

Quy tắc phân loại:

- **real_reproducible**: chạy được trên tool thật + fixture corpus, `_execute` scope,
  không cần LLM, không cần cờ `tool_config` giả lập.
- **fault_injection**: cần `tool_config` (`sql_*`, `itemcf_*`) mà tool thật không có.
- **fault_injection+reflection**: như trên, đồng thời kỳ vọng `reflection_rescued`
  → cần LLM (ScriptedLLM) — thuộc unit test reflection, không phải benchmark.

| case | tools | tool_config | phân loại | lý do |
|---|---|---|---|---|
| executor_001 | FilterTool | {} | real_reproducible | success path |
| executor_002 | SimilarTool→FilterTool (`$1.candidates`) | {} | real_reproducible | ref hợp lệ `$N.path` |
| executor_003 | FilterTool | sql_fail | fault_injection | SQL exception giả |
| executor_004 | FilterTool | sql_empty | fault_injection | empty-result giả; semantics "empty" đã có case thật mới |
| executor_005 | SimilarTool→FilterTool (`$2.candidates` — self/forward ref) | {} | real_reproducible | bad_reference thật qua resolver |
| executor_006 | FilterTool→FilterTool | {} | real_reproducible | multi-step độc lập |
| executor_007 | SimilarTool | itemcf_empty | fault_injection | ItemCF empty giả |
| executor_008 | FilterTool | sql_timeout | fault_injection | infra timeout |
| executor_009 | FilterTool | sql_rate_limit | fault_injection | infra rate limit |
| executor_010 | Similar+Filter | itemcf_fail | fault_injection | ItemCF fail giả |
| executor_011 | FilterTool | sql_partial | fault_injection | partial-result giả — **bỏ**: tool thật không có tương đương deterministic |
| executor_012 | Similar+Filter (`$1.candidates`) | sql_partial | fault_injection | như 011 + ref — **bỏ** |
| executor_013 | FilterTool | sql_malformed | fault_injection | malformed response giả |
| executor_014 | Similar+Filter | sql_partial + reflection_retries | fault_injection+reflection | cần LLM rescue |
| executor_015 | FilterTool | sql_random_error | fault_injection | random error giả |
| executor_016 | Similar+Filter | sql_random_error + reflection_retries | fault_injection+reflection | cần LLM rescue |
| executor_017 | FilterTool | sql_network_error | fault_injection | network error giả |
| executor_018 | Similar+Filter | sql_network_error + reflection_network_retry | fault_injection+reflection | cần LLM rescue |
| executor_019 | FilterTool | sql_auth_error | fault_injection | auth error giả |
| executor_020 | Similar+Filter | sql_auth_error | fault_injection | auth error giả |
| executor_021 | FilterTool | sql_schema_error | fault_injection | schema error giả |
| executor_022 | Similar+Filter | sql_schema_error | fault_injection | schema error giả |
| executor_023 | FilterTool | sql_data_error | fault_injection | data error giả |
| executor_024 | Similar+Filter | sql_data_error + reflection_query_fix | fault_injection+reflection | cần LLM rescue |
| executor_025 | FilterTool | sql_concurrent_error | fault_injection | concurrent error giả |
| executor_026 | Similar+Filter | sql_concurrent_error + reflection_retry_delay | fault_injection+reflection | cần LLM rescue |
| executor_027 | FilterTool | sql_resource_error | fault_injection | resource error giả |
| executor_028 | Similar+Filter | sql_resource_error + reflection_reduce_load | fault_injection+reflection | cần LLM rescue |
| executor_029 | FilterTool | sql_validation_error | fault_injection | validation error giả |
| executor_030 | Similar+Filter | sql_validation_error + reflection_args_fix | fault_injection+reflection | cần LLM rescue |
| executor_031 | FilterTool | sql_permission_error | fault_injection | permission error giả |
| executor_032 | Similar+Filter | sql_permission_error | fault_injection | permission error giả |
| executor_033 | FilterTool | sql_generic_error | fault_injection | generic error giả |
| executor_034 | Similar+Filter | sql_generic_error + reflection_fallback | fault_injection+reflection | cần LLM rescue |
| executor_035 | FilterTool | {} | real_reproducible | success path (duplicate-ish của 001) |

## Tổng kết

- **real_reproducible: 5** (001, 002, 005, 006, 035) — phủ bởi dataset mới 18 case,
  cộng thêm các case lỗi thật mới (unknown tool/args, invented id, bad arg types,
  bad-path/forward ref, empty result qua filter thật) mà bộ 35 case cũ **không có**.
- **fault_injection: 21** — tất cả cần `tool_config` flags tool thật không hỗ trợ.
  PlanExecutor không phân biệt text lỗi infra (tất cả → `tool_error`), nên thay vì
  21 case benchmark, taxonomy được unit-test ở
  `tests/agents/test_executor_error_taxonomy.py` (29 test, 13 nhãn × rescue/không).
- **fault_injection+reflection: 9** — cần ScriptedLLM reflection; hành vi reflection
  đã được `test_plan_reflect.py`/`test_reflection_behavior.py` phủ.

## Về executor_011 / executor_012 (đã bỏ)

Cả hai dùng `sql_partial` — giả lập SQL trả về một phần dữ liệu. Tool thật
(`FilterTool`/`SimilarTool` trên fixture corpus) không có cờ này và không có
cách deterministic để ép "partial". Đây là fault-injection trá hình: expected
`all_steps_ok: true` không kiểm chứng được gì trên tool thật. Case "empty result"
trong dataset mới dùng filter không khớp gì trên corpus thật — cùng semantics
"tool trả về ít/không item" nhưng là hành vi thật.

Lưu ý: `executor_005` (`$2.candidates` — ref tới step chưa chạy) là case
bad_reference tái hiện được hoàn toàn bằng resolver thật, nên được giữ trong
dataset mới.
