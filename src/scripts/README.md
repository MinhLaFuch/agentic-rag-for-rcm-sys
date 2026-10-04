# scripts/

Mọi tham số nằm trong `configs/*.yaml`; các file `.sh` chỉ là lớp bọc mỏng (cd về gốc project, đặt
`PYTHONPATH`, đọc config). Chạy từ đâu cũng được: `bash scripts/sh/<tên>.sh`.

Dữ liệu nằm dưới `resource/` (đường dẫn: `configs/data.yaml → paths`, bị `.gitignore`):

```
resource/raw/<Domain>.jsonl.gz, meta_<Domain>.jsonl.gz     tải về (download_review_data.sh)
resource/cleaned/<Domain>/interactions.parquet             stage 1
resource/filtered/<tag>/interactions.parquet               stage 2
resource/mapped/<tag>/{user2id,item2id}.json               stage 3
resource/splits/<tag>/{train,validation,test}.parquet      stage 3
```

## Data pipeline

| Script | Việc |
|---|---|
| `download_review_data.sh` | tải review + meta của mọi domain (`--no-meta` để bỏ meta) |
| `stage1_clean_domain.sh` | clean từng domain (lặp qua `data.yaml → domains`) |
| `stage2_merge_filter.sh` | gộp domain + k-core (`--cold-start-report` để so sánh warm user) |
| `stage3_map_split.sh` | ID mapping + temporal split + leakage check |
| `run_data_pipeline.sh` | chạy liền stage 1 → 2 → 3 |
| `run_eda.sh` | EDA interaction trên review thô (streaming) |

Stage đã có output thì bị bỏ qua; thêm `--force` để làm lại.

## Experiments

`run_baselines.sh`, `tune_baselines.sh`, `candidate_recall.sh`, `run_tools.sh`, `check_llm_provider.sh`.
Tham số nằm trong `model.yaml`, `evaluation.yaml`, `retrieval.yaml`, `agent.yaml`.

## Biến môi trường

- `PYTHON` — interpreter, vd `PYTHON=.venv/Scripts/python`
- `DOMAINS` — ghi đè danh sách domain, vd `DOMAINS="Video_Games Toys_and_Games"`
- `TAG` — ghi đè `data.yaml → run_tag`, để thử ít domain mà không ghi đè bản chạy đủ

```bash
DOMAINS="Video_Games Toys_and_Games" TAG=vg_toys bash scripts/sh/run_data_pipeline.sh
TAG=vg_toys bash scripts/sh/run_baselines.sh --models popularity,item_knn
```
