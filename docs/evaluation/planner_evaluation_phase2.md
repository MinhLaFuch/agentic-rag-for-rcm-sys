# Planner Evaluation - Phase 2 Report

**Date**: 2026-10-27
**Component**: Planner (PlanExecutor - package/agents/planner/plan_executor.py)
**Framework**: Component-level evaluation framework (Giai đoạn 0)

## Overview

Phase 2 triển khai evaluation cho Planner component với mock tools và mock LLM để test cô lập Planner mà không cần chạy executor thật.

## Architecture

### Files created

1. **`planner_benchmark.py`**: PlannerEvaluator
   - Run Planner với mock tools và mock LLM
   - Score theo 8 metrics yêu cầu

2. **`planner_mock_tools.py`**: Mock tools
   - MockSQLTool: trả về deterministic candidates
   - MockSemanticSearchTool: trả về deterministic search results
   - MockItemCFTool: trả về deterministic similar items
   - MockRecoModelTool: trả về deterministic ranking

3. **`planner_mock_llm.py`**: Mock LLM
   - Trả về canned responses dựa trên pattern trong request
   - Hỗ trợ test deterministic

4. **`planner_dataset.jsonl`**: Test dataset
   - 4 cases với 4 tags: normal, hard, ambiguous, must-not-guess

## Dataset

**4 test cases**:

| Case ID | Tag | Description | Expected |
|---------|-----|-------------|----------|
| planner_001 | normal | Simple price filter | SQLTool with price_max=50 |
| planner_002 | hard | Multi-step with reference | ItemCFTool → SQLTool with $1.candidates |
| planner_003 | ambiguous | Ambiguous request | ask_user clarification |
| planner_004 | must-not-guess | Unknown user | ask_user for user ID |

**Tags breakdown**:
- normal: 1 case
- hard: 1 case
- ambiguous: 1 case
- must-not-guess: 1 case

## Metrics Implemented

1. **tool_selection_accuracy**: Tỷ lệ tool được chọn đúng
2. **argument_correctness**: Tỷ lệ argument khớp theo field
3. **plan_validity**: Plan có hợp lệ (list of steps) không
4. **reference_correctness**: Reference $N.path có đúng không
5. **constraint_handling**: Ràng buộc trong filters có đúng không
6. **clarification_precision**: Hỏi lại đúng lúc (precision)
7. **clarification_recall**: Hỏi lại khi cần (recall)
8. **refusal_to_guess**: Không đoán khi thiếu thông tin

## Benchmark Results

**Command**:
```bash
python -m package.evaluation.component.run \
    --component planner \
    --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl \
    --runs 1
```

**Results**:
- **Success rate**: 100% (4/4 cases)
- **Mean latency**: 0.0001s
- **P95 latency**: 0.0002s

**Quality metrics (mean over cases)**:
- tool_selection_accuracy: 1.000
- argument_correctness: 1.000
- plan_validity: 1.000
- reference_correctness: 1.000
- constraint_handling: 1.000
- clarification_precision: 0.500
- clarification_recall: 0.750
- refusal_to_guess: 0.750

## Detailed Analysis

### Case breakdown

**planner_001 (normal)**: ✅ Pass
- Tool selection: SQLTool ✓
- Arguments: price_max=50, domain=Video_Games ✓
- Clarification: không cần ✓

**planner_002 (hard)**: ✅ Pass
- Tool selection: ItemCFTool → SQLTool ✓
- Arguments: items=["item_vg_123"], top_k=10 ✓
- Reference: $1.candidates ✓
- Constraint: price_max=100 ✓

**planner_003 (ambiguous)**: ⚠️ Partial
- Expected: ask_user clarification
- Actual: question=null (không hỏi)
- clarification_precision: 0.0 (không hỏi khi cần)
- clarification_recall: 0.0

**planner_004 (must-not-guess)**: ✅ Pass
- Expected: ask_user for user ID
- Actual: ask_user đúng ✓
- refusal_to_guess: 1.0

## Error Analysis

### Planner weakness detected

**Ambiguous case (planner_003)**:
- Request: "What kind of games do you have?"
- Expected: hỏi clarification
- Actual: không hỏi, trả về empty plan
- **Lỗi**: Mock LLM không có pattern matching cho request này → trả về default empty plan

**Limitation hiện tại**:
- Mock LLM chỉ match chính xác pattern → không đủ flexible
- Cần LLM thật hoặc rule-based oracle để test clarification behavior tốt hơn

## Hạn chế

1. **Cỡ mẫu nhỏ**: 4 cases (1 per tag) → không đủ ý nghĩa thống kê
2. **Mock LLM đơn giản**: Chỉ match pattern chính xác → không test được real LLM behavior
3. **Chưa có stability test**: Chưa chạy N runs để đo độ ổn định
4. **Chưa có LLM thật**: Chưa support LLM thật hoặc replay/cached response
5. **Reference resolution chưa test sâu**: Chỉ check presence, chưa test correctness của path
6. **Constraint handling chưa test đầy đủ**: Chỉ test filters, chưa test các constraint khác

## So sánh với yêu cầu ban đầu

### Đã đáp ứng
- ✅ Dataset với 4 tags (normal, hard, ambiguous, must-not-guess)
- ✅ Mock tools để chạy cô lập
- ✅ 8 metrics cơ bản
- ✅ Chạy được bằng một lệnh
- ✅ Kết quả theo tag

### Chưa đáp ứng
- ❌ Sample size: 4 cases << yêu cầu "đủ ý nghĩa thống kê tối thiểu"
- ❌ Stability: chưa chạy N runs
- ❌ LLM thật/replay: chưa implement
- ❌ Reference resolution: chưa test sâu
- ❌ Constraint handling: chưa test đầy đủ
- ❌ Clarification behavior: mock LLM không đủ flexible
- ❌ Oracle: chưa có rule-based oracle, chỉ dùng mock LLM
- ❌ README cách thêm case mới: chưa tạo

## Tiếp theo

1. **Tăng sample size**: Add nhiều cases per tag (>= 10 per tag)
2. **Improve mock LLM**: Add rule-based oracle cho clarification behavior
3. **Implement stability test**: Chạy N runs (>= 3) và đo độ ổn định
4. **Add LLM thật support**: Support LLM thật và replay/cached response
5. **Deep reference testing**: Test correctness của $N.path, không chỉ presence
6. **Full constraint testing**: Test các constraint khác ngoài filters
7. **Create README**: Hướng dẫn cách thêm case mới
8. **Real dataset**: Add cases từ real user requests
