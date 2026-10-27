# Component Evaluation Inventory

Giai đoạn 0 - Kiểm kê hiện trạng và baseline test
Được tạo: 2026-10-27

## Phần A: Kiểm kê hiện trạng

### A.1. Evaluators end-to-end hiện có (layer1→layer5)

| Tên evaluator | Đường dẫn | Đo gì | Thuộc component nào | Có entrypoint/CI/Script thống nhất không? |
|--------------|-----------|-------|-------------------|-----------------------------------------|
| layer1_outcome | package/evaluation/layer1_outcome/layer1_outcome.py | Ranking metrics: precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k, seen_item_rate, seed_in_result, distinct_domains | Outcome (End-to-end) | Có - được gọi bởi score_trajectory.py |
| layer2_interaction | package/evaluation/layer2_interaction/layer2_interaction.py | Task success, constraint satisfaction, price_unknown_rate, asked_clarification | Interaction (End-to-end) | Có - được gọi bởi score_trajectory.py |
| layer3_grounding | package/evaluation/layer3_grounding/layer3_grounding.py | Answer status flags, answer_grounded, answer_fallback | Grounding (End-to-end) | Có - được gọi bởi score_trajectory.py |
| layer4_process | package/evaluation/layer4_process/layer4_process.py | Plan validity, plan attempts, n_steps, steps_ok_rate, invented_ids, reflections, first_attempt_ok, tool_selection_ok, args_valid_rate, price_arg_ok, category_arg_ok, used_ranker | Process (Planner/Executor) | Có - được gọi bởi score_trajectory.py |
| layer5_deployment | package/evaluation/layer5_deployment/layer5_deployment.py | Token usage, latency, provider_error, sql_time_budget_hits, inference metrics | Deployment (Runtime) | Có - được gọi bởi score_trajectory.py |
| score_trajectory | package/evaluation/score_trajectory.py | Ghép 5 layer lại thành 1 row per trajectory | Integration | Có - entrypoint chính cho trajectory scoring |
| summarize | package/evaluation/summarize.py | Aggregate scored rows theo agent/kind/segment | Integration | Có - được gọi sau score_trajectory |
| error_taxonomy | package/evaluation/diagnostics/error_taxonomy.py | Phân loại lỗi theo type (step-level và plan-level) | Diagnostics | Có - tool cho phân tích lỗi |
| failure_rates | package/evaluation/diagnostics/failure_rates.py | Tính tỷ lệ lỗi theo agent/kind/segment | Diagnostics | Có - tool cho phân tích lỗi |
| reflection_diagnostics | package/evaluation/diagnostics/reflection_diagnostics.py | Phân tích reflection behavior | Diagnostics (Reflection) | Có - tool cho phân tích reflection |
| ablation/compare | package/evaluation/ablation/_compare.py | So sánh giữa 2 agent/groups với bootstrap CI, McNemar test | Ablation | Có - được gọi bởi ablation runner |
| ablation/loader | package/evaluation/ablation/_loader.py | Load scored data từ experiments, check compatibility | Ablation | Có - được gọi bởi ablation runner |
| ablation/report | package/evaluation/ablation/_report.py | Tạo báo cáo so sánh ablation | Ablation | Có - được gọi bởi ablation runner |
| ablation/statistics | package/evaluation/ablation/_statistics.py | Bootstrap CI, McNemar test | Ablation | Có - được gọi bởi _compare.py |
| ablation/limits | package/evaluation/ablation/_limits.py | Limits cho ablation (bootstrap_resamples, confidence, seed) | Ablation | Có - được dùng bởi _compare.py |

### A.2. Scripts chạy evaluation

| Script | Đường dẫn | Chạy cái gì | Có entrypoint CLI không? |
|--------|-----------|-------------|-------------------------|
| run_agent_eval | scripts/evaluation/run_agent_eval.py | Chạy agent evaluation end-to-end trên nhiều agents/kinds/segments | Có - CLI với --agents, --inference-mode, --request-scope, --metadata-policy, --no-prebuilt, --trajectory-file |
| candidate_recall | scripts/evaluation/candidate_recall.py | Chạy candidate retrieval evaluation | Có - CLI với --tag, --eval-on, --seed, --per-segment, --query-modes, --metadata-policy, --no-prebuilt-corpus |
| ranking_eval | scripts/evaluation/ranking_eval.py | Chạy ranking evaluation với streaming runner | Có - CLI với --tag, --eval-on, --seed, --per-segment, --popularity-weights, --metadata-policy, --no-prebuilt-corpus |
| run_baselines | scripts/evaluation/run_baselines.py | Chạy baseline models evaluation | Có - CLI (xem file để biết chi tiết) |
| tune_baselines | scripts/evaluation/tune_baselines.py | Tune baseline models | Có - CLI (xem file để biết chi tiết) |
| analyze_ranking_bottlenecks | scripts/evaluation/analyze_ranking_bottlenecks.py | Phân tích ranking bottlenecks | Có - CLI |
| benchmark_categories_any | scripts/evaluation/benchmark_categories_any.py | Benchmark categories_any filter | Có - CLI |
| evaluate_product_reply | scripts/evaluation/evaluate_product_reply.py | Evaluate product reply với LLM judge | Có - CLI |
| evaluate_with_jev | scripts/evaluation/evaluate_with_jev.py | Evaluate với JEV judge | Có - CLI |
| compare_experiments | scripts/experiments/compare_experiments.py | So sánh 2 experiments | Có - CLI |

### A.3. Unit tests cho từng component

| Component | Đường dẫn test | Đo gì | Có benchmark độc lập không? |
|-----------|---------------|-------|---------------------------|
| Memory | tests/agents/test_memory_tool.py | MemoryTool với large histories, unknown user, zero interactions, null prices, plan reference compatibility | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Planner/Executor | tests/agents/test_plan_executor.py | PlanExecutor: retry on bad JSON, max_steps cut, invented-id guard, reference chaining, ask_user, step logging, tool documentation | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Reflection | tests/agents/test_reflection_behavior.py | Reflection behavior: empty plan trigger, failed step trigger, no reflect with invented_ids, time budget error, reflect rounds limit, bad reflect reply, usage accumulation | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Inference/Grounding | tests/agents/inference/test_compose.py | compose_answer: status routing, LLM path with grounding + retry, template fallback, usage, modes, number checking, grounding checks | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Inference/Adapters | tests/agents/inference/test_adapters.py | Inference adapters | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Inference/Limits | tests/agents/inference/test_limits.py | Inference limits | **Một phần** - có unit test nhưng **không có benchmark dataset cố định** |
| Runtime/End-to-end | tests/agents/test_end_to_end.py | End-to-end agent scenarios | **Một phần** - có integration test nhưng **không có benchmark dataset cố định** |
| Runtime/Phase1 smoke | tests/agents/test_phase1_smoke.py | Phase 1 smoke test | **Một phần** - có smoke test nhưng **không có benchmark dataset cố định** |

### A.4. Đánh giá component benchmark độc lập

| Component | Đã có component benchmark độc lập chưa? | Bằng chứng (đường dẫn file) |
|-----------|----------------------------------------|---------------------------|
| Memory | **Chưa** | Không có file benchmark chuyên biệt cho MemoryTool. Chỉ có unit test tests/agents/test_memory_tool.py |
| Planner | **Chưa** | Không có file benchmark chuyên biệt cho Planner. Chỉ có unit test tests/agents/test_plan_executor.py |
| Executor (PlanExecutor) | **Chưa** | Không có file benchmark chuyên biệt cho PlanExecutor. Chỉ có unit test tests/agents/test_plan_executor.py |
| Reflection | **Chưa** | Không có file benchmark chuyên biệt cho Reflection. Chỉ có unit test tests/agents/test_reflection_behavior.py |
| Inference | **Chưa** | Không có file benchmark chuyên biệt cho Inference. Chỉ có unit test tests/agents/inference/test_compose.py, test_adapters.py |
| Grounding | **Chưa** | Không có file benchmark chuyên biệt cho Grounding. Chỉ có unit test trong test_compose.py |
| Runtime (Agent workflow) | **Một phần** | Có test_end_to_end.py nhưng không có benchmark dataset cố định với oracle |
| Plan building | **Một phần** | Có test_plan_building.py nhưng không có benchmark dataset cố định với oracle |

### A.5. Baseline test suite

#### Command chạy
```bash
cd src
python -m pytest -q --tb=short
```

#### Kết quả baseline (2026-10-27)
- **Total tests**: 1174 tests
- **Passed**: 1161
- **Failed**: 9
- **Skipped**: 2
- **Xfailed**: 2
- **Warnings**: 13 (SparseEfficiencyWarnings từ scipy)
- **Thời gian**: 36.94 giây

#### Lỗi chi tiết

1. **test_data_paths_layout_is_under_resource** (tests/config/test_data_paths.py)
   - Lỗi: Assertion fail về path layout
   - Nguyên nhân: config paths không match với expected structure

2. **test_config_cli_resolves_paths_from_datapaths_for_shell_scripts** (tests/config/test_data_paths.py)
   - Lỗi: Assertion fail về path resolution
   - Nguyên nhân: config paths không match với expected structure

3. **test_every_public_module_has_one_public_symbol_named_after_the_file** (tests/config/test_package_layout.py)
   - Lỗi: 8 files có public symbol không match filename
   - Files vi phạm:
     - package/evaluation/jev_product_evaluator.py
     - package/evaluation/layer1_outcome/layer1_outcome.py
     - package/evaluation/layer2_interaction/layer2_interaction.py
     - package/evaluation/layer3_grounding/layer3_grounding.py
     - package/evaluation/layer4_process/layer4_process.py
     - package/evaluation/layer5_deployment/layer5_deployment.py
     - package/evaluation/product_reply_evaluator.py

4. **test_no_module_imports_a_private_module_of_another_folder** (tests/config/test_package_layout.py)
   - Lỗi: 6 files import private module của folder khác
   - Files vi phạm:
     - package/evaluation/build_run_provenance.py
     - package/evaluation/layer5_deployment/layer5_deployment.py
     - scripts/evaluation/run_agent_eval.py

5. **test_comparison_rejects_policy_and_protocol_mixing** (tests/evaluation/ablation/test_loader.py)
   - Lỗi: Assertion fail về metadata_policy mixing
   - Nguyên nhân: test không reject như mong đợi

6. **test_behavior_snapshot_matches_existing** (tests/evaluation/agent/test_behavior_snapshot.py)
   - Lỗi: Row keys mismatch
   - Nguyên nhân: schema thay đổi, snapshot không sync

7. **test_run_planner_adds_the_answer_without_touching_the_recommendation_or_planner_usage** (tests/evaluation/agent/test_eval_integration.py)
   - Lỗi: AttributeError: 'ScriptedLLM' object has no attribute 'replies'
   - Nguyên nhân: test fixture thay đổi, code không update

8. **test_end_to_end_scenario[llm]** (tests/evaluation/agent/test_eval_integration.py)
   - Lỗi: AttributeError: 'ScriptedLLM' object has no attribute 'replies'
   - Nguyên nhân: test fixture thay đổi, code không update

9. **test_importing_package_does_not_load_subpackages** (tests/test_package_import.py)
   - Lỗi: subprocess returncode != 0
   - Nguyên nhân: package import loading subpackages

#### Lỗi môi trường
- Không có lỗi môi trường nghiêm trọng. Test suite chạy thành công phần lớn.

### A.6. Kết luận kiểm kê

**Đã có**:
- Evaluators end-to-end (layer1→layer5) với schema rõ ràng
- Unit tests cho Memory, Planner, Executor, Reflection, Inference, Grounding
- Scripts chạy evaluation end-to-end (run_agent_eval.py, candidate_recall.py, ranking_eval.py)
- Diagnostics tools (error_taxonomy, failure_rates, reflection_diagnostics)
- Ablation framework (_compare, _loader, _report, _statistics)

**Thiếu**:
- **Không có component benchmark độc lập** với dataset/fixture cố định cho từng component
- Không có oracle/tiêu chí chấm rõ cho từng component riêng lẻ
- Không có negative/failure cases chuyên biệt cho từng component
- Không có cost & latency tracking riêng cho từng component
- Không có regression framework cho component-level
- Không có interface evaluator chung có thể tái sử dụng cho mọi component

**Lưu ý**:
- 9 test failures hiện tại chủ yếu là config/layout issues và test fixture issues, không ảnh hưởng đến core logic
- Các layer evaluators (layer1→layer5) đang hoạt động tốt, được test rộng rãi
- Diagnostics và ablation framework đã khá hoàn thiện cho end-to-end evaluation
- Component-level evaluation là mảnh ghép còn thiếu để hoàn thiện hệ thống evaluation

## Phần B: Khung benchmark chung (để implement)

### B.1. Vị trí khung benchmark component
- Đặt trong: `src/package/evaluation/component/`
- Lý do:
  - Giữ cùng namespace với các evaluators hiện có (layer1→layer5, diagnostics, ablation)
  - Dễ discover và maintain
  - Có thể tái sử dụng các utilities hiện có (schema, helpers)

### B.2. Schema dataset/fixture (để thiết kế)
- `case_id`: str - unique identifier cho test case
- `input`: dict - input cho component (user_id, request, interactions, etc.)
- `expected/oracle`: dict - output mong đợi hoặc oracle để chấm điểm
- `tags`: list[str] - tags như normal/hard/ambiguous/negative/oracle
- `metadata`: dict - metadata bổ sung (description, difficulty, etc.)

### B.3. Interface evaluator chung (để implement)
- `load_cases(dataset_path) -> list[BenchmarkCase]` - load test cases từ file
- `run_component(component, case) -> ComponentResult` - chạy component với 1 case
- `score_component(actual, expected) -> dict[str, float]` - chấm điểm 1 case
- `aggregate_results(results: list[dict]) -> dict[str, Any]` - aggregate theo tag

### B.4. Schema kết quả JSON (để thiết kế)
```json
{
  "benchmark_version": str,
  "component": str,
  "config": dict,
  "prompt_schema_hash": str | null,
  "run_count": int,
  "per_case_results": list[dict],
  "metrics": dict[str, float],
  "latency": dict[str, float],
  "token_cost": dict[str, float] | null,
  "timestamp": str,
  "git_sha": str
}
```

### B.5. Runner CLI (để implement)
- `python -m package.evaluation.component.run --component <name> --dataset <path> --runs <n> --output <path>`
- Hỗ trợ chạy lặp N lần
- Tự động lưu kết quả JSON

### B.6. Regression report (để implement)
- `python -m package.evaluation.component.regress --baseline <path> --current <path> --output <path>`
- So sánh metrics theo tag
- Nêu metric nào tăng/giảm

### B.7. Benchmark mẫu (dummy) (để implement)
- 1 component đơn giản (ví dụ: MemoryTool)
- 3-5 test cases
- Chạy được end-to-end

### B.8. Unit test cho khung (để implement)
- test_runner.py - test runner CLI
- test_loader.py - test dataset loader
- test_regression.py - test regression diff

## Phần C: Giả định và phát hiện

### Giả định
1. Component benchmark sẽ **không thay thế** end-to-end evaluation, chỉ **bổ sung**
2. Dataset/fixture sẽ được lưu dưới dạng JSON hoặc JSONL để dễ version control
3. Oracle data sẽ được tạo từ held-out target hoặc hand-crafted cho negative cases
4. Khung benchmark sẽ **không phụ thuộc** vào component cụ thể, chỉ define interface chung
5. Benchmark sẽ chạy trên synthetic hoặc held-out data, không cần production data

### Phát hiện chưa được nối pipeline
1. **Không có script chạy component benchmark** - cần implement CLI runner
2. **Không có CI integration** cho component benchmark - cần thêm vào CI pipeline
3. **Không có experiment tracking** cho component benchmark - cần integrate với existing experiment framework
4. **Test failures hiện tại** (9 tests) nên được fix trước khi implement khung mới để tránh noise
5. **Package layout violations** (public symbol naming, cross-folder imports) nên được fix để maintain code quality

### Rủi ro
1. Component benchmark có thể gây duplication với existing unit tests nếu không thiết kế cẩn thận
2. Oracle data có thể khó maintain nếu không có quy trình clear
3. Regression framework có thể phức tạp nếu không giới hạn scope
4. CLI runner có thể conflict với existing scripts nếu không thiết kế rõ ràng

### Tiếp theo
Implement khung benchmark component theo Phần B, bắt đầu với B.1 (schema dataset/fixture) và B.2 (interface evaluator chung).
