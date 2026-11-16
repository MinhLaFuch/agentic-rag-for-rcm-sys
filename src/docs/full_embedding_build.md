# Full embedding build: chunk, resume, atomic publish

## Trạng thái

Đã triển khai code và test synthetic; chưa chạy test hoặc full build trong lượt này theo yêu cầu người dùng. Hai resource pilot đã pass trên CPU/batch 64; pilot 10k đạt khoảng 90 item/s, peak RSS 0,918 GiB. Ngoại suy encode-only khoảng 8 giờ 8 phút, không phải cam kết ETA của full build.

Script mới: `scripts/data_pipeline/build_full_item_embeddings.py`. Builder cũ không phải đường chạy full khuyến nghị.

## Protocol và checkpoint

- Dùng MiniLM revision từ pilot 10k: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, max sequence length 256.
- Pilot/full dùng chung `format_catalog_text` để giữ `title_store_main_category_categories_sorted_v2`; category được sort trước khi ghép text.
- Đọc catalog bằng keyset `item_id > last_id`, theo chunk 4096 item; gọi encoder theo batch 64. Không nạp toàn catalog text/vector vào RAM.
- Mỗi chunk gồm ID JSON và float32 NPY, được flush/fsync và thay tên từ file tạm. Checkpoint chỉ commit sau khi cả hai file đã hoàn tất và có checksum.
- Ctrl+C hoặc process bị ngắt: chỉ chunk đang dở cần encode lại; chunk đã commit được kiểm tra lại hash, shape, norm, ID order khi resume.
- Orphan chunk chưa được checkpoint xác nhận sẽ được thay thế ở lần tiếp tục, không được tính vào catalog.
- OS lock cho cả work và output ngăn hai builder cùng ghi. Lockfile có thể còn sau khi process thoát; OS lock tự nhả, không xóa lockfile khi một build còn chạy.
- Resume khóa corpus checksum/path, model revision/probe, batch/chunk/device, text protocol, source fingerprint, environment và P0/pilot evidence. Thay đổi chúng phải dùng work/output mới.
- Corpus được hash đầu/cuối build; mỗi chunk kiểm tra size/mtime để tránh hash lại file 3 GiB hàng trăm lần. Không chạy tác vụ sửa corpus đồng thời.

## Publish và RAM/đĩa

Các chunk được ghép vào `vectors.npy` và `item_ids.npy` bằng memory mapping trong staging directory. Tất cả mmap handle được đóng trước khi rename trên Windows. Chỉ khi đủ số item và checksum cuối hoàn tất, directory được rename atomically sang output.

Artifact cuối chứa `manifest.json` với trạng thái complete, full-catalog coverage/count, encoder/provenance, checksums và build identity. Output đã tồn tại không bị ghi đè; `--resume` chỉ chấp nhận publication có đúng build identity. Gián đoạn khi ghép file hoặc sau rename có thể tiếp tục mà không encode lại catalog đã commit.

Work và output phải là hai thư mục riêng, không lồng nhau, cùng filesystem. Dành khoảng **12 GiB dung lượng trống** cho chunk/checkpoint, staging và artifact, ngoài dữ liệu/model hiện có. Vector float32 khoảng 3,77 GiB; ID array và checkpoint tốn thêm dung lượng. Work chunks được giữ lại sau publish để kiểm chứng/resume, không tự xóa.

Builder tránh các bản copy toàn catalog trong Python, nhưng RSS của full run vẫn có thể tăng do mmap/OS page cache; không coi RAM pilot là cận trên cho full build.

## Lệnh local

Chạy test trước, khi profile chưa bật. Test dùng corpus/encoder giả, không tải model:

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"
Remove-Item Env:EVAL_BUNDLE_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:CONFIG_OVERLAY_PATH -ErrorAction SilentlyContinue

.\src\.venv-baseline\Scripts\python.exe -m pytest -q `
  src/tests/embeddings `
  src/tests/tools/retrieval `
  src/tests/tools/evaluation/test_candidate_recall_protocol.py `
  src/tests/config/test_package_layout.py
```

Sau test pass, chạy full build trong môi trường semantic đã chạy pilot:

```powershell
$env:EVAL_BUNDLE_PROFILE = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.profile.yaml").Path
$env:CONFIG_OVERLAY_PATH = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml").Path
$fullBuildRoot = "src/experiments/embedding_builds/minilm_v2_audit_cpu"

.\src\.venv-semantic\Scripts\python.exe -u src/scripts/data_pipeline/build_full_item_embeddings.py `
  --tag multi_domain_v2_audit_20261030 `
  --readiness-report src/experiments/readiness/p0_profile_20261116_182515.json `
  --pilot-report src/experiments/embedding_pilot/pilot_10k_20261116_190552/report.json `
  --batch-size 64 --chunk-size 4096 --device cpu `
  --work-dir "$fullBuildRoot/work" `
  --output-dir "$fullBuildRoot/artifact"
```

**Resume:** dùng chính lệnh trên và thêm `--resume`. Giữ nguyên đường dẫn, profile, dependency và code trong suốt run. Không thêm timestamp mới vào work/output khi muốn resume. Nếu lệnh lỗi trước khi tạo checkpoint đầu tiên thì chưa có dữ liệu để resume; xử lý nguyên nhân và chọn work/output mới.

Log `encode_ETA` chỉ ước lượng encode loop, không bao gồm khởi động, xác minh checkpoint, đọc text, ghép artifact và hashing cuối. Mỗi chunk có tiến độ; startup/publish có nhãn riêng.

## Nạp artifact sau build

`load_validated_embeddings` hỗ trợ directory artifact và legacy NPZ. Directory loader kiểm tra full completion, checksums, ID order/uniqueness, shape, finite/norm, corpus và query encoder probe. Vector/ID được mmap; ID lookup dùng binary search thay vì tạo thêm dictionary hàng triệu phần tử.

Candidate evaluation hỗ trợ `--embeddings-path` trỏ tới `$fullBuildRoot/artifact`. Chưa chạy benchmark lớn ngay: cần hoàn thiện cohort/query artifact, dense-only ablation và search/filter correctness/performance theo plan. Exact search hiện vẫn có bước tạo/sort danh sách toàn catalog mỗi query; artifact mmap không tự giải quyết latency này. Ranking hybrid/runtime integration cũng chưa hoàn tất.

Giữ `manifest.json` cuối và `work/checkpoint.json` để review. Chỉ kết luận full build hoàn tất khi output được publish, số item khớp corpus và loader kiểm chứng thành công.
