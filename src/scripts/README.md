# scripts/

Mọi tham số nằm trong `configs/*.yaml`; các file `.sh` chỉ là lớp bọc mỏng (cd về gốc project, đặt
`PYTHONPATH`, đọc config). Chạy từ đâu cũng được: `bash scripts/sh/<tên>.sh`.

Mọi thư mục của project được định nghĩa MỘT lần trong `configs/data_paths.yaml → paths`; Python lấy qua
`package.config.get_data_paths()`, shell qua `data_path <tên>` (= `python -m package.config path:<tên>`). Không ghép
đường dẫn bằng tay trong code/script.

```
resource/raw/<Domain>.jsonl.gz, meta_<Domain>.jsonl.gz     tải về (download_review_data.sh)
resource/cleaned/<Domain>/interactions.parquet             stage 1
resource/filtered/<tag>/interactions.parquet               stage 2
resource/mapped/<tag>/{user2id,item2id}.json               stage 3
resource/splits/<tag>/{train,validation,test}.parquet      stage 3
resource/logs/<tag>/run_tools.log                          log pipeline/tool   (paths.log_dir)
experiments/exp_NNN/{config.yaml,metrics.json,README.md}   kết quả thí nghiệm (paths.experiments_dir)
experiments/candidate_recall/exp_NNN/…                     candidate_recall    (+ candidate_recall.experiments_subdir)
tests/logs/*.log                                           log của test (tests/run_*.sh), ngoài cấu hình này
```

`resource/` bị `.gitignore`; `experiments/` được giữ lại (chỉ bỏ qua `*.log`).

## Data pipeline

| Script | Việc |
|---|---|
| `download_review_data.sh` | tải review + meta của mọi domain (`--no-meta` để bỏ meta) |
| `stage1_clean_domain.sh` | clean từng domain (lặp qua `domains.yaml → domains`) |
| `stage2_merge_filter.sh` | gộp domain + k-core (`--cold-start-report` để so sánh warm user) |
| `stage3_map_split.sh` | ID mapping + temporal split + leakage check |
| `run_data_pipeline.sh` | chạy liền stage 1 → 2 → 3 |
| `run_eda.sh` | EDA interaction trên review thô (streaming) |

Stage đã có output thì bị bỏ qua; thêm `--force` để làm lại.

## Experiments

`run_baselines.sh`, `tune_baselines.sh`, `candidate_recall.sh`, `run_tools.sh`, `check_llm_provider.sh`.
Tham số nằm trong các file YAML atomics: `baselines.yaml`, `tuning.yaml`, `recommendation_metrics.yaml`,
`segment_thresholds.yaml`, `candidate_recall.yaml`, `llm.yaml`.

## Biến môi trường

- `PYTHON` — interpreter, vd `PYTHON=.venv/Scripts/python`
- `DOMAINS` — ghi đè danh sách domain, vd `DOMAINS="Video_Games Toys_and_Games"`
- `TAG` — ghi đè `run_tag.yaml → tag`, để thử ít domain mà không ghi đè bản chạy đủ
- `LLM_API_KEY` — API key cho `configs/llm.yaml` (`api_key: ${LLM_API_KEY:-}`); KHÔNG ghi key vào file yaml

```bash
DOMAINS="Video_Games Toys_and_Games" TAG=vg_toys bash scripts/sh/run_data_pipeline.sh
TAG=vg_toys bash scripts/sh/run_baselines.sh --models popularity,item_knn
```
