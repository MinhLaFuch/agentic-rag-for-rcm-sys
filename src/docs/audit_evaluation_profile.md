# Evaluation profile cho bundle audit

Bundle: `multi_domain_v2_audit_20261030`.

## Kết quả kiểm chứng local ngày 2026-11-16

Đã đọc log `test_results_20261116_182444.md`: 101 passed, exit status 0. Report `p0_profile_20261116_182515.json` có `ready_for_evaluation=true`, `blockers=[]`, historical config verified; 45 artifact checks và 27 config checks MATCH. Scan split: temporal order hợp lệ, 0 overlapping events. P0 đạt đối với profile này; đây chưa phải bằng chứng chất lượng embedding hoặc readiness production.

## Bằng chứng lịch sử

Đã khôi phục 7 config theo SHA256 trong manifest, lưu tại `configs/historical/multi_domain_v2_audit_20261030/configs/`. Bốn file khác runtime được tìm trong Git và phục hồi CRLF để khớp chính xác hash lịch sử:

| Config | Git blob |
|---|---|
| agent/agent_eval.yaml | `887e4c57ef60e9b23c54df136154ec0dd7ae7dfb` |
| data/split.yaml | `3c53ecea5e33da94b4f921219b33203ce676e0ed` |
| eval/baselines.yaml | `2e80f29af4d5b46bb67939f112da504967097080` |
| path/domains.yaml | `c7dfd899af36c695b064686296f1e127aabdfe1c` |

Ba file còn lại khớp byte hiện tại. `recovery.yaml` lưu hash và nguồn từng file. `.gitattributes` giữ nguyên byte snapshot khi checkout. Đây là config evidence lịch sử, không phải các file config hiện tại được sửa để làm MATCH. Data và manifest cũ không thay đổi.

## Runtime tương thích

Overlay `configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml` chọn bundle audit, `temporal_train_core`, hai cutoff đã ghi nhận, seed 42, k=20 và historical metadata policy. Các trường mới của schema hiện tại vẫn dùng config hiện tại.

Profile `.profile.yaml` pin checksum overlay và contract runtime. Cần bật cả hai biến môi trường bằng đường dẫn tuyệt đối:

- `EVAL_BUNDLE_PROFILE`: chọn bằng chứng lịch sử.
- `CONFIG_OVERLAY_PATH`: chọn cấu hình chạy hiện tại.

Verifier dùng snapshot **chỉ** cho `config_sha256`. Input/output/upstream vẫn kiểm tra file thật như trước. Không có profile thì hành vi kiểm chứng mặc định vẫn nghiêm ngặt. Profile sai tag, overlay đổi byte, runtime sai protocol/cutoff hoặc snapshot không khớp hash sẽ bị từ chối.

Report audit vẫn liệt kê `config_drift` của các file runtime gốc, đồng thời ghi `audit_profile`, hash snapshot và hash runtime riêng. Drift không còn là blocker khi snapshot đúng và contract runtime đạt. Candidate experiment và ranking/checkpoint lưu profile provenance.

Candidate evaluation nay dùng cùng `build_core_model` với ranking: ItemKNN/popularity từ train-core, history/seen từ toàn bộ lịch sử trước target, cache được kiểm chứng bằng mapping và fit hash. Với protocol audit hiện tại, train-core CF giữ cố định cả khi đánh giá test; không mặc định refit CF bằng validation. Cold/sparse/warm vẫn phân loại bằng full pre-target history.

## Chạy local

Các lệnh dưới đây đã được người dùng chạy local và xác nhận kết quả ở trên. Khi cần kiểm tra lại sau thay đổi mới, chạy test khi profile chưa bật để các test mặc định không bị ảnh hưởng bởi overlay:

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"
Remove-Item Env:EVAL_BUNDLE_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:CONFIG_OVERLAY_PATH -ErrorAction SilentlyContinue

.\src\.venv-baseline\Scripts\python.exe -m pytest -q `
  src/tests/config `
  src/tests/data/pipeline/test_stage_manifests.py `
  src/tests/data/pipeline/test_historical_config_evidence.py `
  src/tests/tools/evaluation/test_bundle_audit.py `
  src/tests/tools/evaluation/test_candidate_recall_protocol.py
```

Sau test pass, bật profile và chạy lại full P0:

```powershell
$env:EVAL_BUNDLE_PROFILE = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.profile.yaml").Path
$env:CONFIG_OVERLAY_PATH = (Resolve-Path "src/configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml").Path
$p0Scratch = "src/experiments/readiness/scratch"
New-Item -ItemType Directory -Force -Path $p0Scratch | Out-Null
$p0Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

.\src\.venv-baseline\Scripts\python.exe -u src/scripts/data_pipeline/audit_bundle.py `
  --tag multi_domain_v2_audit_20261030 --scan-splits `
  --scratch-dir $p0Scratch `
  --report "src/experiments/readiness/p0_profile_$p0Stamp.json"
```

Hash/scan vẫn chạy trên dữ liệu thật; không tái sử dụng report trước để bỏ kiểm chứng. Nếu report còn blocker, chưa bắt đầu embedding benchmark. Profile không tự tích hợp dense vào ranking/demo; việc đó vẫn thuộc giai đoạn sau.

Kết thúc phiên audit thì unset hai biến để trở về cấu hình mặc định. Không dùng profile này để chạy lại pipeline ghi đè dữ liệu audit.
