# scripts/

Mọi tham số nằm trong `configs/*.yaml`; các file `.sh` chỉ là lớp bọc mỏng (cd về gốc project, đặt
`PYTHONPATH`, đọc config). Chạy từ đâu cũng được: `bash scripts/sh/<tên>.sh`.

Mọi thư mục của project được định nghĩa MỘT lần trong `configs/path/data_paths.yaml → paths`; Python lấy qua
`package.config.get_data_paths()`, shell qua `data_path <tên>` (= `python -m package.config path:<tên>`). Không ghép
đường dẫn bằng tay trong code/script.

```
resource/raw/<Domain>.jsonl.gz, meta_<Domain>.jsonl.gz     tải về thủ công (đặt vào resource/raw/ trước khi chạy stage 1)
resource/cleaned/<Domain>/interactions.parquet             stage 1
resource/filtered/<tag>/interactions.parquet               stage 2
resource/mapped/<tag>/{user2id,item2id}.json               stage 3
resource/splits/<tag>/{train,validation,test}.parquet      stage 3
resource/logs/<tag>/run_tools.log                          log pipeline/tool   (paths.log_dir)
experiments/exp_NNN/{config.yaml,metrics.json,README.md}   kết quả thí nghiệm (paths.experiments_dir)
experiments/candidate_recall/exp_NNN/…                     candidate_recall    (+ candidate_recall.experiments_subdir)
experiments/agent_eval/exp_NNN/…                           run_agent_eval      (+ agent_eval.experiments_subdir; có trajectories/requests/scored.jsonl)
tests/logs/*.log                                           log của test (tests/run_*.sh), ngoài cấu hình này
```

`resource/` bị `.gitignore`; `experiments/` được giữ lại (chỉ bỏ qua `*.log`).

## Data pipeline

| Script | Việc |
|---|---|
| `stage1_clean_domain.sh` | clean từng domain (lặp qua `domains.yaml → domains`) |
| `stage2_merge_filter.sh` | gộp domain + k-core (`--cold-start-report` để so sánh warm user) |
| `stage3_map_split.sh` | ID mapping + temporal split + leakage check |
| `run_data_pipeline.sh` | chạy liền stage 1 → 2 → 3 |
| `run_eda.sh` | EDA interaction trên review thô (streaming) |

Stage đã có output thì bị bỏ qua; thêm `--force` để làm lại.

## Experiments

`run_baselines.sh`, `tune_baselines.sh`, `candidate_recall.sh`, `run_tools.sh`, `check_llm_provider.sh`, `run_agent_eval.sh`.
Tham số nằm trong các file YAML atomics: `baselines.yaml`, `tuning.yaml`, `recommendation_metrics.yaml`,
`segment_thresholds.yaml`, `candidate_recall.yaml`, `llm.yaml`, `agent.yaml` (giới hạn PlanExecutor), `agent_eval.yaml`.

### Agent eval và plan-reflect

`run_agent_eval.sh` chạy cùng một tập request qua các agent và ghi `trajectories.jsonl`, `scored.jsonl`, `metrics.json`.
Planner có plan-reflect: nếu plan chạy có step lỗi, hoặc không ra item nào (và không phải `ask_user`), LLM được gửi báo cáo
step và viết lại plan, tối đa `agent.reflect_rounds` lần (`configs/agent/agent.yaml`, mặc định 1, 0 = tắt).
Không reflect khi có id bịa hoặc SQL hết giờ. Ghi đè từng lần chạy: `--reflect-rounds N` (ghi vào `config.yaml` của experiment).

Cột kết quả liên quan (trung bình theo agent/kind/segment):
- `task_success`: đúng trên kết quả CUỐI (sau khi sửa), định nghĩa không đổi.
- `first_attempt_ok`: đúng ngay lần chạy đầu (không step lỗi, có item hoặc hỏi lại). Chênh với `task_success` = phần reflect cứu được.
- `reflections`: số lượt reflect trung bình. `completion_tokens` / `llm_latency_seconds` đã cộng dồn cả lượt reflect.

`--resume` chỉ dùng lại trajectory planner được tạo với cùng `reflect_rounds` (file cũ trước plan-reflect tính là 0); khác thì chạy lại.
Kết quả LLM không tái lập hoàn toàn: so bật/tắt reflect cần lặp nhiều lần và báo phương sai.

## Biến môi trường

- `PYTHON` — interpreter, vd `PYTHON=.venv/Scripts/python`
- `DOMAINS` — ghi đè danh sách domain, vd `DOMAINS="Video_Games Toys_and_Games"`
- `TAG` — ghi đè `run_tag.yaml → tag`, để thử ít domain mà không ghi đè bản chạy đủ
- `LLM_API_KEY` — API key cho `configs/agent/llm.yaml` (`api_key: ${LLM_API_KEY:-}`); KHÔNG ghi key vào file yaml

```bash
DOMAINS="Video_Games Toys_and_Games" TAG=vg_toys bash scripts/sh/run_data_pipeline.sh
TAG=vg_toys bash scripts/sh/run_baselines.sh --models popularity,item_knn
```
