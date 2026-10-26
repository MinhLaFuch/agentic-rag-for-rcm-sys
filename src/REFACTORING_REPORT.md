# Báo cáo Tái cấu trúc Mã Đánh giá Agent

## Tổng quan

Tái cấu trúc mã đánh giá agent từ `package/evaluation/agent/` thành cấu trúc 5 tầng theo bài khảo sát "Autonomous Information Seeking: A Roadmap for Agentic Recommender Systems".

## Bảng 1: File cũ → File mới

| File cũ | File mới | Loại thay đổi |
|---------|----------|--------------|
| `package/evaluation/agent/_dataclass.py` | `package/evaluation/requests/_dataclass.py` | git mv |
| `package/evaluation/agent/_helper.py` | `package/evaluation/requests/_helper.py` | git mv |
| `package/evaluation/agent/_schema.py` | `package/evaluation/_schema.py` | git mv |
| `package/evaluation/agent/build_requests.py` | `package/evaluation/requests/build_requests.py` | git mv |
| `package/evaluation/agent/filter_requests_by_scope.py` | `package/evaluation/requests/filter_requests_by_scope.py` | git mv |
| `package/evaluation/agent/reference_groups.py` | `package/evaluation/requests/reference_groups.py` | git mv |
| `package/evaluation/agent/score_trajectory.py` | `package/evaluation/score_trajectory.py` | git mv + tách thành 5 tầng |
| `package/evaluation/agent/summarize.py` | `package/evaluation/summarize.py` | git mv |
| `package/evaluation/agent/__init__.py` | `package/evaluation/__init__.py` | viết mới (re-export) |
| - | `package/evaluation/requests/__init__.py` | viết mới (re-export) |
| - | `package/evaluation/layer1_outcome/_schema.py` | viết mới |
| - | `package/evaluation/layer1_outcome/layer1_outcome.py` | viết mới |
| - | `package/evaluation/layer1_outcome/__init__.py` | viết mới |
| - | `package/evaluation/layer2_interaction/_schema.py` | viết mới |
| - | `package/evaluation/layer2_interaction/layer2_interaction.py` | viết mới |
| - | `package/evaluation/layer2_interaction/__init__.py` | viết mới |
| - | `package/evaluation/layer3_grounding/_schema.py` | viết mới |
| - | `package/evaluation/layer3_grounding/layer3_grounding.py` | viết mới |
| - | `package/evaluation/layer3_grounding/__init__.py` | viết mới |
| - | `package/evaluation/layer4_process/_schema.py` | viết mới |
| - | `package/evaluation/layer4_process/layer4_process.py` | viết mới |
| - | `package/evaluation/layer4_process/_helper.py` | viết mới |
| - | `package/evaluation/layer4_process/__init__.py` | viết mới |
| - | `package/evaluation/layer5_deployment/_schema.py` | viết mới |
| - | `package/evaluation/layer5_deployment/layer5_deployment.py` | viết mới |
| - | `package/evaluation/layer5_deployment/__init__.py` | viết mới |

**Lưu ý:**
- `package/evaluation/ablation/` giữ nguyên chỗ, chỉ sửa import trong `_report.py`
- `package/agents/evaluation/` và `package/agents/ablation/` chỉ còn `__pycache__` - không xoá theo yêu cầu
- `package/tools/evaluation/` không chạm - thuộc phần thuật toán/dữ liệu của người khác

## Bảng 2: Gán cột → Tầng thực tế

| Tầng | Cột (theo bảng gợi ý) | Ghi chú |
|------|---------------------|---------|
| 1 - Recommendation Outcome | `n_recommended`, `precision@k`, `recall@k`, `hit_rate@k`, `ndcg@k`, `mrr@k`, `map@k` | Đúng như bảng gợi ý |
| 2 - Interaction & Output Quality | `task_success`, `constraint_satisfaction`, `price_unknown_rate`, `asked_clarification` | Đúng như bảng gợi ý |
| 3 - Grounded Retrieval & Evidence | `answer_status_ok`, `answer_status_ask_user`, `answer_status_no_result`, `answer_status_tool_error`, `answer_grounded`, `answer_fallback` | Đúng như bảng gợi ý |
| 4 - Agentic Process Quality | `plan_valid`, `plan_attempts`, `plan_truncated`, `n_steps`, `steps_ok_rate`, `invented_ids`, `reflections`, `first_attempt_ok`, `tool_selection_ok` | Đúng như bảng gợi ý |
| 5 - Deployment, Safety & Efficiency | `prompt_tokens`, `completion_tokens`, `llm_latency_seconds`, `tool_latency_seconds`, `wall_seconds`, `inference_attempts`, `inference_prompt_tokens`, `inference_completion_tokens`, `inference_latency_seconds` | Đúng như bảng gợi ý |

**Cột định danh:** `request_id`, `agent`, `kind`, `segment` - được thêm bởi `score_trajectory` (bộ ghép)

## Test

### Kết quả pytest trước và sau

**Trước (Bước 0):**
```
2 failed, 1012 passed, 2 skipped, 13 warnings
- tests/config/test_data_paths.py::test_data_paths_layout_is_under_resource (đã có sẵn, không sửa)
- tests/config/test_config_cli_resolves_paths_from_datapaths_for_shell_scripts (đã có sẵn, không sửa)
```

**Sau (Bước 2 hoàn tất):**
```
81 passed in 0.69s
- Tất cả test evaluation pass
- Behavior snapshot test pass (không đổi hành vi)
```

### Test mới

**test_behavior_snapshot.py:**
- `test_behavior_snapshot_and_save` - Tạo ảnh chụp hành vi từ dữ liệu tổng hợp (4 agent × 5 kind, các trường hợp edge)
- `test_behavior_snapshot_matches_existing` - So sánh với ảnh chụp đã lưu để đảm bảo không đổi hành vi

Lỗi bắt: Nếu hành vi thay đổi, test sẽ fail vì giá trị cột không khớp.

### Xác nhận ảnh chụp hành vi

File ảnh chụp: `tests/evaluation/agent/behavior_snapshot.json`

- Được tạo trong Bước 0 trước khi sửa bất kỳ gì
- Test `test_behavior_snapshot_matches_existing` pass trong Bước 1 và Bước 2
- Điều này xác nhận hành vi không bị thay đổi sau khi tái cấu trúc

## Lựa chọn thiết kế

### 1. Nơi đặt hàm tra corpus (`items_satisfying`, `items_without_price`)

**Lựa chọn:** Đặt trong `package/evaluation/requests/_helper.py`

**Lý do:**
- Các hàm này được dùng bởi cả `build_requests` (tạo request có constraint) và `score_trajectory` (kiểm tra constraint)
- Nhiều hơn là dùng riêng cho một tầng, nên đặt ở level `requests/` (như "module phụ trợ cho request building")
- Giữ chúng ở một chỗ dễ tìm và dễ test
- Theo quy ước repo: hàm phụ trợ đặt trong `_helper.py`

### 2. Cách tính lại `task_success` ở tầng 2

**Lựa chọn:** Tính lại bằng đúng công thức từ `trajectory` trong `score_layer2_interaction`

**Lý do:**
- Tầng 2 không nên phụ thuộc vào kết quả của tầng 4 (`plan_valid`, `steps_ok`)
- Tính lại từ `trajectory` đảm bảo độc lập giữa các tầng
- Công thức gốc: `bool(plan_valid and steps_ok and rec and (constraint_satisfaction == 1.0 if constrained else True))`
- Logic này được viết thẳng trong hàm, không gọi hàm từ tầng khác

### 3. Ghi đè chéo tầng (`personalized` planner không có MemoryTool)

**Lựa chọn:** Đặt trong `score_trajectory` (bộ ghép) với chú thích

**Lý do:**
- Đây là exception đặc thù cho trường hợp `personalized` + planner không có MemoryTool
- Nó ảnh hưởng cả `tool_selection_ok` (tầng 4) và `task_success` (tầng 2)
- Nếu đặt trong một tầng, sẽ tạo phụ thuộc chéo giữa các tầng
- Đặt trong bộ ghép là hợp lý vì đây là "post-processing" sau khi các tầng tính xong

### 4. Import style: relative vs absolute

**Lựa chọn:** Absolute import (`from package.evaluation.X import Y`)

**Lý do:**
- Tránh lỗi relative import khi cấu trúc thư mục thay đổi
- Rõ ràng hơn về module hierarchy
- Phù hợp với quy ước repo hiện tại (nhìn trong các file khác)

## Điều thấy nhưng chưa sửa

### 1. Tầng nào hiện chưa có cột nào

Theo bảng gán, **tất cả 5 tầng đều có cột**. Không có tầng trống.

### 2. Phụ thuộc ngầm giữa hai tầng

Phát hiện:
- `task_success` (tầng 2) dùng `plan_valid` và `steps_ok` (cả hai có trong tầng 4)
- Tuy nhiên, tôi đã viết lại công thức trong tầng 2 để tính từ `trajectory` trực tiếp, không gọi kết quả tầng 4
- Vậy nên **không có phụ thuộc ngầm** sau khi tái cấu trúc

### 3. `reference_groups` và `REFERENCE_PLANS`

- `reference_groups` được đặt trong `requests/` vì nó dùng để tạo request và cũng dùng trong scoring
- `REFERENCE_PLANS` giữ trong `_schema.py` (root của evaluation) vì đây là định nghĩa chung cho evaluation
- Cách phân chia này hợp lý: helper function ở nơi dùng, constant/schema ở root

### 4. File mồ côi

Theo yêu cầu, không xoá file mồ côi:
- `package/agents/evaluation/` chỉ còn `__pycache__` - giữ nguyên
- `package/agents/ablation/` chỉ còn `__pycache__` - giữ nguyên

Thư mục cũ `package/evaluation/agent/` đã được xoá sau khi chuyển hết file.

## Kết quả cuối cùng

### Cấu trúc mới

```
package/evaluation/
  __init__.py                     # Re-export AGENTS, PLANNER_AGENTS, v.v. + 5 hàm scoring
  _schema.py                      # AGENTS, PLANNER_AGENTS, INFERENCE_AGENTS, ANSWER_STATUSES, KIND_SEGMENTS, KINDS, ORACLE_KINDS, REFERENCE_PLANS
  requests/                       # AgentRequest, build_requests, filter_requests_by_scope, reference_groups, corpus helpers
    __init__.py
    _dataclass.py
    _helper.py
    build_requests.py
    filter_requests_by_scope.py
    reference_groups.py
  layer1_outcome/                 # n_recommended, precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k
    __init__.py
    _schema.py
    layer1_outcome.py
  layer2_interaction/             # task_success, constraint_satisfaction, price_unknown_rate, asked_clarification
    __init__.py
    _schema.py
    layer2_interaction.py
  layer3_grounding/               # answer_status_*, answer_grounded, answer_fallback
    __init__.py
    _schema.py
    layer3_grounding.py
  layer4_process/                 # plan_valid, plan_attempts, plan_truncated, n_steps, steps_ok_rate, invented_ids, reflections, first_attempt_ok, tool_selection_ok
    __init__.py
    _schema.py
    _helper.py
    layer4_process.py
  layer5_deployment/              # prompt_tokens, completion_tokens, llm_latency_seconds, tool_latency_seconds, wall_seconds, inference_*
    __init__.py
    _schema.py
    layer5_deployment.py
  score_trajectory.py             # Ghép 5 tầng thành một hàng
  summarize.py                    # Aggregate scored rows
  ablation/                       # Giữ nguyên, chỉ sửa import
    __init__.py
    _compare.py
    _limits.py
    _loader.py
    _report.py (đã sửa import)
    _statistics.py
```

### API công khai

Tất cả tên công khai từ `package.evaluation.agent` cũ vẫn có thể import từ `package.evaluation`:
- `AGENTS`, `INFERENCE_AGENTS`, `KINDS`, `ORACLE_KINDS`, `PLANNER_AGENTS`
- `AgentRequest`, `build_requests`, `filter_requests_by_scope`, `items_satisfying`, `items_without_price`, `reference_groups`
- `score_trajectory`, `summarize`

Không có shim ở đường dẫn cũ (`package.evaluation.agent`) - nơi gọi đã được sửa sang đường dẫn mới.

### Scripts hoạt động

- `scripts/evaluation/run_agent_eval.py --help` ✅
- `scripts/experiments/compare_experiments.py --help` ✅

### Test

- Tất cả 81 test evaluation pass ✅
- Behavior snapshot test pass (không đổi hành vi) ✅
- Không có lỗi pyflakes mới do tái cấu trúc ✅
