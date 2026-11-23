# Dự án Công nghệ Thông tin - Học kỳ 1 (2026 - 2027)

# Nhóm
mê ngủ nướng

# Danh sách thành viên
Đặng Hồ Thiên Phúc - 52300145
Trần Phạm Anh Quân - 52300150

# Đề tài
Nghiên cứu và Ứng dụng Mô hình Agentic RAG trong Hệ thống Cá nhân hóa mua sắm trên nền tảng Thương mại Điện tử Việt Nam.

Research-grade project: Traditional RecSys + Sequential Recommendation + Retrieval + LLM-powered Agentic Recommendation trên một domain của Amazon Reviews 2023.

# Tóm tắt trong folder `src`

Tài liệu trung tâm: **`src/Project repository reading 29.10.md`** — repository reading đầy đủ (kiến trúc, evaluation framework, known issues, future work).

Tài liệu hỗ trợ trong `src/docs/` (các investigation/eval-surface docs tuần 47):

- `investigation_week47.md` — điều tra eval surface
- `eval_surface_inventory.md` — inventory các eval path
- `eval_demo_check_week47.md` — kiểm tra demo/eval outputs
- `ablation_scope.md`, `opik_assessment.md`, `case_proposal_week47.md` — phân tích ablation, Opik, case study
- `repo_reading_update_log.md`, `report_update_log.md` — nhật ký cập nhật tài liệu

## Trạng thái hiện tại

- **Phase 0–3 — Research, môi trường, dataset, data pipeline:** hoàn thành. Domain chính: `Video_Games` (+ Toys_and_Games, Electronics). Temporal split + leakage check bắt buộc.
- **Recommendation foundation:** ItemCorpus (SQLite FTS5/BM25), CandidateScorer (popularity + ItemKNN), RankTool/FilterTool/SearchTool/SimilarTool/LookupTool/MemoryTool — hoàn thành.
- **Agent layer:** PlanExecutor (LLM planner + reflection), Type1Agent (fixed plan), Inference layer — hoàn thành.
- **Evaluation:** 5-layer trajectory scoring + component benchmarks + campaign runner + multi-turn — hoàn thành; đã chạy campaign thật (`campaign_001`).
- **Evaluation integrity audit (2026-11-15):** R1–R3 diagnostics + oracle-leakage fix (`exclusion` → oracle) + placeholder-output labeling — đã commit (`2caa25d`…`91719da`).
- **Đang làm:** chuẩn bị experiments cho thesis; demo readiness verification; một số metric phụ (`evolving_interest`, `_score_language`) đang deferred.

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

## Rebuild `src/resource/` (gitignored, ~17GB)

`resource/` không nằm trong git — rebuild từ raw Amazon Reviews 2023:

```bash
cd src
DOMAIN=Video_Games PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages all --domain Video_Games
# lặp cho Toys_and_Games, Electronics; merged bundle = không truyền --domain
```

4 stages: clean → k-core filter → ID mapping → temporal split + leakage check → corpus/ItemKNN artifacts. Thiếu `--force` sẽ không ghi đè output đã có.

Benchmark `.jsonl` datasets (component benchmarks, multi-turn `conversations.jsonl`) **đã commit** trong `package/evaluation/` — không cần regenerate khi clone. `memory_correctness_dataset.jsonl` có drift-check: `python -m scripts.evaluation.build_memory_correctness_dataset --check` (regenerate bằng cách bỏ `--check`); các dataset planner/executor/grounding/integration là curated fixtures, sửa tay.

Dense retrieval artifacts (optional): env riêng có torch + sentence-transformers → `python scripts/evaluation/build_semantic_embeddings.py pin/build` → điền `configs/eval/dense_retrieval.yaml`.

## Cấu trúc thư mục

```
src/
  package/       # corpus, recommenders, tools, agents, evaluation, inference, config...
  scripts/       # data_pipeline/, evaluation/, demo/, ...
  tests/         # unit + integration tests
  configs/       # data.yaml, agent/, eval/, path/... (single source of truth)
  docs/          # investigation & eval-surface documents (xem trên)
  experiments/   # kết quả từng experiment (trajectories, scored.jsonl, metrics)
  resource/      # data đã xử lý: raw/, mapped/, splits/, corpus artifacts
  benchmarks/    # benchmark configs/fixtures
  Project repository reading 29.10.md  # TÀI LIỆU TRUNG TÂM — repository reading đầy đủ
notebooks/       # EDA/visualization only — KHÔNG chứa business logic
```

## Nguyên tắc bắt buộc

1. LLM không thay thế ranking/retrieval model chuyên biệt — chỉ dùng cho planning, reranking (Top-K giới hạn), explanation.
2. Không random split cho interaction data — chỉ temporal split (`train < validation < test`).
3. Domain (`DOMAIN` env var) không được hard-code trong business logic.
4. Mọi tool call của agent phải log được (timestamp, agent, action, tool, input hash, output, latency).
5. Không báo "hoàn thành" một phase nếu chưa có code chạy được + test pass + doc cập nhật.

---

## Prompts Reference

> **Source of truth**: `_prompt.py` files in each module. This section is a curated view for quick lookup.

### 1. Planner Agent (`package/agents/planner/_prompt.py`)
**Purpose**: Plans tool calls for product recommendation  
**Key components**:
- `SYSTEM_PROMPT` — Full system prompt with tool descriptions, rules, examples
- **Tools exposed**: ItemCFTool, SemanticSearchTool, RecoModelTool, QueryTool, SQLTool, MemoryTool
- **Reference syntax**: `$1.candidates`, `$S.shown_items.1`, `$1.love_categories`
- **Output format**: JSON `{steps: [...], ask_user: ...}`

### 2. Answer Composer (`package/inference/compose/_prompt.py`)
**Purpose**: Composes final user-facing response from ranked products  
**Key components**:
- `SYSTEM_PROMPT` — Rules for formatting product list (Vietnamese default)
- `RETRY_NOTICE` — Sent when LLM output fails validation
- **Shared texts** (defined in this file):
  - `NO_RESULT_TEXT` — "Chưa tìm thấy sản phẩm phù hợp..."
  - `TOOL_ERROR_TEXT` — "Xin lỗi, hệ thống chưa xử lý được..."
  - `OK_HEADER` — "Dưới đây là các sản phẩm gợi ý cho bạn:"
  - `PARTIAL_HEADER` — "Các sản phẩm tìm được (kết quả có thể chưa đầy đủ):"
  - `ID_ONLY_NOTE` — "Chưa có thông tin chi tiết, chỉ có mã sản phẩm."

### 3. Agent Request Templates (`package/agents/_schema.py`)
**Purpose**: Evaluation request templates (VI/EN)  
**Types**: `similar`, `personalized`, `constrained`, `cold_text`, `ambiguous`

---

### Maintenance Rule
> When you modify a `_prompt.py`, **update this section** in the same PR.  
> The central reading doc is `src/Project repository reading 29.10.md` — keep it in sync.
