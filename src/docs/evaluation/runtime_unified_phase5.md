# Runtime Metrics and Unified Report - Phase 5 Report

**Date**: 2026-10-27
**Component**: Runtime/API + Unified Reporting

## Phần A: Runtime Metrics

### Latency Tracking

Latency đã được track qua tất cả component benchmarks:

| Component | Mean Latency | P95 Latency | Notes |
|-----------|--------------|-------------|-------|
| Memory | 0.0000s | 0.0000s | Synthetic data, no external calls |
| Planner | 5.2371s | 8.5095s | LLM API calls (gpt-5.4 via xah.io) |
| Executor | 0.0001s | 0.0001s | Mock tools, no external calls |
| Grounding | 0.0000s | 0.0000s | Rule-based, no external calls |

### Token/Cost Tracking

- Planner: token usage được track qua LLM provider
- Các component khác: không có token usage (mock/rule-based)

### Timeout/Error/Retry

- Không có timeout trong các benchmark chạy
- Planner LLM: thành công (không retry cần thiết)
- Error rate: 0% (tất cả benchmark chạy thành công)

### Tính tái lập

- Git SHA được capture: `782814126d539bd22518e109ca90374ab844adaf`
- Benchmark version: `1.0.0`
- Config được lưu trong JSON results

## Phần B: Báo cáo hợp nhất

### Unified Report Script

**File**: `package/evaluation/component/run_all.py`

**Chạy tất cả benchmarks**:
```bash
cd src
python -m package.evaluation.component.run_all --runs 1 --output-dir benchmark_results
```

**Kết quả**:
- JSON report: `benchmark_results/unified_report_20261027_154306.json`
- Markdown report: `benchmark_results/unified_report_20261027_154306.md`

### Component Results

| Component | Status | Cases | Success Rate | Mean Latency | Mean Metric |
|-----------|--------|-------|-------------|-------------|-------------|
| Memory | ✅ Success | 16 | 100% | 0.0000s | 0.2375 |
| Planner | ✅ Success | 4 | 100% | 5.2371s | 0.6875 |
| Executor | ✅ Success | 5 | 100% | 0.0001s | 0.4000 |
| Grounding | ✅ Success | 5 | 100% | 0.0000s | 0.6000 |

### Weakest Component Analysis

- **Weakest component**: Memory (mean metric: 0.2375)
  - known_correct: 0.1875
  - n_interactions_correct: 0.1875
  - top_categories_match: 0.2500
  - price_range_correct: 0.3125
  - recent_items_match: 0.2500

### Quality vs Latency Trade-off

- Planner: Highest latency (5.2s) due to LLM calls, but decent quality (0.6875)
- Memory/Executor/Grounding: Near-zero latency (mock/rule-based), variable quality

## Regression Testing

### Regression Detection

Framework đã có `_regression.py` với:
- `compare_benchmarks()`: so sánh hai kết quả với thresholds
- `format_regression_report()`: human-readable report

### Regression Command

```bash
python -m package.evaluation.component.run regress \
  --baseline baseline.json \
  --current current.json \
  --text-report regression_report.txt
```

### Regression Test

Chạy lại benchmark lần 2 để test regression detection:
```bash
cd src
python -m package.evaluation.component.run_all --runs 1 --output-dir benchmark_results_v2
```

Sau đó so sánh hai kết quả.

## CI Integration

### Lightweight Mode (CI)

- Sử dụng mock LLM/mock tools để tránh API calls
- Chạy subset của datasets
- Cache results

### Full Mode (Manual)

- Sử dụng LLM thật
- Chạy toàn bộ datasets
- Generate full reports

## Deliverables

1. ✅ `run_all.py`: Script chạy tất cả benchmarks
2. ✅ Unified JSON report
3. ✅ Unified Markdown report
4. ✅ Latency tracking (mean, P95)
5. ✅ Git SHA capture
6. ✅ Component comparison

## Kết luận

Phase 5 đã hoàn thành:
- Runtime metrics được track qua tất cả benchmarks
- Unified report generator hoạt động
- Regression framework sẵn sàng
- Một lệnh chạy tất cả component benchmarks

**Files**:
- `package/evaluation/component/run_all.py`
- `benchmark_results/unified_report_*.json`
- `benchmark_results/unified_report_*.md`
