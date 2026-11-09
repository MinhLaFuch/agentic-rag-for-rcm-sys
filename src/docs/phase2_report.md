# Phase 2 Report — Ngưỡng PASS/FAIL (đề xuất) + khôi phục test bị skip

Ngày: 2026-11-09. Kế thừa Phase 1 (1341 passed / 8 skipped / 2 xfailed).

## 1. Kết quả pytest

```
PYTHONPATH=. python -m pytest tests/ -q
================ 1349 passed, 2 xfailed, 13 warnings in 45.83s ================
```

**0 skipped** — cả 8 test skip đã được khôi phục và PASS. 2 xfailed giữ nguyên
(`test_parse_llm_reply_none_text`, `test_parse_llm_reply_empty_text` — chỉ liệt kê,
không sửa vì ngoài phạm vi).

## 2. Test đã khôi phục (2.2)

### SQL hardening — 4 test (`tests/sql/test_sql_hardening.py` ×3, `test_sql_filter_validation.py` ×1)

Nguyên nhân skip: fixture patch `package.config.load_config.load_config`, nhưng
`package/corpus/item_corpus.py:31` bind `load_config` vào module namespace lúc
import → patch không tới được; cộng thêm `_get_corpus_limits` là `lru_cache`.

Sửa: patch trực tiếp `item_corpus._get_corpus_limits` (trả `(max_rows, budget_nhỏ)`)
bằng `monkeypatch.setattr` — đúng chỗ cần test (cơ chế timeout), không cần refactor
config loader. `test_corpus_is_usable_after_a_timeout` dùng `monkeypatch.undo()`
giữa test để khôi phục budget thật. Cả 4 test PASS, gồm test bảo mật timeout
thực sự fire (`SLOW_CTE` recursive 1e8 dòng bị interrupt bởi progress handler).

### Memory leakage — 2 test (`tests/evaluation/component/test_memory_correctness.py`)

- `test_detector_catches_planted_leakage`: test gốc (commit `7828141`) dùng closure
  `FullFrame` nhận FULL frame bất chấp snapshot cut. Bản hiện tại chỉ truyền
  `as_of_timestamp=None` nhưng vẫn dùng df đã bị evaluator cắt → không leak được.
  Đã restore đúng cơ chế closure: tool luôn thấy full `inter` →
  `future_leakage_max == 1.0`, case `correctness_007` bị flag đúng.
- `test_committed_dataset_matches_oracle`: điều tra sâu phát hiện **3 vấn đề thật**:
  1. `_dataset_common.SPECS` stale so với dataset commit: thiếu 1 case boundary
     (`u_mixed_ratings`/`u_boundary_love`/`u_boundary_hate` thay vì 2 spec trùng
     `u_love_hate_mix`), sai tags `no_rating_col`→`no_rating_column`, thiếu
     `correctness_030`, lệch id ở đoạn cutoff/leakage_guard.
  2. `expected.loved_items` của case 024/025 **sai nội dung** so với fixture hiện
     tại (chạy thật cả 30 case: `loved_items_set_match=0.0` → all_fields_match=0).
     Dataset được regenerate bằng `render()` (chỉ 13 dòng đổi).
  3. **Nondeterminism thật**: `loved_items`/`hated_items` sort bằng
     `sorted(set(...), key=rating)` — khi >top_n item cùng rating ở biên,
     set-iteration order (hash seed) quyết định item nào bị cắt → kết quả đổi
     giữa các process. Đây là lỗi reproducibility (liên quan Task 3.1 audit).

  Sửa: thêm tie-break `item_id` vào sort key ở **cả hai phía** để deterministic:
  - `package/memory/memory_tool.py:155-162` (runtime)
  - `package/evaluation/component/benchmarks/compute_memory_oracle.py:150-157` (oracle)
    loved: `(-rating, item_id)`; hated: `(rating, item_id)` — thứ tự rating giữ
    nguyên, chỉ thêm tie-break.

  Sync test viết lại so sánh semantic (parse JSONL, normalize loved/hated items
  thành sorted) thay vì string equality — vẫn bắt được mọi drift về nội dung.

### stage4_integration — 2 test (`tests/data/pipeline/test_stage4_integration.py`)

Cả hai trước chỉ là stub `pytest.skip`. Đã implement thật:
- `test_stage4_eval_on_validation_creates_one_file`: fixture tối thiểu
  (mapped_dir + parquet splits qua `save_splits`) → `build_artifacts(eval_on=
  ["validation"], skip_corpus=True)` → chỉ file `item_knn_*_validation.npz` được
  tạo. mappings phải có nội dung thật vì `fit_provenance` kiểm tra
  `fit indices exceed mapping dimensions`.
- `test_stage4_skip_item_knn_skips_item_knn_building`: đối xứng test skip_corpus.

## 3.2 Đề xuất thiết kế thresholds (CHƯA code — chờ duyệt)

Vấn đề: `ComponentEvaluator.run_case` đặt `success=True` khi "chạy không ném lỗi",
không so ngưỡng chất lượng → integration `contract_valid_mean=0.6857` và grounding
`0.9062` vẫn in "Passed".

Đề xuất:
- `configs/eval/component_benchmarks.yaml`: thêm section `thresholds:` per component,
  ví dụ `integration: {contract_valid_mean: 0.8, no_mismatch_mean: 0.9}`,
  `grounding: {grounding_rate: 0.85, hallucination_rate_max: 0.1}`.
- `_evaluator.py`: sau khi aggregate metrics, tính `passed = success AND mọi metric
  trong thresholds đạt` (hỗ trợ hậu tố `_max` cho metric "càng thấp càng tốt").
- `BenchmarkSummary`/report: thêm field `pass` tách khỏi `success`; `_run_all.py`
  tổng chỉ gọi PASS khi cả hai đúng; per-case `success` giữ nguyên nghĩa.
- Metric nào không có trong thresholds → không chặn pass (opt-in), tránh phá
  benchmark chưa đặt ngưỡng.
- Test hồi quy: component với metric thấp hơn threshold → `pass=False` nhưng
  `success=True`; metric đạt → cả hai True.

Cần người dùng chốt: danh sách ngưỡng cụ thể cho từng component (hoặc để agent đề
xuất giá trị mặc định từ baseline hiện tại).

## 4. File đã đổi (Phase 2)

```
 package/evaluation/component/benchmarks/_dataset_common.py      | SPECS sync với dataset (30 case)
 package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl | regenerate (fix 024/025 + ordering)
 package/evaluation/component/benchmarks/compute_memory_oracle.py | deterministic tie-break loved/hated
 package/memory/memory_tool.py                                    | deterministic tie-break loved/hated
 tests/data/pipeline/test_stage4_integration.py                   | implement 2 test + helpers
 tests/evaluation/component/test_memory_correctness.py            | restore 2 test
 tests/sql/test_sql_filter_validation.py                          | unskip + fix fixture target
 tests/sql/test_sql_hardening.py                                  | unskip ×3 + fix fixture target
```

(Lưu ý: `memory_tool.py` là runtime code — thay đổi duy nhất là tie-break sort,
output giống hệt khi không có rating trùng ở biên; full suite 1349 pass xác nhận
không hồi quy.)

## 5. except Exception mới / fake mới trong vùng B

Không có. Không thêm mock/fake nào vào package/evaluation hay scripts.

## 6. Việc chưa làm

- 2.1 thresholds: chờ duyệt thiết kế + giá trị ngưỡng.
- 2 xfail `parse_llm_reply` (none_text/empty_text): chỉ liệt kê theo yêu cầu,
  không sửa (ngoài phạm vi phase).
- Phase 3+: chờ xác nhận.
