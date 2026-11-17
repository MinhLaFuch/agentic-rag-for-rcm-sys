# P0: kiểm chứng bundle trước embedding evaluation

Trạng thái: code chuẩn bị đã có; chưa chạy test hoặc audit dữ liệu trong lượt triển khai này theo yêu cầu người dùng. Gate 1 chưa được xác nhận đạt.

## Bundle selection

Các CLI `verify_tag.py`, `build_item_embeddings.py`, `candidate_recall.py` và `ranking_eval.py` hỗ trợ `--tag`. Bộ chọn dùng chung là `package.config.resolve_bundle_paths.resolve_bundle_paths`, giữ nguyên lựa chọn mặc định và không bỏ kiểm chứng.

Ví dụ tag ứng viên: `multi_domain_v2_audit_20261030`. Đây chưa phải quyết định chọn bundle cuối. Mặc định của ứng dụng vẫn là `multi_domain`. Runtime hiện có API `get_data_paths(tag=...)`; việc đưa cấu hình đã chốt vào agent/demo vẫn cần làm ở giai đoạn tích hợp runtime.

## Hai mức audit

`audit_bundle.py` không sửa data, config hoặc manifest. Nó chỉ ghi report JSON được chỉ định và, khi scan splits, tạo/xóa SQLite tạm trong thư mục scratch.

1. Mặc định: kiểm tra hash input/output/upstream manifest, định danh stage/tag, attestation của selected artifact, mapping/corpus, first_seen coverage, row counts và config drift.
2. `--scan-splits`: thêm scan toàn bộ train/validation/test theo batch; kiểm tra index bounds, timestamp cutoffs, temporal order và duplicate event xuyên split bằng chỉ mục trên đĩa.

Mỗi file chỉ hash một lần trong một run; có log tiến độ khi hash file lớn. Config drift được tách riêng khỏi lỗi artifact, nhưng vẫn chặn readiness. Report không biến drift thành MATCH hoặc cho phép evaluator bỏ qua kiểm chứng hiện tại.

Exit code 1 cùng `status=blocked` là kết quả audit có blocker, không nhất thiết là chương trình lỗi. Xem `blockers`, `config_drift`, `artifact_checks`, `corpus`, `protocol`, `split_scan`. `status=failed` ghi lỗi khiến audit chưa hoàn tất; cần xử lý rồi chạy lại.

Report hiện có thể bị chặn vì config lịch sử khác runtime và protocol mặc định là legacy. Sau khi xác minh artifact, cần giải quyết snapshot config lịch sử và tương thích runtime riêng; không chỉ sửa `merged_name`, không sửa hash manifest và không chạy lại pipeline toàn bộ khi chưa có bằng chứng cần thiết.

## Lệnh local

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"

# Chạy test mới và test tương thích config/CLI trước.
.\src\.venv-baseline\Scripts\python.exe -m pytest -q `
  src/tests/config `
  src/tests/tools/evaluation/test_bundle_audit.py `
  src/tests/tools/evaluation/test_candidate_recall_protocol.py
```

Sau khi test pass, audit checksum trước. Có thể mất thời gian vì đọc các raw và artifact lớn. Tên report có timestamp để tránh ghi đè.

```powershell
$p0Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$p0Report = "src/experiments/readiness/p0_$p0Stamp.json"
.\src\.venv-baseline\Scripts\python.exe -u src/scripts/data_pipeline/audit_bundle.py `
  --tag multi_domain_v2_audit_20261030 `
  --report $p0Report
```

Gửi report để phân loại blocker trước khi scan toàn bộ. Nếu artifact bị sai hash/missing, chưa cần tốn chi phí scan. Chỉ sau khi artifact ổn định, chạy bản đầy đủ:

```powershell
# Chọn scratch trên ổ còn nhiều dung lượng; index có thể lớn hơn Parquet nén đáng kể.
$p0Scratch = "src/experiments/readiness/scratch"
New-Item -ItemType Directory -Force -Path $p0Scratch | Out-Null
$p0Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
.\src\.venv-baseline\Scripts\python.exe -u src/scripts/data_pipeline/audit_bundle.py `
  --tag multi_domain_v2_audit_20261030 `
  --scan-splits --scratch-dir $p0Scratch `
  --report "src/experiments/readiness/p0_full_$p0Stamp.json"
```

Scan toàn bộ có thể lâu và tốn đĩa. Không chạy build/eval song song với audit trên cùng artifact. Không bắt đầu full embedding hoặc test evaluation trước khi xem report và đóng các blocker.
