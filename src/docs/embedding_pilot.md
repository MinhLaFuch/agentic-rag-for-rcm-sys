# Pilot model thực sau P0

## Phạm vi

P0 đã pass với bundle `multi_domain_v2_audit_20261030`, report `p0_profile_20261116_182515.json` và 101 test local. Pilot tiếp theo đo khả năng chạy model trên máy, không đo chất lượng retrieval.

Contract ban đầu: `configs/eval/embedding_benchmark_contract.yaml`. Khóa bundle/protocol, MiniLM baseline, seed 42, text template sorted-categories v2, max length 256, budgets 50/100/200, Recall@100 và so sánh ghép cặp. Cold-query dataset, cohort/query artifacts và các quality/latency gates vẫn pending; contract chưa phải benchmark chất lượng hoàn chỉnh. Không dùng test để tuning.

## Chế độ pilot

`pilot_item_embeddings.py` yêu cầu report P0 đã đạt và đúng profile/overlay. Nó hash lại corpus, lấy mẫu ID bằng reservoir theo seed với quota cân bằng domain, rồi mới lấy text cho tối đa 10.000 item. Toàn bộ catalog ID được duyệt nhưng không nạp toàn bộ text/vector vào RAM.

Pilot lưu ngoài resource: `sample.jsonl`, `pilot_vectors.npy` và `report.json`. ID và vector cùng thứ tự. Đây là partial catalog; không có production `.npz` hoặc sidecar mà candidate evaluator có thể tự nhận nhầm.

CLI nạp PyTorch trước các import khoa học/dự án để kiểm tra DLL sớm; thời gian này được lưu riêng trong `torch_preflight`. Thời gian tải model/download, chọn mẫu, warm-up và encode được tách riêng. Hai encode repeat chạy sau warm-up. RSS được lấy mẫu mỗi 50ms từ sau preflight; Windows bổ sung peak working set toàn vòng đời process. GPU pilot có peak allocated/reserved VRAM riêng. Report lưu device thực, revision bất biến, library versions, corpus/sample/vector hashes, truncation exposure, thiếu metadata và throughput.

Ước lượng encode toàn catalog chỉ là ngoại suy từ mẫu cân bằng; không bao gồm extraction/save/index và không là ETA full build. Peak RAM pilot không là cận trên cho builder full hiện vẫn giữ text/batch trong RAM. Chưa chạy full build trước khi review report và chuẩn bị streaming/chunk/resume khi cần. Full builder cũng phải dùng đúng text protocol v2 nếu chọn pilot này làm cấu hình cuối.

## Lệnh local

Chưa chạy test, download model hoặc pilot trong lượt chuẩn bị này. Chạy test bằng baseline environment khi profile chưa bật:

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"
Remove-Item Env:EVAL_BUNDLE_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:CONFIG_OVERLAY_PATH -ErrorAction SilentlyContinue
.\src\.venv-baseline\Scripts\python.exe -m pytest -q src/tests/embeddings
```

Môi trường `.venv-semantic` đã có sentence-transformers theo kiểm tra trước đó, nhưng thiếu một số dependency dự án. Cài dependency vào chính môi trường này; không thay baseline environment:

```powershell
.\src\.venv-semantic\Scripts\python.exe -m pip install -e . psutil
```

Nếu máy khác chưa có sentence-transformers, cài thêm vào `.venv-semantic`. Lưu output phiên bản trong report. Dừng nếu pip báo lỗi, chưa chạy pilot tiếp.

```powershell
$env:EVAL_BUNDLE_PROFILE = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.profile.yaml").Path
$env:CONFIG_OVERLAY_PATH = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml").Path
$pilotStamp = Get-Date -Format "yyyyMMdd_HHmmss"
.\src\.venv-semantic\Scripts\python.exe -u src/scripts/data_pipeline/pilot_item_embeddings.py `
  --tag multi_domain_v2_audit_20261030 `
  --readiness-report src/experiments/readiness/p0_profile_20261116_182515.json `
  --limit 1000 --batch-size 64 --device cpu `
  --work-dir "src/experiments/embedding_pilot/pilot_$pilotStamp"
```

Lần đầu có thể tải model từ Hugging Face. Model load time bao gồm download; không gộp nó vào encode throughput. Không bật CUDA nếu chưa xác nhận GPU/PyTorch hỗ trợ. Lần sau tăng lên 10.000 item hoặc đổi device/batch chỉ sau review report; dùng `--revision` lấy từ run đầu để giữ model cố định.

## Quyết định sau pilot

1. Kiểm tra status, vector validity, sample/domain coverage, metadata thiếu và truncation.
2. Xem encode throughput, peak RSS/VRAM, chi phí khởi động và vector storage estimate.
3. Chọn batch/device và kiến trúc full build theo RAM/đĩa thực; không đơn thuần bỏ `--limit` để chạy toàn catalog.
4. Hoàn thiện cohort/query artifacts, cold-query dataset và dense-only evaluator; chốt các ngưỡng validation trước khi so chất lượng.
