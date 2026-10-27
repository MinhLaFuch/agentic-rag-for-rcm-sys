# Memory Evaluation - Phase 1 Report

**Date**: 2026-10-27
**Component**: MemoryTool (package/memory/memory_tool.py)
**Framework**: Component-level evaluation framework (Giai đoạn 0)

## Phần A: Memory Correctness

### Oracle Calculator

Đã implement `memory_oracle.py` với logic độc lập từ MemoryTool:
- `compute_memory_oracle()`: Tính expected profile từ raw data
- `check_leakage()`: Kiểm tra future leakage với as_of_timestamp

### Dataset

**File**: `package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl`

**16 test cases**:

| Case ID | Type | Description | Result |
|---------|------|-------------|--------|
| correctness_001 | negative | User không tồn tại | ✅ Pass |
| correctness_002 | negative | User có 0 interactions | ✅ Pass |
| correctness_003 | normal | Short history (2 interactions) | ✅ Pass |
| correctness_004 | normal | Long history (10 interactions) | ✅ Pass |
| correctness_005 | cutoff | as_of before first event | ✅ Pass |
| correctness_006 | cutoff | as_of == first timestamp | ✅ Pass |
| correctness_007 | cutoff | as_of mid-history | ✅ Pass |
| correctness_008 | cutoff | as_of == last timestamp | ✅ Pass |
| correctness_009 | edge_case | Tie-break categories | ✅ Pass |
| correctness_010 | edge_case | NULL prices | ✅ Pass |
| correctness_011 | edge_case | Equal prices | ✅ Pass |
| correctness_012 | edge_case | Outlier price | ✅ Pass |
| correctness_013 | edge_case | Duplicate items semantics | ✅ Pass |
| correctness_014 | edge_case | top_n_exceeds_available | ✅ Pass |
| correctness_015 | leakage_guard | untruncated + as_of=4 → expect LeakageError | ✅ Pass |
| correctness_016 | leakage_guard | untruncated + as_of=9 (control) | ✅ Pass |

### Benchmark Results

**Command**:
```bash
python -m package.evaluation.component.run \
    --component memory_correctness \
    --dataset package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl \
    --runs 1 \
    --output memory_correctness_benchmark_v3.json
```

**Results**:
- **Success rate**: 100% (16/16 cases)
- **Mean latency**: 0.0010s
- **P95 latency**: 0.0020s
- **All fields match**: 100% (16/16 cases)
- **Error behavior correct**: 100%
- **Future leakage**: 0% (leakage guard hoạt động đúng)

**Metrics breakdown**:
- `known_correct`: 100%
- `n_interactions_correct`: 100%
- `top_categories_exact`: 100%
- `price_range_exact`: 100%
- `recent_items_exact`: 100%

### Danh sách Bug/Hành vi đáng ngờ

**Không phát hiện bug** - MemoryTool hoạt động đúng với tất cả 16 test cases.

## Phần B: Memory Utility

### Thiết kế thí nghiệm paired

**Design rules** (từ `memory_utility.py`):
- Paired: chỉ requests scored cho CẢ HAI conditions được so sánh
- Multi-run: mỗi request được trung bình qua runs per condition; CI là bootstrap qua REQUESTS
- ORACLE groups (cold_text, constrained) được phân tích TÁCH BIỆT với realistic groups
- Verdicts per group, conservative: "inconclusive" trừ khi n >= min_n, runs >= 2 và CI loại trừ 0

### Datasets

**Experiment dirs**: exp_002, exp_003, exp_004 (mỗi dir có cả planner và planner_memory)

**Kinds**: cold_text, constrained, similar, personalized, ambiguous

**Kích thước**:
- Tổng: 20 requests
- ORACLE: 6 requests (2 cold_text + 4 constrained)
- Realistic: 14 requests (4 similar + 4 personalized + 6 ambiguous)

### Benchmark Results

**Command**:
```bash
python package/evaluation/component/benchmarks/memory_utility.py \
    --dirs experiments/agent_eval/exp_002 experiments/agent_eval/exp_003 experiments/agent_eval/exp_004 \
    --baseline-agent planner --memory-agent planner_memory --k 10 \
    --out-dir experiments/agent_eval/memory_utility_analysis
```

**Configuration**:
- runs: baseline=3, memory=3
- bootstrap: 5000 x 0.95
- min_n: 20

**Key findings**:

#### Task Success

| Group | n_pairs | baseline | memory | diff [CI] | verdict |
|-------|---------|----------|--------|-----------|---------|
| oracle | 6 | 0.417 | 0.167 | -0.250 [-0.583, +0.000] | inconclusive |
| oracle/constrained | 4 | 0.625 | 0.250 | -0.375 [-0.750, +0.000] | inconclusive |
| realistic | 14 | 0.857 | 0.929 | +0.071 [+0.000, +0.214] | inconclusive |
| realistic/personalized | 4 | 0.500 | 0.750 | +0.250 [+0.000, +0.750] | inconclusive |

#### Cost/Latency

| Group | n_pairs | baseline tokens | memory tokens | diff [CI] | verdict |
|-------|---------|-----------------|---------------|-----------|---------|
| oracle | 6 | 159.8 | 168.3 | +8.5 [-14.2, +37.7] | inconclusive |
| realistic | 14 | 142.5 | 166.8 | +24.2 [-4.6, +59.5] | inconclusive |
| realistic/personalized | 4 | 282.9 | 359.9 | +77.0 [-9.5, +154.0] | inconclusive |

**Warnings**:
- `n=6 < 20: too few pairs for a reliable estimate` (oracle)
- `n=14 < 20: too few pairs for a reliable estimate` (realistic)
- `n=4 < 20: too few pairs for a reliable estimate` (subgroups)

**Verdict**: TẤT CẢ groups = **inconclusive** do cỡ mẫu quá nhỏ (n < 20).

### So sánh với Ablation cũ

**Ablation cũ** (`experiments/agent_eval/ablation/memory_vs_no_memory`):
- **Design**: 1 run per group (không multi-run)
- **Sample size**: 146 paired requests
- **Groups**: cold_text (20), constrained (40), similar (40)
- **Kết quả**:
  - cold_text: memory cải thiện task_success (+0.05), recall@10 (+0.15), ndcg@10 (+0.058)
  - constrained: không rõ ràng
  - similar: task_success giảm nhẹ (-0.025)

**Phân tích mới**:
- **Design**: 3 runs per condition, bootstrap CI
- **Sample size**: 20 requests (RẤT NHỎ)
- **Kết quả**: TẤT CẢ inconclusive

**Sự khác biệt chính**:
1. **Cỡ mẫu**: Ablation cũ 146 vs mới 20 → mới quá nhỏ để kết luận
2. **Multi-run**: Mới có 3 runs, cho phép đo run-to-run variance
3. **Groups**: Mới có thêm personalized và ambiguous
4. **ORACLE labeling**: Mới tách rõ oracle vs realistic trong report

**Hạn chế của phân tích mới**:
- Cỡ mẫu 20 << min_n=20 → không có verdict nào đáng tin
- Nhiều metrics (recall@10, ndcg@10) = 0 cho realistic groups → data không đủ

## Hạn chế

### Correctness Benchmark

1. **Cỡ mẫu nhỏ**: 16 cases synthetic, không đại diện cho production workload
2. **Không có case leakage thực tế từ production**: Chỉ test leakage guard với synthetic data

### Utility Experiment

1. **Cỡ mẫu quá nhỏ**: 20 requests << 146 của ablation cũ
2. **Tất cả verdict = inconclusive**: Không thể kết luận memory có cải thiện hay không
3. **Các realistic metrics = 0**: recall@10, ndcg@10 đều 0 cho realistic groups
4. **6 requests unscored**: ambiguous requests không có ground truth cho ranking metrics

## Kết luận

### Correctness

✅ **MemoryTool hoạt động đúng** với 16 test cases:
- User không tồn tại, empty history, short/long history
- as_of_timestamp (before, at, mid, after)
- Tie-break categories, NULL prices, equal prices, outlier prices
- Duplicate items semantics
- Leakage guard hoạt động đúng (raise LeakageError khi expected)

✅ **Không phát hiện bug** trong MemoryTool.

### Utility

⚠️ **Không thể kết luận** - Cỡ mẫu quá nhỏ (20 requests), tất cả verdict = inconclusive.

**So sánh với ablation cũ**:
- Ablation cũ (146 requests) cho thấy memory có thể cải thiện cold_text
- Phân tích mới (20 requests) không đủ sample để xác nhận
- Phân tích mới có lợi thế: multi-run, bootstrap CI, rõ ràng ORACLE vs realistic

**Recommendation**: Cần chạy experiment với cỡ mẫu lớn hơn (>= 100 requests) để có verdict đáng tin.

## Tiếp theo (Phase 2)

1. Rà lại các component khác (Planner, Executor, Reflection, Inference/Grounding)
2. Chạy utility experiment với cỡ mẫu lớn hơn
3. Fix leakage check nếu cần test as_of_timestamp tốt hơn
