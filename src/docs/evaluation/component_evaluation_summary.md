# Component Evaluation Summary Report

**Date**: 2026-10-27
**Repository**: Agentic RAG for RCM System
**Framework**: Component-level evaluation framework (Giai đoạn 0)

## Overview

Báo cáo tổng hợp kết quả evaluation cho các component từ Phase 0 đến Phase 4.

## Phase 0: Framework

**Status**: ✅ Done

**Deliverables**:
- Component benchmark framework: `package/evaluation/component/`
  - Schema: `_schema.py` (BenchmarkCase, BenchmarkResult, BenchmarkSummary, RegressionReport)
  - Loader: `_loader.py` (JSON/JSONL, tag/metadata filters)
  - Evaluator: `_evaluator.py` (ComponentEvaluator base class)
  - Regression: `_regression.py` (compare_benchmarks, format_regression_report)
  - CLI Runner: `run.py` (--component, --dataset, --runs, --tags, --config)
- Unit tests: 19/19 passed
- Documentation: README.md, PR_DESCRIPTION_PHASE0.md

**Baseline test**: 1161 passed, 9 failed, 2 skipped (36.94s)

## Phase 1: Memory

**Status**: ✅ Done

### Phần A: Correctness

**Dataset**: 16 test cases
- User không tồn tại, empty history, short/long history
- as_of_timestamp (before, at, mid, after) với snapshot_mode
- Tie-break, NULL prices, equal prices, outlier prices
- Duplicate items semantics
- Leakage guard

**Results**:
- 16/16 cases pass (100%)
- All fields match: 100%
- Error behavior correct: 100%
- Future leakage: 0%
- Mean latency: 0.0010s

**Oracle**: `memory_oracle.py` (logic độc lập)

### Phần B: Utility

**Experiment**: exp_002, exp_003, exp_004 (3 runs per condition)

**Results**:
- TẤT CẢ verdict = inconclusive
- Cỡ mẫu: 20 requests (ORACLE: 6, realistic: 14)
- Warnings: n < 20: too few pairs

**Kết luận**: Không thể kết luận memory có cải thiện hay không do cỡ mẫu quá nhỏ.

## Phase 2: Planner

**Status**: ✅ Done (with LLM thật)

**Dataset**: 4 test cases
- normal, hard, ambiguous, must-not-guess

**Mock implementation**: 4/4 cases, latency 0.0001s

**LLM thật** (gpt-5.4 via xah.io):
- tool_selection_accuracy: 0.750 (3/4)
- argument_correctness: 0.425
- plan_validity: 1.000
- reference_correctness: 0.750
- constraint_handling: 0.750
- clarification_precision: 0.500
- clarification_recall: 0.750
- refusal_to_guess: 0.750
- Mean latency: 5.4s

**Issues phát hiện**:
- planner_002 (hard): LLM không dùng $1.candidates reference → dùng categories_any thay thế
- planner_003 (ambiguous): LLM không hỏi clarification → trả về empty plan

## Phase 3: Executor & Reflection

**Status**: ⚸️ Partial

### Phần A: PlanExecutor

**Dataset**: 5 test cases
- normal, reference, error, empty, reference_error

**Results**:
- Success rate: 100% (5/5)
- all_steps_ok: 0.600 (3/5)
- reflection_triggered: 0.400 (2/5)
- Mean latency: 0.0001s

### Phần B: Reflection

**Metrics**:
- reflection_triggered: 40% (2/5)
- reflection_rescued: 0% (mock LLM hạn chế)
- reflection_no_change: 100%

**Hạn chế**:
- Mock LLM không tạo corrected plan → reflection chỉ retry same plan
- Tool config bug → không test được fail/empty cases
- Cần LLM thật để test reflection contribution thật

## Phase 4: Grounding

**Status**: ⚸️ Partial

**Dataset**: 5 test cases
- grounded-normal: 2 cases
- hallucination-bait: 1 case
- conflicting-evidence: 1 case
- prompt-injection: 1 case

**Rule-based results**:
- grounding_rate: 0.800 (4/5)
- hallucination_rate: 0.200 (1/5)
- prompt_injection_detected: 0.200 (1/5)
- Mean latency: 0.0000s

**Jev LLM-as-judge**:
- Cần Typesafe API key (OpenRouter key không hoạt động với TypeSafe API)
- 401 Unauthorized khi test

**Hạn chế**:
- Rule-based only (chưa có LLM-as-judge hoạt động)
- Chưa có judge calibration
- Chưa test real inference component

## Tổng quan

| Phase | Component | Status | Đã test | Còn thiếu |
|-------|-----------|--------|---------|-----------|
| 0 | Framework | ✅ Done | 19 tests | - |
| 1 | Memory | ✅ Done | 16 cases correctness, 3 runs utility | Utility cỡ mẫu lớn hơn |
| 2 | Planner | ✅ Done | 4 cases (mock + LLM thật) | Sample size lớn hơn |
| 3 | Executor+Reflection | ⚸️ Partial | 5 cases (mock) | LLM thật cho reflection |
| 4 | Grounding | ⚸️ Partial | 5 cases (rule-based) | Jev LLM-judge, real inference |

## Files đã tạo

**Framework**:
- `package/evaluation/component/_schema.py`
- `package/evaluation/component/_loader.py`
- `package/evaluation/component/_evaluator.py`
- `package/evaluation/component/_regression.py`
- `package/evaluation/component/run.py`

**Memory**:
- `benchmarks/memory_correctness_dataset.jsonl`
- `benchmarks/memory_correctness_evaluator.py`
- `benchmarks/memory_oracle.py`
- `benchmarks/memory_utility.py`

**Planner**:
- `benchmarks/planner_benchmark.py`
- `benchmarks/planner_mock_tools.py`
- `benchmarks/planner_mock_llm.py`
- `benchmarks/planner_dataset.jsonl`

**Executor**:
- `benchmarks/executor_mock_tools.py`
- `benchmarks/executor_dataset.jsonl`
- `benchmarks/executor_benchmark.py`

**Grounding**:
- `benchmarks/grounding_dataset.jsonl`
- `benchmarks/grounding_benchmark.py`

**Reports**:
- `docs/evaluation/inventory.md`
- `docs/evaluation/memory_evaluation_phase1.md`
- `docs/evaluation/planner_evaluation_phase2.md`
- `docs/evaluation/executor_reflection_phase3.md`
- `docs/evaluation/grounding_evaluation_phase4.md`

## Kết luận

Framework evaluation đã được thiết lập và hoạt động cho tất cả component:
- Memory: Correctness 100%, Utility cần cỡ mẫu lớn hơn
- Planner: LLM thật hoạt động, cần sample size lớn hơn
- Executor: Framework OK, cần LLM thật cho reflection
- Grounding: Rule-based OK, cần Jev LLM-judge với Typesafe API key

**Next steps**:
1. Tăng sample size cho Planner
2. Test Executor reflection với LLM thật
3. Lấy Typesafe API key cho Jev
4. Test real inference component
5. Tạo Runtime evaluation
