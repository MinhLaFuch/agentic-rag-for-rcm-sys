# E-commerce Agentic Recommender System (Amazon Reviews 2023)

Research-grade project: Traditional RecSys + Sequential Recommendation + Retrieval + LLM-powered Agentic Recommendation trên một domain của Amazon Reviews 2023.

Xem `docs/` để hiểu đầy đủ ngữ cảnh trước khi đọc code:

- `docs/research_review.md` — các paper nền tảng đã research
- `docs/architecture.md` — kiến trúc hệ thống + agent (4 module Profile/Memory/Planning/Action)
- `docs/data_specification.md` — schema Amazon Reviews 2023, temporal split, leakage rule
- `docs/experiment_plan.md` — experiment matrix E0–E9 + ablation
- `docs/decisions.md` — nhật ký quyết định kiến trúc (WHAT/WHY/EVIDENCE/RISK)
- `docs/limitations.md` — hạn chế và rủi ro đã biết
- `docs/research_matrix.md` — bảng phân biệt "paper báo cáo" vs "đã tự chạy"

## Trạng thái hiện tại

- **Phase 0 — Research & Specification:** hoàn thành.
- **Phase 1 — Repository & Environment:** hoàn thành (13/13 test).
- **Phase 2 — Dataset Acquisition & EDA:** hoàn thành. Domain chính thức: `Video_Games`. Phát hiện quan trọng: 72.21% user chỉ có 1 interaction (cold-start-dominant), sparsity 99.9988%.
- **Phase 3 — Data Pipeline:** code hoàn thành + đã test end-to-end với dữ liệu synthetic (45/45 test pass), **CHƯA chạy trên dữ liệu thật đầy đủ** (cần chạy trên máy người dùng — xem `scripts/run_pipeline_local.py`).
- **Phase 4+:** chưa thực hiện.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy test

```bash
python -m pytest -q
```

## Chạy script kiểm tra thủ công

Scripts trong `scripts/` cần `PYTHONPATH=.` (pytest tự set qua `pyproject.toml`, nhưng chạy trực tiếp thì không):

```bash
PYTHONPATH=. python scripts/check_llm_provider.py
```

## Chạy Phase 3 pipeline trên dữ liệu thật

```bash
DOMAIN=Video_Games PYTHONPATH=. python scripts/run_phase3_pipeline_local.py \
    --review-path /duong/dan/toi/review_Video_Games.jsonl.gz
```

Pipeline: clean → k-core filter (min_user=5, min_item=5 theo `configs/data.yaml`) → ID mapping → temporal split (80/10/10) → leakage check (3 loại check, dừng pipeline nếu fail) → lưu `data/mapped/`, `data/splits/`. Paste toàn bộ output console lại cho Claude để cập nhật docs với số liệu thật.

## Cấu trúc thư mục

```
src/
  data/          # ETL, temporal split, leakage check (Phase 3)
  features/      # feature engineering
  retrieval/      # candidate retrieval (Phase 6+)
  recommenders/  # baseline models (Phase 4)
  sequential/    # sequential recommender (Phase 5)
  embeddings/    # embedding models
  memory/        # Short/Long-term, Preference, Interaction memory (Phase 7)
  agents/        # Agent workflow (Phase 8+)
  tools/         # UserProfileTool, RerankingTool, MemoryTool... (Phase 8)
  ranking/       # deterministic filtering + scoring
  evaluation/    # metrics, ablation runner (Phase 11)
  inference/     # serving logic
  api/           # FastAPI app (Phase 13)
  llm/           # LLMProvider abstraction — ĐÃ implement ở Phase 1
  config/        # config loader — ĐÃ implement ở Phase 1

configs/         # data.yaml, model.yaml, retrieval.yaml, agent.yaml, evaluation.yaml
scripts/         # CLI scripts
tests/           # unit + integration + smoke test
notebooks/       # EDA/visualization only — KHÔNG chứa business logic
experiments/     # kết quả từng experiment (config, metrics, logs)
docs/            # xem trên
```

## Nguyên tắc bắt buộc

1. LLM không thay thế ranking/retrieval model chuyên biệt — chỉ dùng cho planning, reranking (Top-K giới hạn), explanation.
2. Không random split cho interaction data — chỉ temporal split (`train < validation < test`).
3. Domain (`DOMAIN` env var) không được hard-code trong business logic.
4. Mọi tool call của agent phải log được (timestamp, agent, action, tool, input hash, output, latency).
5. Không báo "hoàn thành" một phase nếu chưa có code chạy được + test pass + doc cập nhật.
