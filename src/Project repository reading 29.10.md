---
created: 2026-09-27-15:07
updated: 2026-11-03-12:00
viewed: 2026-11-03-12:00
---
# 1. Đọc nhanh

**agentic-rag-for-rcm-sys / `src`** — hệ gợi ý sản phẩm bằng LLM agent, chạy trên Amazon Reviews 2023 (3 domain: `Video_Games`, `Toys_and_Games`, `Electronics`).

> **LLM chỉ quyết định "làm gì"; tool cung cấp thao tác có kiểm soát; `ItemCorpus` cung cấp kiến thức về item; recommender cung cấp tín hiệu gợi ý; tầng agent ghép kết quả; tầng inference viết câu trả lời cuối từ đúng những item agent đã chọn.**

Mỗi mục dưới đây là một thành phần: vai trò → bảng *từng file làm gì* → điểm dễ nhầm. Trạng thái đối chiếu: repo tại commit `f00b62f` (02/11/2026), GitNexus index hiện tại (6.013 nodes, 11.804 edges, 209 clusters, 264 flows).

| Thành phần | Nơi nằm | Vai trò |
|---|---|---|
| Config | `configs/`, `package/config/` | Mọi tham số trong YAML; một nguồn duy nhất cho đường dẫn |
| Data pipeline | `package/data/`, `scripts/data_pipeline/`, `scripts/eda_diagnostic/` | Review thô → sạch → gộp domain + k-core → map id + chia theo thời gian |
| Item corpus | `package/tools/corpus/`, `tools/_schema.py`, `tools/_limits.py` | Kho item read-only (SQLite in-memory) mà mọi tool đọc |
| Tools | `package/tools/{base,sql_query,retrieval,ranking,score}/`, `package/memory/` | Các thao tác có kiểm soát mà agent được gọi |
| Recommendation models | `package/tools/recommenders/` | Popularity, ItemKNN, BPR-MF… |
| API layer (LLM) | `package/api/` | `LLMProvider` + bản OpenAI-compatible |
| Agent layer | `package/agents/{planner,type1,toolkit,results}/` | `PlanExecutor` (LLM viết plan), `Type1Agent` (plan cố định) |
| Inference | `package/inference/{outcome,compose,grounding}/` | Viết câu trả lời cuối từ item agent đã chọn (LLM + grounding, hoặc template) |
| Evaluation | `package/evaluation/`, `package/tools/evaluation/` | **5-layer evaluation (L1-L5), 7 request kinds, component benchmarks, multi-turn, campaign orchestration, statistical analysis, reporting** |
| Demo | `package/demo/{adapter,backend,samples,view}/`, `scripts/demo/` | Giao diện Gradio (mock / live, đã nối inference) |
| Scripts | `scripts/` | Entry point chạy pipeline, thí nghiệm, đánh giá |
| Tests | `tests/` | pytest cho config, data, agents, tools, demo, evaluation |

Bố cục chi tiết: §2.1. Quy ước code (một symbol mỗi file, tên trùng tên file): §2.6. Bảng đổi tên sau refactor 17/10: §2.7.

## 1.1. Snapshot hiện tại — 02/11/2026, commit `f00b62f`

**Thay đổi so với snapshot 31/10** (`git diff --name-status b40643d..HEAD`: 47 file mới, 23 sửa, 2 xoá, 1 đổi tên):

- **`package/agents/session.py`**: `Turn` → `_Turn` (private) để tuân thủ quy ước "một symbol public mỗi file" (test `tests/config/test_package_layout.py` giờ pass).
- **`package/evaluation/`**: Thêm `campaign/` (orchestration multi-run), `statistics/` (bootstrap CI, paired significance), `reporting/generator.py` (chart layer-comparison, request-kind heatmap, retrieval funnel, latency distribution, multi-turn performance).
- **`package/tools/evaluation/`**: Thêm `normalize_query_text.py` (ascii_fold cho Unicode), `ranking_run_store.py` (checkpoint SQLite + lock), `ranking_stream_summary.py` (cộng dồn metric retrieval/ranking), `stage_progress.py` (progress bar ETA).
- **`package/tools/recommenders/`**: Thêm provenance files (`file_hash.py`, `mapping_hash.py`, `fit_split_names.py`, `fit_provenance.py`) để trace artifact reproducibility.
- **`package/memory/memory_tool.py`**: Tổng hợp `love/hate_categories`, `loved/hated_items` từ rating; dùng SQL `MIN/MAX/GROUP BY` (không bị giới hạn 100 dòng `corpus.select`).
- **`package/inference/`**: `compose_llm.py` có `price_tolerance`, `check_numbers` config; `grounding/check_grounding.py` kiểm `bare_asin`, `mentioned_item_ids` vs text, giá rating.
- **Mới trong `scripts/evaluation/`**: `analyze_ranking_bottlenecks.py` (chẩn đoán mất mát retrieval vs headroom ranking + fusion nguồn), `evaluate_product_reply.py`, `evaluate_with_jev.py` (product reply evaluation faithfulness + communication).
- **`tests/config/test_package_layout.py`**: Bắt buộc 1 symbol public/file, tên trùng file (case/underscore-insensitive); cross-folder private import cấm.
- **`docs/evaluation/`**: `RANKING_PILOT_REVIEW.md`, `FINAL_SUMMARY.md`, `METRICS.md`, `REQUEST_KINDS.md`, `MULTI_TURN.md`, `EXECUTION.md`, `CAMPAIGN.md`, `ARCHITECTURE.md`.

---

# 2. Bức tranh tổng thể

## 2.1. Cấu trúc thư mục
## 2.1. Cáº¥u trÃºc thÆ° má»¥c

```
src/
â”œâ”€â”€ configs/     20 file YAML, 4 thÆ° má»¥c con: path/ (3), data/ (3), eval/ (6), agent/ (8)
â”œâ”€â”€ package/     toÃ n bá»™ logic (import lÃ  `package.*`): config, data, api, tools, memory, agents, inference, evaluation, demo, utils
â”‚                `evaluation/`: ablation/, requests/, layer1_outcome/ â€¦ layer5_deployment/, component/ (+ benchmarks/), diagnostics/, judge/, score_trajectory.py, summarize.py
â”œâ”€â”€ scripts/     7 thÆ° má»¥c theo chá»©c nÄƒng + README.md (cháº¡y `PYTHONPATH=. python scripts/<thÆ° má»¥c>/<tÃªn>.py`)
â”œâ”€â”€ tests/       pytest: agents/ (+ fakes/), config/, data/, demo/, evaluation/ (agent/, component/, ablation/), tools/ (má»—i module má»™t thÆ° má»¥c con) + README.md, logs/
â”œâ”€â”€ docs/        EVALUATION_PROTOCOL.md + evaluation/ (16 file); **khÃ´ng cÃ³** ablation_protocol.md / demo.md / inference_contract.md / decisions.md
â”‚
â”œâ”€â”€ resource/    (sinh ra khi cháº¡y, .gitignore) raw â†’ cleaned â†’ filtered â†’ mapped â†’ splits; corpus/ (SQLite cache), item_knn/ (.npz cache)
â””â”€â”€ experiments/ README.md + exp_NNN/{config.yaml, metrics.json, README.md}; baselines/, agent_eval/ (kÃ¨m exp_009â€“exp_013, component_benchmarks/, memory_utility_analysis/, requests / trajectories / scored .jsonl), candidate_recall/, ranking_eval/, ranking_diagnostics/, data_pipeline/, smoke_tests/, test_logs/, logs/<tag>/
```

`pyproject.toml`, `PACKAGE_SETUP.md`, `.gitattributes` **khÃ´ng cÃ²n trong `src/`** â€” Ä‘Ã£ chuyá»ƒn lÃªn gá»‘c repo trong commit `7c1144a` (29/10).

## 2.2. NguyÃªn táº¯c xuyÃªn suá»‘t

- **Tham sá»‘ náº±m trong YAML, há»£p Ä‘á»“ng (schema) náº±m trong code.** VÃ­ dá»¥ `configs/agent/tools.yaml` chá»©a giá»›i háº¡n runtime (Ä‘á»c bá»Ÿi `tools/_limits.py`), cÃ²n tÃªn cá»™t / filter key lÃ  há»£p Ä‘á»“ng nÃªn náº±m á»Ÿ `tools/_schema.py`.
- **ÄÆ°á»ng dáº«n chá»‰ láº¥y qua `package.config.get_data_paths()`**; cÃ³ test AST (`test_path_hygiene.py`) cáº¥m hard-code `resource/â€¦`, `experiments/â€¦`.
- **Business logic chá»‰ phá»¥ thuá»™c interface `LLMProvider`**, khÃ´ng import SDK cá»§a má»™t provider cá»¥ thá»ƒ.
- **Quy Æ°á»›c Ä‘áº·t tÃªn:** file báº¯t Ä‘áº§u báº±ng `_` lÃ  ná»™i bá»™ cá»§a folder Ä‘Ã³ (`_schema.py`, `_helper.py`, `_dataclass.py`, `_error.py`, `_limits.py`, `_constants.py`); má»—i hÃ m/class cÃ´ng khai náº±m trong file cÃ¹ng tÃªn.
- `load_config` nháº­n tÃªn **cÃ³ thÆ° má»¥c**: `load_config("agent/tools")`, `load_config("path/data_paths")`.

## 2.3. Hai luá»“ng cháº¡y

- **Luá»“ng offline (khÃ´ng LLM):** review thÃ´ â†’ pipeline dá»¯ liá»‡u (má»¥c 4) â†’ fit recommender (má»¥c 7) â†’ Ä‘Ã¡nh giÃ¡ (má»¥c 10).
- **Luá»“ng online (cÃ³ LLM):** cÃ¢u request â†’ `PlanExecutor` (má»¥c 9) â†’ tool (má»¥c 6) â†’ káº¿t quáº£ â†’ `Inference` (má»¥c 9.4) â†’ cÃ¢u tráº£ lá»i. Tool dá»±a trÃªn `ItemCorpus` (má»¥c 5) vÃ  recommender Ä‘Ã£ fit (má»¥c 7).

## 2.4. SÆ¡ Ä‘á»“ runtime

```mermaid
flowchart TB
    USER["User"]

    subgraph AGENT_LAYER["Agent layer â€” package/agents, package/api"]
        LLM["LLMProvider<br/>(OpenAICompatibleProvider)"]
        EXEC["PlanExecutor<br/>LLM viáº¿t plan JSON â†’ cháº¡y tá»«ng step"]
        T1["Type1Agent<br/>plan cá»‘ Ä‘á»‹nh, khÃ´ng LLM"]
    end

    subgraph INFER_LAYER["Inference â€” package/inference"]
        ANS["compose_answer<br/>item agent Ä‘Ã£ chá»n â†’ cÃ¢u tráº£ lá»i<br/>(LLM + kiá»ƒm grounding, hoáº·c template)"]
    end

    subgraph TOOL_LAYER["Tool layer â€” package/tools, package/memory"]
        SEARCH["SemanticSearchTool<br/>text â†’ candidates (BM25)"]
        CF["ItemCFTool<br/>seed items â†’ similar items"]
        RECO["RecoModelTool<br/>candidates â†’ ranked"]
        QUERY["QueryTool<br/>item_ids â†’ metadata"]
        MEMORY["MemoryTool<br/>user_id â†’ profile tá»« history"]
        SQL["SQLTool<br/>filter â†’ candidates<br/>(chÆ°a cáº¥p cho planner)"]
    end

    subgraph KNOWLEDGE["Item knowledge"]
        CORPUS["ItemCorpus<br/>SQLite in-memory, read-only<br/>items Â· item_categories Â· items_fts"]
    end

    subgraph MODELS["Recommendation models â€” tools/recommenders, tools/score"]
        POP["PopularityRecommender"]
        KNN["ItemKNNRecommender"]
        SCORER["CandidateScorer (Protocol)<br/>â”” BaselineScorer"]
    end

    INTERACT["Userâ€“item interactions<br/>(splits/train.parquet)"]

    USER --> LLM --> EXEC
    EXEC --> SEARCH & CF & RECO & QUERY & MEMORY

    SEARCH --> CORPUS
    SEARCH -.->|"mÆ°á»£n bá»™ compile filter"| SQL
    SQL -.-> CORPUS
    QUERY --> CORPUS
    MEMORY --> CORPUS
    MEMORY --> INTERACT

    INTERACT --> POP
    INTERACT --> KNN
    KNN -->|"similarity matrix"| CF
    POP --> SCORER
    KNN --> SCORER
    SCORER --> RECO

    T1 --> CF
    T1 --> RECO
    T1 --> QUERY

    EXEC --> ANS
    T1 --> ANS
    ANS -.->|"mode = llm"| LLM
    ANS --> USER
```

~~Ba Ä‘iá»ƒm dá»… nháº§m:~~

1. ~~ðŸ”´**Planner khÃ´ng cÃ³ `SQLTool`.** `agents/toolkit/build_tools.py` (`build_tools()` â†’ `AgentTools`; `for_planner()` = 4 tool: ItemCF, RecoModel, Query, SemanticSearch; `for_planner_memory()` = thÃªm `MemoryTool`) â€” dÃ¹ng bá»Ÿi `run_agent_eval.py` vÃ  `smoke_real_llm.py` â€” khÃ´ng Ä‘Æ°a `SQLTool` vÃ o. `SQLTool` váº«n Ä‘Æ°á»£c code, test vÃ  cháº¡y trong `scripts/tools/run_tools.py`, vÃ  `SemanticSearchTool` dÃ¹ng chung hÃ m `compile_filters` (`sql_query/compile_filters.py`) vá»›i nÃ³. Náº¿u muá»‘n planner dÃ¹ng filter thuáº§n cáº¥u trÃºc (khÃ´ng text) thÃ¬ pháº£i thÃªm vÃ o `agents/toolkit/build_tools.py` **vÃ ** cáº­p nháº­t `agents/planner/_prompt.py`. (`scripts/demo/demo_full_agent.py` cÃ²n báº£n `build_tools()` riÃªng, cÅ©, 5 tool, khÃ´ng qua `AgentTools` â€” Ä‘á»«ng nháº§m vá»›i báº£n tháº­t.)~~
2. ~~`PlanExecutor.run()` **tráº£ vá» danh sÃ¡ch káº¿t quáº£ tool**; cÃ¢u tráº£ lá»i cuá»‘i do `package/inference` (má»¥c 9.4) sinh sau Ä‘Ã³ vÃ  **chá»‰ trÃ¬nh bÃ y** cÃ¡c item agent Ä‘Ã£ chá»n (khÃ´ng chá»n láº¡i, khÃ´ng Ä‘á»•i thá»© tá»±). ChÆ°a cÃ³ vÃ²ng láº·p "LLM Ä‘á»c káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿" (má»¥c 15). `demo` chÆ°a gá»i `inference` (má»¥c 13.1).~~
3. ~~ðŸ”´`MemoryTool` Ä‘á»c **cáº£** `interactions` (DataFrame) vÃ  `ItemCorpus`.~~

## 2.5. Chiá»u phá»¥ thuá»™c giá»¯a cÃ¡c package

HÆ°á»›ng **Ä‘Æ°á»£c phÃ©p** (test `test_dependency_direction.py` Ã©p cÃ¡c cáº·p **bá»‹ cáº¥m** á»Ÿ cá»™t pháº£i):

```
tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º data, config                              tools âœ— agents
memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º tools, data.leakage
api â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º config
agents â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º tools, memory, api                        agents âœ— inference, demo, evaluation
inference â”€â”€â”€â”€â”€â”€â–º agents, api                               inference âœ— demo, evaluation
evaluation â”€â”€â”€â”€â”€â–º agents, inference, tools, data            evaluation âœ— demo
demo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º agents, inference, tools, memory, data    demo âœ— evaluation
má»i nÆ¡i â”€â”€â”€â”€â”€â”€â”€â”€â–º config
```

`config` vÃ  `data` khÃ´ng import `tools`/`agents` (ngoáº¡i lá»‡: `tools/corpus` dÃ¹ng `data.namespaced_item_id`; `DataPaths.split_path` import `data.split` lazily). VÃ¬ `agents` khÃ´ng Ä‘Æ°á»£c import `evaluation`, `extract_recommendations` vÃ  `TEMPLATES` náº±m trong `agents/` (`agents/results/`, `agents/_schema.py`) Ä‘á»ƒ `inference`, `evaluation` vÃ  `demo` cÃ¹ng dÃ¹ng. `evaluation/agent/_schema.py` váº«n **láº·p láº¡i** `ANSWER_STATUSES` cá»§a `inference` (cÃ³ test giá»¯ hai báº£n báº±ng nhau); lÃ½ do ban Ä‘áº§u lÃ  trÃ¡nh vÃ²ng import, nay `evaluation` Ä‘Æ°á»£c phÃ©p import `inference` nÃªn báº£n láº·p cÃ³ thá»ƒ bá». `package/__init__.py` **rá»—ng**; `tools/__init__.py` váº«n import eager `evaluation`, `recommenders`â€¦ (má»¥c 16.2). `tests/test_package_import.py` giá»¯ cho import nháº¹.

## 2.6. Quy Æ°á»›c cáº¥u trÃºc (Ä‘Æ°á»£c test Ã©p)

Ba file test trong `tests/config/` biáº¿n quy Æ°á»›c thÃ nh luáº­t (`scripts/` Ä‘Æ°á»£c kiá»ƒm cÃ¹ng `package/`; `tests/` Ä‘Æ°á»£c miá»…n vÃ¬ lÃ  white-box):

- **Má»™t file, má»™t symbol** (`test_package_layout.py`): module cÃ´ng khai (khÃ´ng báº¯t Ä‘áº§u báº±ng `_`, khÃ´ng pháº£i `__init__` / `__main__`) cÃ³ **Ä‘Ãºng má»™t** class / hÃ m cÃ´ng khai á»Ÿ cáº¥p module, vÃ  tÃªn Ä‘Ã³ trÃ¹ng tÃªn file (bá» dáº¥u `_`, khÃ´ng phÃ¢n biá»‡t hoa thÆ°á»ng): `ItemCFTool` â†” `item_cf_tool.py`. VÃ¬ váº­y `candidate_results` tÃ¡ch khá»i `candidate_ids.py`, má»—i recommender má»™t file, má»—i hÃ m demo má»™t file.
- **TÃªn cÃ´ng khai duy nháº¥t toÃ n package** (cÃ¹ng file test): vÃ¬ tháº¿ hai lá»›p ma tráº­n Ä‘á»•i tÃªn `PopularityMatrixRecommender` / `ItemKNNMatrixRecommender`, cÃ²n tÃªn cÅ© `PopularityRecommender` / `ItemKNNRecommender` Ä‘Æ°á»£c giá»¯ báº±ng **lá»›p con rá»—ng** cá»§a lá»›p DataFrame-based.
- **RiÃªng tÆ° theo thÆ° má»¥c** (cÃ¹ng file test): module `_xxx` chá»‰ Ä‘Æ°á»£c import trong chÃ­nh thÆ° má»¥c chá»©a nÃ³; ngoÃ i thÆ° má»¥c pháº£i Ä‘i qua `__init__.py` hoáº·c má»™t module cÃ´ng khai. VÃ¬ tháº¿ `compile_filters.py` (dÃ¹ng chung cho `retrieval/`) lÃ  module cÃ´ng khai thay vÃ¬ `_helper.py`.
- **HÆ°á»›ng phá»¥ thuá»™c** (`test_dependency_direction.py`): báº£ng á»Ÿ má»¥c 2.5; danh sÃ¡ch ngoáº¡i lá»‡ hiá»‡n rá»—ng.
- **Import pháº£i trá» tá»›i module cÃ³ tháº­t** (`test_import_resolution.py`): ra Ä‘á»i tá»« lá»—i `compare_experiments.py` import `package.agents.evaluation.ablation` (khÃ´ng tá»“n táº¡i).

Há»‡ quáº£ khi Ä‘á»c code: hÃ m / class `X` náº±m á»Ÿ file cÃ¹ng tÃªn; `_dataclass.py`, `_helper.py`, `_schema.py`, `_limits.py`, `_error.py`, `_prompt.py` lÃ  ná»™i bá»™ cá»§a thÆ° má»¥c chá»©a chÃºng; `__init__.py` lÃ  máº·t tiá»n cÃ´ng khai cá»§a thÆ° má»¥c.

## 2.7. Báº£ng Ä‘á»•i tÃªn (trÆ°á»›c â†’ sau refactor 17/10)

| TrÆ°á»›c | Sau |
|---|---|
| `config/loader.py` | `config/load_config.py` |
| `utils/console.py` | `utils/ensure_utf8_stdout.py` |
| `tools/corpus/corpus.py` | `tools/corpus/item_corpus.py` |
| `tools/sql_query/_helper.py` | `tools/sql_query/compile_filters.py` (cÃ´ng khai) |
| `api/{base,factory,openai_compatible}.py` | `api/{llm_provider,build_llm_provider,openai_compatible_provider}.py` |
| `tools/base/candidate_ids.py` (kÃ¨m `candidate_results`) | `candidate_ids.py` + `candidate_results.py` |
| `popularity.py`, `item_knn.py` (matrix) | `popularity_matrix_recommender.py`, `item_knn_matrix_recommender.py` |
| `baseline_{popularity,item_knn}.py` | `baseline_*_recommender.py` + lá»›p con rá»—ng giá»¯ tÃªn cÅ© (`popularity_recommender.py`, `item_knn_recommender.py`) |
| `tools/evaluation/{evaluator,recommendation_metrics,segment_users}.py` | `evaluate_recommender.py`, `evaluate_ranking.py`, `segment_users_by_history.py` |
| `agents/{plan_executor,_prompt,_schema,_helper}.py` | `agents/planner/â€¦` |
| `agents/evaluation/â€¦`, `agents/ablation/â€¦` | `package/evaluation/agent/â€¦` â†’ nay lÃ  `evaluation/{requests/,score_trajectory.py,summarize.py}`; `evaluation/ablation/â€¦` |
| `inference/_helper.py` | `inference/grounding/*`, `inference/cut.py`, `inference/empty_usage.py` |
| `demo/_view_model.py`, `_formatter.py`, `_adapter.py`, `_samples.py` | `demo/view/*`, `demo/adapter/*`, `demo/samples/*` |
| `configs/agent/judge.yaml` | `configs/eval/judge.yaml` |

CÃ¡c Ä‘á»•i tÃªn cÃ²n láº¡i theo cÃ¹ng quy Æ°á»›c á»Ÿ Â§2.6 (má»—i file má»™t symbol cÃ´ng khai, tÃªn trÃ¹ng tÃªn file; `_xxx.py` lÃ  ná»™i bá»™ thÆ° má»¥c): `metrics/*.py` â†’ `*_at_k.py`, `bpr_mf.py`/`random_rec.py`/`fallback.py`/`factory.py` â†’ `*_recommender.py` + `build_model.py`.

---

# 3. Config

**Vai trÃ²:** má»i giÃ¡ trá»‹ chá»‰nh Ä‘Æ°á»£c náº±m trong `configs/*.yaml`; `package/config` Ä‘á»c YAML (cÃ³ thay biáº¿n mÃ´i trÆ°á»ng) vÃ  lÃ  **nguá»“n duy nháº¥t** cho Ä‘Æ°á»ng dáº«n.

## 3.1. `configs/`

|File|Giá»¯ gÃ¬|Ai Ä‘á»c|
|---|---|---|
|`path/data_paths.yaml`|Má»i thÆ° má»¥c: `raw_dir`, `cleaned_dir`, `filtered_dir`, `mapped_dir`, `splits_dir`, `item_knn_dir` (cache `.npz`), `corpus_dir` (cache `.sqlite`), `log_dir` (= `experiments/logs`, trÆ°á»›c lÃ  `resource/logs`), `experiments_dir`. ChÃº thÃ­ch Ä‘áº§u file liá»‡t kÃª `experiments/{logs,test_logs,baselines,agent_eval,data_pipeline,smoke_tests}/` â€” váº«n **chÆ°a khá»›p** code (`candidate_recall`, `ranking_eval`, `ranking_diagnostics` khÃ´ng Ä‘Æ°á»£c nháº¯c; má»¥c 16.2)|`get_data_paths()` â†’ má»i script|
|`path/run_tag.yaml`|`tag: multi_domain` â€” tÃªn má»™t láº§n cháº¡y; stage 2/3 ghi vÃ o `<dir>/<tag>/`|`get_data_paths()`|
|`path/domains.yaml`|3 domain báº­t (`Video_Games` primary; `Toys_and_Games`, `Electronics` secondary)|`get_domains()`. TrÆ°á»ng `role` **khÃ´ng cÃ³ code nÃ o Ä‘á»c**|
|`data/cleaning.yaml`|`chunk_size: 250000`|stage 1|
|`data/filtering.yaml`|k-core `min_user_interactions=5`, `min_item_interactions=5`|stage 2|
|`data/split.yaml`|0.8 / 0.1 / 0.1 (luÃ´n temporal)|stage 3|
|`eval/baselines.yaml`|`seed`, `models`, `popularity_fallback`, `item_knn.{k,block_elements}`, `bpr_mf.{â€¦}`|`run_baselines`, `tune_baselines`, `candidate_recall`, `run_agent_eval` (láº¥y `item_knn.k`, `seed`)|
|`eval/tuning.yaml`|`selection_metric: ndcg@10`, lÆ°á»›i tham sá»‘ cho `item_knn`, `bpr_mf`|`tune_baselines`|
|`eval/recommendation_metrics.yaml`|`k_values: [5, 10, 20]`|`run_baselines`, `tune_baselines`|
|`eval/segment_thresholds.yaml`|`sparse_max_history: 4` (cold = 0, sparse 1â€“4, warm â‰¥ 5)|evaluator, `candidate_recall`, `run_agent_eval`|
|`eval/candidate_recall.yaml`|`budgets [50,100,200]`, `per_segment 1000`, `seed_items 10`, `query_items 3`, `min_metadata_coverage 0.5`, `experiments_subdir candidate_recall`|`candidate_recall`|
|`agent/tools.yaml`|`max_candidates 1000`, `max_query_rows 100`, `sql_time_budget_seconds 5`, `max_output_summary_chars 500`, `defaults.{sql_limit 100, item_cf_top_k 20, query_max_rows 20, memory_top_n_categories 3, memory_recent_items 5}`, `semantic_search.{default_limit 50, max_query_tokens 20}`|`tools/_limits.py` (**validate lÃºc load, Ä‘á»c má»™t láº§n lÃºc import**)|
|`agent/agent.yaml`|`max_steps 8`, `plan_retries 1`, `reflect_rounds 1` (0 = táº¯t plan-reflect), `max_tokens 2048`, `temperature 0.0`, `type1.{candidate_multiplier 5, min_candidates 50}`, `reflect_error_chars 300`|`agents/_limits.py` (validate)|
|`agent/llm.yaml`|`provider`, `model` (ghi tháº³ng), `base_url: ${LLM_BASE_URL:-}`, `api_key: ${LLM_API_KEY:-}`, `timeout_seconds`|`build_llm_provider`|
|`agent/agent_eval.yaml`|`agents [baseline,type1,planner,planner_memory]`, `k 10`, `per_segment 20`, `n_ambiguous 6`, `language vi`, `price_slack 1.25`, `price_round_to 5`, `min_metadata_coverage 0.5`, `trajectory_error_chars 300`, `max_consecutive_llm_errors 5`, `experiments_subdir agent_eval`, `trajectory_file`|`run_agent_eval` (vÃ  `ranking_eval` cho `min_metadata_coverage`)|
|`agent/inference.yaml`|`mode` (`llm` \| `template`), `max_items 10`, `max_tokens 2048`, `temperature 0.0`, `llm_retries 1`, `check_numbers true`, `price_tolerance 0.5` (USD), `title_chars 120`, `reason_chars 300`|`inference/_limits.py` (validate)|
|`agent/demo.yaml`|`max_error_length 300`, `max_items_display 10`, `sample_users_per_segment 3`, `default_language vi`, `max_recent_items_display 5`, `max_turn_history_rows 50`|`demo/_limits.py` (validate)|
|`agent/ablation.yaml`|`bootstrap_resamples 10000`, `confidence 0.95`, `min_n_warn 20`, `seed 42`, `metrics` (11 má»¥c, gá»“m `answer_fallback`, `inference_latency_seconds`, `inference_completion_tokens`), `groups` (**nay khai bÃ¡o tháº­t**: `reflect_0: [exp_012]`, `reflect_1: [exp_013]`, `infer_template: [exp_011]`), `contrasts` (6 contrast), `output_subdir agent_eval/ablation`|`evaluation/ablation/_limits.py`, `scripts/experiments/compare_experiments.py`|
|`agent/demo_profiles.yaml`|`demo_profiles.pinned` (danh sÃ¡ch profile ghim cho demo UI; hiá»‡n `[]`)|`demo/_profile_builder.py` (`build_profiles`, `load_config("agent/demo_profiles")`)|
|`eval/judge.yaml`|`api_key: ${OPENROUTER_API_KEY:-}`, `model jev-latest`, `base_url https://api.typesafe.ai`, `timeout_seconds 30`, `enable_long_context false`, `evaluation.faithfulness.{claim_extraction rule, support_threshold 0.7}`, `evaluation.communication.criteria.{relevance, clarity, language, honesty_about_gaps}` + rubric 5 má»©c|`evaluation/judge/jev_client.py`, `evaluation/jev_product_evaluator.py` (Ä‘á»c tháº³ng file báº±ng `yaml.safe_load`, máº·c Ä‘á»‹nh `configs/eval/judge.yaml`, **khÃ´ng** qua `load_config`)|

`tools.yaml`, `agent.yaml`, `inference.yaml`, `demo.yaml`, `ablation.yaml` Ä‘Æ°á»£c validate (trong `_limits.py` cá»§a tá»«ng package); cÃ¡c file cÃ²n láº¡i script Ä‘á»c tháº³ng (`eval/judge.yaml` Ä‘á»c báº±ng `yaml.safe_load`). **Biáº¿n mÃ´i trÆ°á»ng:** `LLM_API_KEY`, `LLM_BASE_URL` (cáº£ hai máº·c Ä‘á»‹nh rá»—ng â†’ `build_llm_provider` bÃ¡o thiáº¿u `base_url`), `OPENROUTER_API_KEY` (cho `eval/judge.yaml`). `scripts/README.md` **khÃ´ng nháº¯c** biáº¿n mÃ´i trÆ°á»ng nÃ o. Tá»« 29/10 **khÃ´ng cÃ²n comment hay docstring nÃ o trá» tá»›i file `docs/*` khÃ´ng tá»“n táº¡i** (Ä‘Ã£ bá» tham chiáº¿u `decisions.md` á»Ÿ `llm.yaml`/`domains.yaml` vÃ  `inference_contract.md` á»Ÿ `inference.yaml` + `classify_outcome.py`; má»¥c 16).

## 3.2. `package/config/`

|File|Viá»‡c|
|---|---|
|`__init__.py`|export `load_config`, `DataPaths`, `get_data_paths`, `get_domains`|
|`load_config.py`|`load_config("<thÆ°_má»¥c>/<tÃªn>")` Ä‘á»c `configs/<thÆ°_má»¥c>/<tÃªn>.yaml`, thay `${VAR}` / `${VAR:-default}` báº±ng biáº¿n mÃ´i trÆ°á»ng (káº¿t quáº£ luÃ´n lÃ  **chuá»—i**)|
|`_helper.py`|`_interpolate_env`: ngá»¯ nghÄ©a shell `:-` (biáº¿n chÆ°a Ä‘áº·t **hoáº·c rá»—ng** thÃ¬ dÃ¹ng default); `${VAR}` khÃ´ng default mÃ  thiáº¿u â†’ `ConfigError`|
|`get_data_paths.py`|`get_data_paths(tag)` â†’ `DataPaths`. **KhÃ´ng Ä‘á»c biáº¿n mÃ´i trÆ°á»ng `TAG`** (script Python dÃ¹ng `--tag`)|
|`_dataclass.py`|`DataPaths` (frozen) + `corpus_path`, `item_knn_path` (cache theo `tag` vÃ  `eval_on`) vÃ  cÃ¡c hÃ m `review_path` (**nay thá»­ `<domain>/<domain>.jsonl[.gz]` trÆ°á»›c**, rá»“i file pháº³ng á»Ÿ `raw_dir`), `meta_path`, `cleaned_path`, `filtered_path`, `split_path`; tÃªn file `interactions.parquet`; `log_dir` = `experiments/logs/<tag>`|
|`get_domains.py`|danh sÃ¡ch tÃªn domain tá»« `path/domains.yaml`|
|`__main__.py`|CLI Ä‘á»ƒ shell Ä‘á»c config/Ä‘Æ°á»ng dáº«n (khÃ´ng script nÃ o trong repo cÃ²n gá»i, vÃ¬ `scripts/sh/` Ä‘Ã£ bá»): `python -m package.config path/domains.domains` hoáº·c `path:raw_dir`, `path:cleaned_path:Video_Games`. CÃ³ báº£ng `folder_map` hard-code cho tÃªn cÅ© khÃ´ng cÃ³ thÆ° má»¥c (`domains.domains` váº«n cháº¡y).|
|`_constants.py`|`PROJECT_ROOT`, `CONFIG_DIR`, regex `${VAR}`|
|`_error.py`|`ConfigError`|

---

# 4. Data pipeline

**Vai trÃ²:** biáº¿n review thÃ´ Amazon thÃ nh 3 split theo thá»i gian Ä‘Ã£ map sang chá»‰ sá»‘ nguyÃªn, Ä‘á»§ Ä‘á»ƒ fit mÃ´ hÃ¬nh, Ä‘á»“ng thá»i cÃ³ kiá»ƒm tra leakage.

```mermaid
flowchart LR
    RAW["resource/raw<br/>reviews + meta (.jsonl.gz)"]
    S1["stage 1<br/>clean tá»«ng domain"]
    S2["stage 2<br/>gá»™p domain + k-core"]
    S3["stage 3<br/>ID mapping + temporal split<br/>+ leakage check"]
    OUT1["cleaned/&lt;Domain&gt;/interactions.parquet"]
    OUT2["filtered/&lt;tag&gt;/interactions.parquet"]
    OUT3["mapped/&lt;tag&gt;/{user2id,item2id}.json<br/>splits/&lt;tag&gt;/{train,validation,test}.parquet"]
    META["meta_&lt;Domain&gt;.jsonl.gz"]
    CORPUS["ItemCorpus"]
    MODELS["Recommenders"]

    RAW --> S1 --> OUT1 --> S2 --> OUT2 --> S3 --> OUT3
    RAW --> META --> CORPUS
    OUT3 --> MODELS
```

## 4.1. Ba stage (scripts)

|Stage|Script|Viá»‡c chÃ­nh|
|---|---|---|
|1|`data_pipeline/stage1_clean_domain.py`|Äá»c review theo chunk (`chunk_size`), `clean_interactions` tá»«ng chunk, **dedupe xuyÃªn chunk báº±ng báº£ng SQLite táº¡m** (khoÃ¡ `(user_id, parent_asin, timestamp)`), ghi parquet theo chunk. Output Ä‘á»c ra theo thá»© tá»± khoÃ¡ chÃ­nh (Ä‘Ã£ sort theo `user_id`). KhÃ´ng cÃ³ `--force` thÃ¬ bÃ¡o lá»—i náº¿u output Ä‘Ã£ tá»“n táº¡i|
|2|`data_pipeline/stage2_merge_filter.py`|`tag_domain` tá»«ng domain â†’ `merge_domains` â†’ `clean_interactions` láº§n ná»¯a â†’ `k_core_filter` **trÃªn dá»¯ liá»‡u Ä‘Ã£ gá»™p** (Ä‘áº¿m xuyÃªn domain) â†’ `optimize_interaction_dtypes` â†’ parquet. `--cold-start-report` so sá»‘ user warm khi lá»c riÃªng tá»«ng domain vá»›i khi gá»™p|
|3|`data_pipeline/stage3_map_split.py`|`build_id_mappings` + `apply_id_mapping` trÃªn **toÃ n bá»™** dá»¯ liá»‡u (ká»ƒ cáº£ val/test) â†’ `compute_temporal_cutoffs` + `temporal_split` â†’ 3 leakage check â†’ `save_splits`|
|EDA|`eda_diagnostic/run_eda.py`|EDA interaction trÃªn review thÃ´, streaming. Chá»‰ in thá»‘ng kÃª interaction; **`compute_metadata_stats` khÃ´ng Ä‘Æ°á»£c script nÃ o gá»i** (chá»‰ cÃ³ test)|
|Cháº©n Ä‘oÃ¡n|`eda_diagnostic/diagnose_splits.py`|`--tag <tag> [--out file.json]`: Ä‘á»c splits + mapping Ä‘Ã£ sinh, in bÃ¡o cÃ¡o vÃ  (tuá»³ chá»n) ghi JSON (`SplitDiagnosis`): sá»‘ dÃ²ng / user / item vÃ  khoáº£ng thá»i gian tá»«ng split; tá»‰ lá»‡ domain; **% item cá»§a val/test Ä‘Ã£ cÃ³ trong train** (theo item vÃ  theo dÃ²ng); **% user val/test cÃ³ lá»‹ch sá»­ train** (+ min / median / p90 Ä‘á»™ dÃ i lá»‹ch sá»­); **% cáº·p (user, item) láº·p** Ä‘Ã£ náº±m trong history; **% dÃ²ng `reachable`** (item cÃ³ trong train **vÃ ** cáº·p chÆ°a náº±m trong history); % user Ä‘a-domain. Má»¥c Ä‘Ã­ch: tráº£ lá»i "vÃ¬ sao recall@10 â‰ˆ 0" (Â§19.6, Â§21.7). **ChÆ°a tháº¥y káº¿t quáº£ cháº¡y trÃªn dá»¯ liá»‡u tháº­t trong zip**|

**Item id** dáº¡ng `{domain}::{parent_asin}`. Sau `tag_domain`, cá»™t váº«n tÃªn `parent_asin` nhÆ°ng giÃ¡ trá»‹ Ä‘Ã£ namespace; `original_item_id` giá»¯ asin gá»‘c. **`user_id` khÃ´ng namespace** (id toÃ n cá»¥c cá»§a Amazon â†’ giÃºp cross-domain). Domain lÆ°u thÃ nh cá»™t vÃ  tra láº¡i, **khÃ´ng parse tá»« id**. **Split** luÃ´n lÃ  temporal toÃ n cá»¥c (khÃ´ng random, khÃ´ng leave-one-out).

## 4.2. `package/data/` â€” tá»«ng file

| Folder     | File                                     | Viá»‡c                                                                                                                                                                                                                                   |
| ---------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (gá»‘c)      | `__init__.py`                            | export cÃ¡c subpackage vÃ  `domain.*`                                                                                                                                                                                                    |
|            | `_schema.py`                             | `REQUIRED_COLUMNS` (user_id, parent_asin, rating, timestamp), `OPTIONAL_COLUMNS`, `ITEM_ID_SEPARATOR = "::"`                                                                                                                           |
| `clean/`   | `clean_interactions.py`                  | bá» dÃ²ng thiáº¿u field báº¯t buá»™c + dedupe `(user, item, timestamp)`; tráº£ `(df, report)` cÃ³ sá»‘ lÆ°á»£ng loáº¡i á»Ÿ má»—i bÆ°á»›c                                                                                                                        |
|            | `iter_reviews_dataframes.py`             | Ä‘á»c `.jsonl.gz` theo chunk (`pd.read_json(chunksize=â€¦)`)                                                                                                                                                                               |
|            | `load_reviews_dataframe.py`              | Ä‘á»c cáº£ file vÃ o má»™t DataFrame (cho file nhá»/test)                                                                                                                                                                                      |
| `domain/`  | `tag_domain.py`                          | thÃªm cá»™t `domain`, `original_item_id`; ghi Ä‘Ã¨ `parent_asin` thÃ nh id cÃ³ namespace                                                                                                                                                      |
|            | `namespaced_item_id.py`                  | `"{domain}::{asin}"`                                                                                                                                                                                                                   |
|            | `merge_domains.py`                       | `pd.concat` cÃ¡c DataFrame Ä‘Ã£ tag (bÃ¡o lá»—i náº¿u chÆ°a tag)                                                                                                                                                                                |
|            | `domain_breakdown.py`                    | thá»‘ng kÃª interaction/user/item theo domain                                                                                                                                                                                             |
| `filter/`  | `k_core_filter.py`                       | láº·p tá»‘i Ä‘a 20 vÃ²ng loáº¡i user/item dÆ°á»›i ngÆ°á»¡ng (**Ä‘áº¿m theo sá»‘ dÃ²ng**); háº¿t 20 vÃ²ng chÆ°a há»™i tá»¥ thÃ¬ **cáº£nh bÃ¡o** (`warnings`) nhÆ°ng váº«n tráº£ káº¿t quáº£ chÆ°a há»™i tá»¥                                                                          |
| `loader/`  | `iter_jsonl_gz.py`                       | generator Ä‘á»c `.jsonl.gz` theo dÃ²ng                                                                                                                                                                                                    |
|            | `load_item_metadata.py`                  | Ä‘á»c `meta_<Domain>.jsonl.gz`, chá»‰ giá»¯ item `keep(domain, asin)`; cá»™t theo `META_FIELDS` + `domain`                                                                                                                                     |
|            | `optimize_interaction_dtypes.py`         | `user_id/parent_asin/domain/original_item_id` â†’ `category`, `rating` â†’ float32 (giá»¯ `timestamp` int64)                                                                                                                                 |
|            | `estimate_memory_usage_mb.py`            | Ä‘o RAM (`deep=True`) Ä‘á»ƒ log                                                                                                                                                                                                            |
|            | `_schema.py`                             | `META_FIELDS`                                                                                                                                                                                                                          |
| `mapping/` | `build_id_mappings.py`                   | gÃ¡n index theo thá»© tá»± xuáº¥t hiá»‡n Ä‘áº§u tiÃªn (khÃ´ng dá»±a timestamp)                                                                                                                                                                         |
|            | `apply_id_mapping.py`                    | thÃªm `user_idx`, `item_idx`; id láº¡ â†’ `ValueError` (khÃ´ng Ã¢m tháº§m bá»)                                                                                                                                                                   |
|            | `save_mappings.py` / `load_mappings.py`  | ghi/Ä‘á»c `user2id.json`, `item2id.json`                                                                                                                                                                                                 |
|            | `_schema.py`                             | tÃªn 2 file trÃªn                                                                                                                                                                                                                        |
| `split/`   | `compute_temporal_cutoffs.py`            | 2 má»‘c timestamp theo phÃ¢n vá»‹ toÃ n cá»¥c                                                                                                                                                                                                  |
|            | `temporal_split.py`                      | cáº¯t thÃ nh train / validation / test theo 2 má»‘c                                                                                                                                                                                         |
|            | `save_splits.py` / `load_splits.py`      | ghi/Ä‘á»c 3 parquet; `load_splits` chá»‰ láº¥y cá»™t cÃ³ trong file; `infer_matrix_shape` (Ä‘á»‹nh nghÄ©a á»Ÿ `infer_matrix_shape.py`) Ä‘Æ°á»£c `load_splits.py` import láº¡i vÃ  re-export                                                                  |
|            | `split_path.py`                          | nÆ¡i duy nháº¥t quyáº¿t Ä‘á»‹nh `<splits_dir>/<name>.parquet`                                                                                                                                                                                  |
|            | `infer_matrix_shape.py`                  | `infer_matrix_shape(*frames)` â€” kÃ­ch thÆ°á»›c ma tráº­n suy tá»« chá»‰ sá»‘ lá»›n nháº¥t. Sau refactor Ä‘Ã£ háº¿t trÃ¹ng (khÃ´ng cÃ²n báº£n thá»© hai trong `load_splits.py`); `load_splits.py` import láº¡i nÃªn pyflakes bÃ¡o import thá»«a                          |
|            | `_schema.py`                             | `SPLIT_NAMES = (train, validation, test)`                                                                                                                                                                                              |
| `leakage/` | `check_split_temporal_order.py`          | `max(train) â‰¤ min(val)` vÃ  `max(val) â‰¤ min(test)`                                                                                                                                                                                      |
|            | `check_no_duplicate_across_splits.py`    | khÃ´ng dÃ²ng nÃ o xuáº¥t hiá»‡n á»Ÿ 2 split                                                                                                                                                                                                     |
|            | `check_profile_snapshot.py`              | khÃ´ng interaction nÃ o cÃ³ `timestamp > as_of` (dÃ¹ng cho `MemoryTool`, `run_agent_eval`, stage 3)                                                                                                                                        |
|            | `_error.py`                              | `LeakageError`                                                                                                                                                                                                                         |
| `eda/`     | `compute_interaction_stats.py`           | thá»‘ng kÃª trÃªn DataFrame (chá»‰ dÃ¹ng trong test)                                                                                                                                                                                          |
|            | `compute_interaction_stats_streaming.py` | thá»‘ng kÃª streaming trÃªn review thÃ´ (dÃ¹ng bá»Ÿi `run_eda`)                                                                                                                                                                                |
|            | `print_streaming_stats_report.py`        | in bÃ¡o cÃ¡o                                                                                                                                                                                                                             |
|            | `diagnose_splits.py`                     | `diagnose_splits(...)` â†’ `SplitDiagnosis` (cÃ¡c chá»‰ sá»‘ á»Ÿ má»¥c 4.1: item/user Ä‘Ã£ tháº¥y trong train, cáº·p láº·p, `reachable`, Ä‘á»™ dÃ i history, tá»‰ lá»‡ domain, % user Ä‘a-domain); chá»‰ gá»i bá»Ÿi `scripts/eda_diagnostic/diagnose_splits.py` vÃ  test |
|            | `compute_metadata_stats.py`              | thá»‘ng kÃª completeness metadata (chá»‰ dÃ¹ng trong test)                                                                                                                                                                                   |
|            | `segment_users.py`                       | phÃ¢n nhÃ³m kiá»ƒu cÅ© (`new`/`sparse_history`/`warm`, ngÆ°á»¡ng 3, cá»™t `evolving_interest` luÃ´n `False`); **chá»‰ dÃ¹ng trong test**. PhÃ¢n Ä‘oáº¡n tháº­t lÃ  `tools/evaluation/_helper.assign_segments` (`cold`/`sparse`/`warm`, `sparse_max=4`)      |
|            | `_dataclass.py`                          | `InteractionStats`, `StreamingInteractionStats`, `MetadataStats`, `SplitDiagnosis` (nay thÃªm `protocol`, `fit_diagnostics`, `domain_diagnostics`; cÃ¡c `*_reachable_pct` Ä‘Æ°á»£c chÃº thÃ­ch láº¡i lÃ  **unique-pair catalog eligibility**, khÃ´ng pháº£i tráº§n macro Recall@K)                                                                                                                                                     |

LÆ°u Ã½ Ä‘á»c code: nhiá»u file trong `clean/`, `domain/`, `mapping/`, `leakage/`, `filter/k_core_filter.py`, `eda/segment_users.py` **dÃ¹ng chung má»™t docstring Ä‘áº§u module copy tá»« file khÃ¡c** â€” Ä‘á»«ng tin docstring Ä‘áº§u file, hÃ£y tin tÃªn hÃ m.

---

# 5. Item corpus â€” kiáº¿n thá»©c vá» item

**Vai trÃ²:** kho item chá»‰ Ä‘á»c mÃ  `SQLTool`, `SemanticSearchTool`, `QueryTool`, `MemoryTool`, `ItemCFTool`, `RecoModelTool` cÃ¹ng dÃ¹ng (hai tool cuá»‘i chá»‰ Ä‘á»ƒ gáº¯n `domain`).

|File|Viá»‡c|
|---|---|
|`tools/corpus/item_corpus.py`|`ItemCorpus`: dá»±ng tá»« metadata DataFrame (`from_dataframe`, `from_parquet`) thÃ nh SQLite in-memory; khoÃ¡ láº¡i báº±ng `PRAGMA query_only` + authorizer chá»‰ cho `SELECT` (`PRAGMA`, ká»ƒ cáº£ `pragma_table_info()`, bá»‹ cháº·n). API: `select(sql, params, max_rows)` (tráº£ `(rows, truncated)`), `count`, `domains`, `item_domains`; **cáº£ `select` vÃ  `count` cÃ³ timeout `sql_time_budget_seconds`** (nÃ©m `SQLTimeOutError`). `from_dataframe` tá»« chá»‘i `domain=` mÃ¢u thuáº«n vá»›i cá»™t `domain` vÃ  `original_item_id` khÃ´ng khá»›p `parent_asin` (`ValueError`)|
|`tools/corpus/_helper.py`|`read_only_authorizer` (Ä‘Æ°á»£c `item_corpus.py` dÃ¹ng), `_clean_row` (NaNâ†’None, numpyâ†’Python), `normalize_categories`, `numeric_column`|
|`tools/corpus/_sql.py`|DDL cá»§a `item_categories` vÃ  `items_fts`, cÃ¡c index (`idx_items_id` UNIQUE, `idx_items_domain`, `idx_items_price`, `idx_cat_item`, `idx_cat_cat`, **`idx_cat_item_cat (item_id, category)` â€” má»›i, hÆ°á»›ng xá»­ lÃ½ timeout `categories_any`**), cÃ¢u SQL náº¡p FTS. CÃ³ háº±ng `ITEMS_TABLE_SCHEMA`: **khÃ´ng** dÃ¹ng Ä‘á»ƒ táº¡o báº£ng (báº£ng do `DataFrame.to_sql` táº¡o trong `from_dataframe`) nhÆ°ng **cÃ³** dÃ¹ng Ä‘á»ƒ tÃ­nh `_CORPUS_SCHEMA_FINGERPRINT` (`_sql.py:79`; má»¥c 16 báº£n 29/10)|
|`tools/corpus/_schema.py`, `_error.py`|háº±ng sá»‘ (`COVERAGE_SAMPLE`, `QUERY_CHUNK_SIZE`â€¦); `SQLTimeOutError` (lá»›p con cá»§a `ToolInputError`)|
|`tools/corpus/apply_metadata_policy.py`|`apply_metadata_policy(corpus, policy, *, as_of_timestamp)`: chá»‘t policy metadata **má»™t láº§n** cho corpus (`historical_static_catalog` â†’ mask `price`/`average_rating`/`rating_number`; `snapshot` â†’ khÃ´ng mask); mask báº±ng TEMP VIEW `items` + authorizer `SQLITE_DENY` trÃªn cÃ¡c cá»™t bá»‹ mask; Ä‘á»•i policy/cutoff sau Ä‘Ã³ â†’ `ValueError` (pháº£i reload corpus)|
|ðŸ”´`tools/corpus/build_corpus.py`|ðŸ”´dá»±ng corpus tá»« `meta_<Domain>.jsonl.gz`, chá»‰ giá»¯ item cÃ³ trong mapping, nÃ©m `ValueError` náº¿u Ä‘á»™ phá»§ dÆ°á»›i `min_coverage`|
|`tools/_schema.py`|há»£p Ä‘á»“ng: `ITEM_COLUMNS`, `SCHEMA_HINT` (Ä‘Æ°a vÃ o thÃ´ng bÃ¡o lá»—i SQL Ä‘á»ƒ LLM sá»­a), `FILTER_KEYS`, `ORDER_COLUMNS`|
|`tools/_limits.py`|giá»›i háº¡n tá»« `agent/tools.yaml` (`MAX_CANDIDATES`, `MAX_QUERY_ROWS`, `SQL_TIME_BUDGET_SECONDS`, `SEMANTIC_*`, cÃ¡c default), **Ä‘á»c má»™t láº§n lÃºc import**|

**Báº£ng trong corpus:** `items(item_id, domain, original_item_id, title, store, price NULL, average_rating, rating_number, main_category)` (**`item_id` khÃ´ng pháº£i PRIMARY KEY**, tÃ­nh duy nháº¥t do `UNIQUE INDEX idx_items_id`; kiá»ƒu cá»™t theo dá»¯ liá»‡u, vd `rating_number` lÃ  INTEGER náº¿u má»i giÃ¡ trá»‹ nguyÃªn, REAL náº¿u cÃ³ thiáº¿u), `item_categories(item_id, category)` (multi-label), `items_fts` (FTS5 trÃªn title/store/main_category/categories, tokenizer `porter unicode61`). `price` Ä‘Æ°á»£c lÃ m sáº¡ch (bá» `$`, `,`; khoáº£ng giÃ¡ dáº¡ng `"10 - 20"` hoáº·c null â†’ NULL). Ráº¥t nhiá»u item thiáº¿u giÃ¡ (~55% á»Ÿ Video_Games) â†’ má»i filter giÃ¡ máº·c Ä‘á»‹nh loáº¡i item NULL trá»« khi `include_missing_price=true`. `rating_number`, `average_rating` lÃ  sá»‘ tá»•ng há»£p **Ä‘áº¿n cuá»‘i dataset** (khÃ´ng pháº£i táº¡i thá»i Ä‘iá»ƒm split) â€” xem Â§16.3.

---

# 6. Tools

**Vai trÃ²:** cÃ¡c thao tÃ¡c cÃ³ kiá»ƒm soÃ¡t mÃ  agent Ä‘Æ°á»£c phÃ©p gá»i. LLM chá»‰ tháº¥y `name`, `description`, `input_schema` vÃ  `output_schema` (khÃ´ng tháº¥y code).

## 6.1. Há»£p Ä‘á»“ng chung â€” `tools/base/`

|File|Viá»‡c|
|---|---|
|`tool.py`|`Tool` (ABC): `name`, `description`, `input_schema`, `output_schema`, `execute()` trá»«u tÆ°á»£ng. `__init_subclass__` **báº¯t buá»™c** subclass khai bÃ¡o cáº£ bá»‘n thuá»™c tÃ­nh vÃ  cáº¥m tÃªn tham sá»‘ `agent`/`action` (`TypeError` lÃºc Ä‘á»‹nh nghÄ©a class). `__call__` bá»c `execute()` báº±ng log (`ToolCallLogger`) vÃ  báº¯t `ToolInputError` thÃ nh `ToolResult(ok=False, error=â€¦)`; exception khÃ¡c Ä‘Æ°á»£c log (`ok=False`) rá»“i **nÃ©m láº¡i**|
|`_dataclass.py`|`ToolResult(ok, data, error)`|
|`_error.py`|`ToolInputError` (input sai: filter láº¡, SQL khÃ´ng an toÃ n, domain láº¡â€¦)|
|`tool_call_logger.py`|ghi call vÃ o bá»™ nhá»› (`input` rÃºt gá»n + tÃ³m táº¯t output, khÃ´ng lÆ°u toÃ n bá»™ output), tuá»³ chá»n thÃªm JSONL|
|`_helper.py`|`_hash_input` (hash kwargs), `_simplify_args` (rÃºt gá»n args trÆ°á»›c khi log)|
|`_validation.py`|`validate_list_like`, `validate_int`â€¦ (kiá»ƒm kiá»ƒu Ä‘áº§u vÃ o, nÃ©m `ToolInputError` rÃµ rÃ ng; dÃ¹ng chung cho tool); `validate_int` cÃ³ `allow_numpy` (nháº­n `numpy.integer`, váº«n tá»« chá»‘i `bool` / `np.bool_`)|
|`candidate_ids.py`|nháº­n `list[str]` hoáº·c `list[{item_id: â€¦}]` (tá»©c output tool khÃ¡c) â†’ list id Ä‘Ã£ dedupe; **tá»« chá»‘i** Ä‘áº§u vÃ o khÃ´ng pháº£i list/tuple (chuá»—i khÃ´ng cÃ²n bá»‹ tÃ¡ch tá»«ng kÃ½ tá»±). `candidate_results.py` (file riÃªng sau refactor): giá»¯ nguyÃªn dict (ká»ƒ cáº£ `score`/`similarity`), bá» trÃ¹ng theo `item_id` â€” **chÆ°a tool nÃ o dÃ¹ng**, chá»‰ cÃ³ test|
|`check_top_k.py`|kiá»ƒm `1 â‰¤ giÃ¡ trá»‹ â‰¤ upper` (máº·c Ä‘á»‹nh `MAX_CANDIDATES`); tá»« chá»‘i bool/float; thÃ´ng bÃ¡o dÃ¹ng Ä‘Ãºng tÃªn tham sá»‘ (`name=`); nay gá»i `validate_int(â€¦, allow_numpy=True)` thay vÃ¬ tá»± kiá»ƒm|

## 6.2. Báº£ng tá»•ng quan 6 tool

|Tool|NhÃ³m|VÃ o|Ra (top-level keys = Ä‘Æ°á»ng dáº«n `$N.path` há»£p lá»‡)|Dá»±a vÃ o|Planner cÃ³?|
|---|---|---|---|---|---|
|`SemanticSearchTool`|retrieval|`query` (tá»« khoÃ¡ tiáº¿ng Anh), `filters`, `limit`|`candidates` (kÃ¨m `score`), `total_matches` (`int`, **`None` náº¿u truy váº¥n Ä‘áº¿m háº¿t giá»**), `query_tokens`, `truncated`, `applied_filters`|corpus (FTS5 + BM25)|cÃ³|
|`SQLTool`|retrieval|`filters`, `order_by`, `descending`, `limit`|`candidates`, `total_matches`, `truncated`, `applied_filters`|corpus|**chÆ°a**|
|`ItemCFTool`|retrieval|`items` (seed), `top_k`, `domain`, `exclude_input`|`candidates` (`item_id`, `similarity`, `domain`), `unknown_items`|ma tráº­n similarity cá»§a ItemKNN|cÃ³|
|`RecoModelTool`|ranking|`user_id`, `candidates`, `top_k`, `exclude_seen`|`ranked`, `model`, `cold_start`, `excluded_seen`, `unscored_item_ids`|`CandidateScorer`|cÃ³|
|`QueryTool`|hydration|Ä‘Ãºng má»™t trong `item_ids` / `query` (SELECT) , `max_rows`|`items`, `missing_item_ids` (chá»‰ vá»›i `item_ids`), `truncated`|corpus|cÃ³|
|`MemoryTool`|memory|`user_id`, `top_n_categories`|`user_id`, `known`, `n_interactions`, `top_categories`, `price_range`|interactions + corpus|chá»‰ á»Ÿ `planner_memory`|

**Retrieval vs Ranking vs Hydration:** retrieval tráº£ "item nÃ o cÃ³ thá»ƒ liÃªn quan" (luÃ´n cÃ³ `item_id` nÃªn Ä‘Æ°a tháº³ng Ä‘Æ°á»£c vÃ o `RecoModelTool`); ranking tráº£ "trong cÃ¡c candidate nÃ y cÃ¡i nÃ o Ä‘á»©ng trÃªn"; hydration tráº£ metadata cho id Ä‘Ã£ biáº¿t.

## 6.3. Chi tiáº¿t tá»«ng tool

|File|Ghi chÃº Ä‘Ã¡ng biáº¿t|
|---|---|
|`sql_query/sql_tool.py` â€” `SQLTool`|Filter compile thÃ nh SQL **cÃ³ tham sá»‘**, key láº¡ bá»‹ tá»« chá»‘i â†’ LLM khÃ´ng thá»ƒ SQL-injection. Key há»£p lá»‡: `domain, price_min, price_max, include_missing_price, min_rating, min_rating_number, categories_any, categories_all, store, title_contains, exclude_item_ids`. **KhÃ´ng nháº­n danh sÃ¡ch candidate Ä‘á»ƒ lá»c** â€” tá»± truy váº¥n corpus. Sáº¯p xáº¿p NULL cuá»‘i, rá»“i `item_id` Ä‘á»ƒ deterministic; `filters` pháº£i lÃ  dict, `descending` pháº£i lÃ  bool (chuá»—i `"false"` khÃ´ng cÃ²n Ã¢m tháº§m sort DESC)|
|`sql_query/query_tool.py` â€” `QueryTool`|`item_ids` (tá»‘i Ä‘a `max_query_rows` id) hoáº·c má»™t `SELECT` tá»± do; tráº§n `max_query_rows` vÃ¬ káº¿t quáº£ Ä‘i tháº³ng vÃ o prompt; `item_ids` qua `validate_list_like`, pháº§n tá»­ pháº£i lÃ  chuá»—i khÃ¡c rá»—ng; `query` pháº£i lÃ  chuá»—i|
|`sql_query/compile_filters.py`|`compile_filters` (filter â†’ `WHERE` cÃ³ tham sá»‘, dÃ¹ng chung `SQLTool` + `SemanticSearchTool`; kiá»ƒm kiá»ƒu báº±ng `_as_list` / `_as_float` / `_as_int`, `store` so khá»›p khÃ´ng phÃ¢n biá»‡t hoa/thÆ°á»ng); tráº£ `(where, params, normalized_filters)` â€” `applied_filters` cá»§a `SQLTool` / `SemanticSearchTool` lÃ  báº£n **Ä‘Ã£ chuáº©n hoÃ¡**, khÃ´ng cÃ²n lÃ  filter thÃ´ LLM gá»­i|
|`retrieval/semantic_search_tool.py` â€” `SemanticSearchTool`|**Thá»±c táº¿ lÃ  lexical** (SQLite FTS5 + BM25), chÆ°a pháº£i embedding. Token `\w+`, bá» stopword, Ä‘áº·t trong nhÃ¡y kÃ©p, ná»‘i `OR` â†’ text ngÆ°á»i dÃ¹ng khÃ´ng inject Ä‘Æ°á»£c cÃº phÃ¡p FTS. Sáº¯p xáº¿p `score DESC, rating_number DESC, item_id`. `total_matches` Ä‘áº¿m báº±ng truy váº¥n MATCH thá»© hai; náº¿u **chá»‰** truy váº¥n Ä‘áº¿m háº¿t giá» thÃ¬ `total_matches = None` vÃ  váº«n tráº£ `candidates` (truy váº¥n chÃ­nh háº¿t giá» váº«n lÃ  `ok=False`). `input_schema` cá»§a _instance_ liá»‡t kÃª **tÃªn domain tháº­t** cá»§a corpus Ä‘á»ƒ planner khÃ´ng bá»‹a. Tá»“n táº¡i vÃ¬ ~72% user chá»‰ cÃ³ 1 interaction â†’ vá»›i há» chá»‰ cÃ³ "Ä‘iá»u há» nÃ³i"|
|`retrieval/_helper.py`, `retrieval/_schema.py`|`_tokenize` (helper) + `STOPWORDS` (schema; bá» `want`, `need`, `cheap`, `best`â€¦ â€” giÃ¡ Ä‘á»ƒ cho filter)|
|`ranking/item_cf_tool.py` â€” `ItemCFTool`|Cá»™ng cÃ¡c hÃ ng similarity cá»§a seed (khÃ´ng densify), tráº£ `unknown_items`. Cross-domain máº·c Ä‘á»‹nh; `domain` filter cÃ³ thá»ƒ tráº£ **Ã­t hÆ¡n** `top_k` vÃ¬ ItemKNN chá»‰ giá»¯ top-k lÃ¡ng giá»ng; `domain` láº¡ â†’ lá»—i `unknown domain â€¦; available: [â€¦]`, `domain=""` = khÃ´ng lá»c; tá»« chá»‘i `item2id` cÃ³ chá»‰ sá»‘ trÃ¹ng; `items` pháº£i lÃ  list chuá»—i khÃ¡c rá»—ng|
|`ranking/reco_model_tool.py` â€” `RecoModelTool`|Xáº¿p háº¡ng candidate báº±ng model (**khÃ´ng pháº£i LLM**). BÃ¡o `cold_start`, `excluded_seen`, `unscored_item_ids` thay vÃ¬ giáº¥u. KhÃ´ng cÃ³ timestamp: "as-of" Ä‘Æ°á»£c quyáº¿t Ä‘á»‹nh bá»Ÿi dá»¯ liá»‡u mÃ  model Ä‘Ã£ fit; kiá»ƒm kiá»ƒu `user_id` (chuá»—i khÃ¡c rá»—ng) vÃ  `exclude_seen` (bool); scorer tráº£ sai sá»‘ lÆ°á»£ng Ä‘iá»ƒm hoáº·c NaN/inf â†’ `ToolInputError`|
|`memory/memory_tool.py` â€” `MemoryTool`|**Chá»‰ Ä‘á»c** (khÃ´ng write/update/forget) vÃ¬ Amazon Reviews khÃ´ng cÃ³ há»™i thoáº¡i Ä‘á»ƒ trÃ­ch preference. Tá»•ng há»£p category hay mua + khoáº£ng giÃ¡ tá»« history. `as_of_timestamp` â†’ `check_profile_snapshot` cháº·n leakage. Output dÃ¹ng Ä‘Æ°á»£c qua ref, vd `"$1.top_categories"` â†’ `filters.categories_any`. Tá»•ng há»£p **báº±ng SQL** (`MIN/MAX` giÃ¡, `GROUP BY category`) nÃªn khÃ´ng bá»‹ giá»›i háº¡n 100 dÃ²ng cá»§a `corpus.select`. User láº¡ hoáº·c 0 tÆ°Æ¡ng tÃ¡c â†’ `known=False`, `top_categories=[]`, `price_range=None`, **khÃ´ng** nÃ©m lá»—i (nháº¥t quÃ¡n vá»›i cold-start cá»§a `RecoModelTool`). **Import public**: dÃ¹ng `package.memory.limits.get_memory_limits()` vÃ  `package.data.leakage.check_profile_snapshot()` thay vÃ¬ cross-folder private imports|

## 6.4. Scorer â€” `tools/score/`

|File|Viá»‡c|
|---|---|
|`candidate_scorer.py`|`CandidateScorer` (Protocol): `name`, `is_known_user`, `seen_items`, `score(user_idx, item_idxs)` â€” chá»— cáº¯m cho SASRec/BPR sau nÃ y|
|`baseline_scorer.py`|`BaselineScorer`: bá»c model há» DataFrame-based. Äiá»ƒm ItemKNN = tá»•ng similarity lÃ¡ng giá»ng vá»›i history + má»™t sá»‘ háº¡ng popularity ráº¥t nhá» (`1e-6`) Ä‘á»ƒ phÃ¡ hoÃ ; user khÃ´ng history â†’ chá»‰ popularity; `__init__` gá»i `_validate_model` (Ä‘á»™ dÃ i `popularity`, shape `user_items` / `similarity`, giÃ¡ trá»‹ há»¯u háº¡n)|

---

# 7. Recommendation models

**Vai trÃ²:** tÃ­n hiá»‡u gá»£i Ã½. Trong `package/tools/recommenders/` cÃ³ **hai há» class song song, trÃ¹ng tÃªn** â€” Ä‘Ã¢y lÃ  chá»— dá»… nháº§m nháº¥t cá»§a repo.

|Há»|File|API|DÃ¹ng á»Ÿ Ä‘Ã¢u|
|---|---|---|---|
|**DataFrame-based** (cho agent)|`baseline_popularity_recommender.py` (`BaselinePopularityRecommender`), `baseline_item_knn_recommender.py` (`BaselineItemKNNRecommender`); tÃªn cÅ© giá»¯ qua hai **lá»›p con rá»—ng** `popularity_recommender.py` (`PopularityRecommender`), `item_knn_recommender.py` (`ItemKNNRecommender`)|`fit(interactions_df)`, `.recommend(user_idx, k)`, cÃ³ `.scores`, `.user_items`, `.similarity`|`ItemCFTool`, `BaselineScorer` â†’ `RecoModelTool`, `Type1Agent`, `run_tools`, `run_agent_eval`. LÃ  `package.tools.recommenders.ItemKNNRecommender` / `PopularityRecommender`|
|**Matrix-based** (offline eval)|`recommender.py` (`Recommender` ABC), `popularity_matrix_recommender.py` (`PopularityMatrixRecommender`), `item_knn_matrix_recommender.py` (`ItemKNNMatrixRecommender`), `bpr_mf_recommender.py`, `random_recommender.py`, `fallback_recommender.py`, `build_model.py`|`fit(csr_matrix)`, `.score_batch()`, `.recommend(user_idxs, k, exclude)`|`run_baselines`, `tune_baselines`, `candidate_recall`, `tools/evaluation/`. TÃªn cÅ© cÃ²n lÃ  **alias** (khÃ´ng pháº£i ABC dÃ¹ cÃ³ háº­u tá»‘): `ItemKNNRecommenderABC = ItemKNNMatrixRecommender`, `PopularityRecommenderABC = PopularityMatrixRecommender`|

| File                                                   | Viá»‡c                                                                                                                                                                                                                                     |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `baseline_popularity_recommender.py`                   | Ä‘áº¿m táº§n suáº¥t item trong táº­p fit; cÃ³ `user_items` (CSR nhá»‹ phÃ¢n); kiá»ƒm cá»™t `user_idx` / `item_idx`, dá»¯ liá»‡u rá»—ng, `top_k` nguyÃªn dÆ°Æ¡ng                                                                                                    |
| `baseline_item_knn_recommender.py`                     | káº¿ thá»«a Popularity; cosine itemâ€“item tá»« co-occurrence, giá»¯ `neighbors` (máº·c Ä‘á»‹nh 20) lÃ¡ng giá»ng má»—i item; user khÃ´ng history â†’ popularity                                                                                                |
| `popularity_recommender.py`, `item_knn_recommender.py` | lá»›p con **rá»—ng** cá»§a hai lá»›p trÃªn, giá»¯ tÃªn cÅ© cho code hiá»‡n cÃ³; tá»“n táº¡i Ä‘á»ƒ thoáº£ luáº­t "tÃªn cÃ´ng khai duy nháº¥t" khi lá»›p ma tráº­n Ä‘á»•i tÃªn                                                                                                    |
| `recommender.py`                                       | `Recommender` ABC: `fit`, `_fit`, `score_batch`, `history_sizes`, `recommend` (loáº¡i item trong `exclude`); `_prepare_train_matrix` chuáº©n hoÃ¡ ma tráº­n train; `recommend` tráº£ `int64` vá»›i `-1` **chá»‰ lÃ  padding**; Ä‘iá»ƒm NaN â†’ `ValueError` |
| `popularity_matrix_recommender.py`                     | popularity dáº¡ng ma tráº­n                                                                                                                                                                                                                  |
| `item_knn_matrix_recommender.py`                       | ItemKNN dáº¡ng ma tráº­n, tÃ­nh theo block (`block_elements`) Ä‘á»ƒ khÃ´ng ná»• RAM; máº·c Ä‘á»‹nh `k=50`                                                                                                                                                |
| `bpr_mf_recommender.py`                                | BPR-MF tá»± cÃ i báº±ng numpy (negative sampling, SGD theo batch); máº·c Ä‘á»‹nh `learning_rate=0.05`; kiá»ƒm tham sá»‘; `_sample_negatives` láº¥y Ä‘Ãºng item chÆ°a tÆ°Æ¡ng tÃ¡c (tá»‘i Ä‘a 10 vÃ²ng rejection, rá»“i láº¥y chÃ­nh xÃ¡c tá»« pháº§n bÃ¹ cá»§a user)            |
| `random_recommender.py`                                | baseline ngáº«u nhiÃªn cÃ³ seed                                                                                                                                                                                                              |
| `fallback_recommender.py`                              | `FallbackRecommender(primary, fallback)`: user khÃ´ng history dÃ¹ng Ä‘iá»ƒm cá»§a fallback (popularity)                                                                                                                                         |
| `build_model.py`                                       | `ALL_MODELS = [random, popularity, item_knn, bpr_mf]`, `build_model(name, cfg)`; bá»c `FallbackRecommender` náº¿u `popularity_fallback: true`; seed riÃªng cá»§a model (`bpr_mf.seed`) ghi Ä‘Ã¨ seed toÃ n cá»¥c                                    |
| `build_interaction_matrix.py`                          | DataFrame â†’ CSR nhá»‹ phÃ¢n vá»›i shape cho trÆ°á»›c                                                                                                                                                                                             |
| `_helper.py`                                           | `_append_popular_unseen`, `_user_item_matrix` (gáº§n trÃ¹ng `build_interaction_matrix` nhÆ°ng tá»± suy shape), `_keep_top_neighbors`                                                                                                           |
| `file_hash.py`                                         | `file_hash(path)` â€” hash ná»™i dung file, dÃ¹ng cho provenance cá»§a artifact (`.npz` ItemKNN, `.sqlite` corpus)                                                                                                                              |
| `mapping_hash.py`                                      | `mapping_hash(mapping)` â€” hash cáº£ tÃªn láº«n chá»‰ sá»‘ cá»§a `user2id` / `item2id`, khÃ´ng phá»¥ thuá»™c thá»© tá»± dict                                                                                                                                  |
| `fit_split_names.py`                                   | `fit_split_names(eval_on)` â†’ `["train"]` (validation) hoáº·c `["train", "validation"]` (test); `eval_on` khÃ¡c hai giÃ¡ trá»‹ nÃ y â†’ `ValueError`                                                                                               |
| `fit_provenance.py`                                    | `fit_provenance(fit_pairs, *, user2id, item2id, eval_on, tag)` â†’ dict provenance (`scope`, hash 2 mapping, `eval_on`, `fit_splits`, `tag`); thiáº¿u má»™t trong hai mapping, hoáº·c chá»‰ sá»‘ fit vÆ°á»£t chiá»u mapping â†’ `ValueError`             |
| Há»‡ quáº£:                                                |                                                                                                                                                                                                                                          |

- **`BPRMFRecommender` hiá»‡n chá»‰ dÃ¹ng trong Ä‘Ã¡nh giÃ¡ baseline offline.** `BaselineScorer` Ä‘Ã²i model cÃ³ `.scores`, `.user_items`, `.num_items` â€” chá»‰ há» DataFrame-based cÃ³. Muá»‘n BPR/SASRec lÃ m ranker cho agent thÃ¬ viáº¿t thÃªm má»™t class thoáº£ `CandidateScorer`.
- CÃ¹ng key `eval/baselines.yaml â†’ item_knn.k` Ä‘iá»u khiá»ƒn **cáº£ hai há»**; `block_elements` chá»‰ há» matrix Ä‘á»c. Máº·c Ä‘á»‹nh trong class lá»‡ch YAML (ItemKNN matrix `k=50`, DataFrame `neighbors=20`, BPR `learning_rate` 0.05 so vá»›i 0.001).
- `tune_baselines` chá»‰ cho phÃ©p `popularity`, `item_knn`, `bpr_mf` (khÃ´ng tune `random`).
- **Hai ItemKNN khÃ´ng cho cÃ¹ng thá»© háº¡ng khi bá»‹ cáº¯t top-k:** `ItemKNNRecommender` (DataFrame) vÃ  `ItemKNNMatrixRecommender` cháº¥m Ä‘iá»ƒm theo hai hÆ°á»›ng ngÆ°á»£c nhau (`history @ S` so vá»›i `history @ S.T`) nÃªn chá»‰ khá»›p khi khÃ´ng cáº¯t lÃ¡ng giá»ng (chÃº thÃ­ch trong `recommenders/__init__.py`, test `tests/tools/recommenders/test_contract_recommenders.py`).

**Hardening á»Ÿ snapshot 17/10** (theo diff so vá»›i snapshot 11/10 vÃ  docstring má»›i; chÆ°a tÃ¡i hiá»‡n láº¡i tá»«ng má»¥c): `Recommender` chuáº©n hoÃ¡ ma tráº­n train (`_prepare_train_matrix`: gá»™p trÃ¹ng, bá» sá»‘ 0, tá»« chá»‘i NaN / Ã¢m / khÃ´ng pháº£i ma tráº­n thÆ°a); `recommend` tráº£ `-1` chá»‰ khi Ã­t hÆ¡n k item khuyáº¿n nghá»‹ Ä‘Æ°á»£c; toÃ n Ä‘iá»ƒm há»£p lá»‡ báº±ng 0 thÃ¬ dÃ¹ng popularity lÃ m Ä‘iá»ƒm; `BPRMFRecommender` kiá»ƒm tham sá»‘ vÃ  láº¥y máº«u item Ã¢m Ä‘Ãºng; factory khÃ´ng cÃ²n lá»—i `multiple values for keyword 'seed'`; `PopularityRecommender` (há» DataFrame) kiá»ƒm Ä‘áº§u vÃ o. Váº«n Ä‘Ãºng: `BPRMFRecommender` chÆ°a cÃ³ scorer cho agent.

---

# 8. API layer â€” `package/api/` (trÆ°á»›c lÃ  `package/llm/`)

**Vai trÃ²:** giao diá»‡n thá»‘ng nháº¥t tá»›i LLM; pháº§n cÃ²n láº¡i cá»§a repo chá»‰ biáº¿t `LLMProvider`. Tá»« snapshot 17/10 thÆ° má»¥c Ä‘á»•i tÃªn tá»« `package/llm/` thÃ nh `package/api/` vÃ  khÃ´ng cÃ²n thÆ° má»¥c con `providers/` (khÃ´ng cÃ²n tham chiáº¿u `package.llm` nÃ o trong code). TÃªn `api/` dá»… hiá»ƒu nháº§m lÃ  API serving; thá»±c táº¿ Ä‘Ã¢y lÃ  táº§ng gá»i LLM. Sau refactor má»—i file giá»¯ má»™t public symbol (má»¥c 2.6); docstring cÃ²n trÃ­ch "spec má»¥c XXI" (má»¥c 16.2).

|File|Viá»‡c|
|---|---|
|`llm_provider.py`|`LLMProvider` (ABC): `complete(messages, *, temperature, max_tokens, response_format_json)`, `health_check()`|
|`openai_compatible_provider.py`|`OpenAICompatibleProvider` â€” OpenAI / vLLM / Ollama / LM Studio qua `urllib` (khÃ´ng SDK). `response_format_json=True` â†’ `{"type": "json_object"}`. Lá»—i máº¡ng/timeout/JSON há»ng â†’ `LLMProviderError`. `health_check` gá»­i má»™t request `ping` tháº­t. Docstring cÃ²n ghi chÃº `BLOCKED` (cáº§n endpoint tháº­t) vÃ  nháº¯c `scripts/tools/check_llm_provider.py` Ä‘á»ƒ xÃ¡c nháº­n|
|`build_llm_provider.py`|`build_llm_provider(config)` Ä‘á»c `agent/llm.yaml`; thiáº¿u `base_url` hoáº·c `model` â†’ `ValueError`; provider láº¡ â†’ `ValueError`|
|`_dataclass.py`|`LLMMessage(role, content)`, `LLMResponse(text, raw, prompt_tokens, completion_tokens, latency_seconds, provider_name, model_name, metadata)`|
|`_error.py`|`LLMProviderError`|
|`__init__.py`|export `LLMMessage`, `LLMProviderError`, `LLMProvider`, `build_llm_provider`, `OpenAICompatibleProvider` (`LLMResponse` khÃ´ng Ä‘Æ°á»£c export á»Ÿ cáº¥p `package.api`, import tá»« `package.api._dataclass`)|

KhÃ´ng cÃ³ `MockLLMProvider`; test dÃ¹ng `ScriptedLLM` Ä‘á»‹nh nghÄ©a trong `tests/agents/test_plan_executor.py`. `inference` (má»¥c 9.4) vÃ  `demo` (má»¥c 13.1) cÅ©ng import tá»« `package.api`.

---

# 9. Agent layer â€” `package/agents/`

**Vai trÃ²:** ghÃ©p LLM vÃ  tool. Hiá»‡n cÃ³ hai agent: `PlanExecutor` (LLM viáº¿t toÃ n bá»™ plan má»™t láº§n rá»“i cháº¡y; náº¿u lá»—i thÃ¬ sá»­a plan thÃªm `reflect_rounds` láº§n vá»›i quality gate) vÃ  `Type1Agent` (plan cá»‘ Ä‘á»‹nh, khÃ´ng LLM). **Há»— trá»£ multi-turn conversation qua `Session`**. Káº¿t quáº£ cá»§a agent Ä‘Æ°á»£c `package/inference` (má»¥c 9.4) biáº¿n thÃ nh cÃ¢u tráº£ lá»i cuá»‘i.

## 9.1. CÃ¡ch `PlanExecutor` hoáº¡t Ä‘á»™ng

1. `build_tool_prompt()` biáº¿n má»—i tool thÃ nh `- <name>: <description>` + `input_schema` + `returns` (= `output_schema`); LLM chá»‰ tháº¥y **mÃ´ táº£ vÃ  schema vÃ o/ra**, khÃ´ng tháº¥y code.
2. LLM tráº£ JSON `{"steps": [{"tool": ..., "args": {...}}], "ask_user": null}` (JSON mode). Reply sai Ä‘á»‹nh dáº¡ng â†’ retry tá»‘i Ä‘a `plan_retries` láº§n kÃ¨m thÃ´ng bÃ¡o lá»—i (chá»‰ cho JSON sai, **khÃ´ng** cho lá»—i provider). HÃ ng rÃ o ` ```json ` Ä‘Æ°á»£c tá»± bÃ³c.
3. Plan dÃ i hÆ¡n `max_steps` bá»‹ cáº¯t (`last_truncated = True`).
4. Má»—i step cháº¡y tuáº§n tá»±. Arg tham chiáº¿u output step trÆ°á»›c báº±ng `"$N.path"`, vd `"$1.candidates"`, `"$2.ranked.*.item_id"` (`*` = láº¥y field tá»« má»i pháº§n tá»­ list). **Multi-turn:** cÃ³ thá»ƒ tham chiáº¿u session state báº±ng `"$S.field"` (vd `$S.shown_items`, `$S.candidates`, `$S.ranked`, `$S.constraints`, `$S.shown_items.1` cho item thá»© 2). Chuá»—i tham chiáº¿u pháº£i lÃ  **toÃ n bá»™** giÃ¡ trá»‹ arg.
5. Chá»‘t an toÃ n (tool **khÃ´ng Ä‘Æ°á»£c gá»i** náº¿u vi pháº¡m):
    - tÃªn tool láº¡ â†’ `unknown tool`;
    - `user_id` / `items` / `item_ids` literal **khÃ´ng xuáº¥t hiá»‡n trong cÃ¢u request hoáº·c session** â†’ coi lÃ  bá»‹a id (`invented_ids`);
    - **arg khÃ´ng cÃ³ trong `input_schema`** â†’ lá»—i cÃ³ gá»£i Ã½ (vd `'price_max' belongs inside 'filters'`); tool khÃ´ng khai bÃ¡o schema thÃ¬ khÃ´ng bá»‹ kiá»ƒm tra;
    - ref há»ng hoáº·c arg sai kiá»ƒu â†’ chá»‰ step Ä‘Ã³ lá»—i (`skipped, step N failed`), cÃ¡c step cÃ²n láº¡i váº«n cháº¡y;
    - thiáº¿u thÃ´ng tin â†’ LLM tráº£ `steps: []` kÃ¨m `ask_user` Ä‘á»ƒ há»i láº¡i thay vÃ¬ Ä‘oÃ¡n.
6. Sau `plan()`/`run()`, cÃ¡c thuá»™c tÃ­nh `last_plan`, `last_question`, `last_response`, `last_usage` (token, latency, sá»‘ láº§n thá»­; cá»™ng dá»“n má»i láº§n gá»i LLM, reflect gá»“m cáº£), `last_truncated` mÃ´ táº£ request gáº§n nháº¥t.
7. **Plan-reflect** (`reflect_rounds`, máº·c Ä‘á»‹nh 1; 0 = táº¯t): náº¿u plan cháº¡y xong nhÆ°ng cÃ³ step lá»—i, hoáº·c khÃ´ng ra item nÃ o (vÃ  khÃ´ng pháº£i `ask_user`), `run()` gá»­i cho LLM bÃ¡o cÃ¡o tá»«ng step (`_step_report`, lá»—i cáº¯t `reflect_error_chars` kÃ½ tá»±, máº·c Ä‘á»‹nh 300) rá»“i cháº¡y plan Ä‘Ã£ sá»­a, tá»‘i Ä‘a `reflect_rounds` láº§n. **KhÃ´ng reflect** khi cÃ³ step dÃ¹ng id bá»‹a hoáº·c cháº¡m time budget SQL (plan má»›i khÃ´ng giÃºp Ã­ch: `_blocks_reflect`). **Quality gate:** reflection chá»‰ Ä‘Æ°á»£c cháº¥p nháº­n náº¿u cáº£i thiá»‡n quality (fewer failed steps, more items, fewer error kinds). Reply reflect khÃ´ng dÃ¹ng Ä‘Æ°á»£c (hoáº·c lá»—i provider lÃºc reflect) thÃ¬ bá»‹ bá» vÃ  giá»¯ káº¿t quáº£ trÆ°á»›c. Thuá»™c tÃ­nh thÃªm: `last_reflections` (sá»‘ lÆ°á»£t Ä‘Ã£ dÃ¹ng, reply há»ng cÅ©ng tÃ­nh), `last_first_attempt_ok`, `last_attempt_plans`.
8. **Session update:** sau má»—i turn thÃ nh cÃ´ng, PlanExecutor cáº­p nháº­t Session vá»›i turns, shown_items, candidates, ranked (method `_update_session`).

`output_schema` cá»§a má»—i tool Ä‘Æ°á»£c render vÃ o prompt (dÃ²ng `returns:`) Ä‘á»ƒ LLM biáº¿t tÃªn field há»£p lá»‡ cho `$N.path`; nÃ³ **chÆ°a** Ä‘Æ°á»£c dÃ¹ng Ä‘á»ƒ kiá»ƒm tra ref lÃºc cháº¡y (`_resolve_path` duyá»‡t káº¿t quáº£ tháº­t).

## 9.2. `Type1Agent`

KhÃ´ng LLM, chuá»—i cá»‘ Ä‘á»‹nh: `ItemCFTool` (láº¥y `max(top_k Ã— candidate_multiplier, min_candidates)` candidate quanh seed; máº·c Ä‘á»‹nh 5 vÃ  50 trong `agent.yaml â†’ type1`) â†’ `RecoModelTool` (xáº¿p háº¡ng cho `user_id`) â†’ `QueryTool` (gáº¯n metadata). BÆ°á»›c nÃ o lá»—i tráº£ `{"ok": False, "stage": "retrieve"|"rank"|"fetch", "error": â€¦}`. Chá»‰ Ã¡p dá»¥ng cho request kiá»ƒu `similar` (cáº§n seed item).

## 9.3. Tá»«ng file

|File|Viá»‡c|
|---|---|
||`planner/plan_executor.py`|`PlanExecutor` (má»¥c 9.1). Giá»›i háº¡n máº·c Ä‘á»‹nh tá»« `agent/agent.yaml`, ghi Ä‘Ã¨ Ä‘Æ°á»£c qua tham sá»‘. Má»—i entry step nay cÃ³ thÃªm `error_kind` (`unknown_tool` / `invented_id` / `unknown_args` / `tool_error` / `bad_reference` / `exception`). CÃ³ method `_update_session()` Ä‘á»ƒ cáº­p nháº­t session sau má»—i turn|
||`session.py`|`Session`: quáº£n lÃ½ state multi-turn conversation (turns, shown_items, candidates, ranked, constraints, feedback). _Turn (internal dataclass): 1 lÆ°á»£t há»™i thoáº¡i. Limits (max_turns, max_shown_items, max_candidates, max_turn_chars). Methods: `add_turn`, `add_shown_items`, `set_candidates`, `update_constraints`, `add_exclusions`, `add_feedback`, `get_valid_ids`, `reset`, `to_dict`|
|`planner/_prompt.py`|`SYSTEM_PROMPT` cá»§a planner: luáº­t (chá»‰ dÃ¹ng tool/arg cÃ³ sáºµn, khÃ´ng bá»‹a id, cÃ¡ch viáº¿t ref, luÃ´n rank báº±ng `RecoModelTool` rá»“i fetch báº±ng `QueryTool`, thiáº¿u thÃ´ng tin thÃ¬ `ask_user`) + má»™t vÃ­ dá»¥. Chá»‰ nháº¯c `ItemCFTool`, `SemanticSearchTool`, `RecoModelTool`, `QueryTool`|
|`planner/_schema.py`|ngá»¯ phÃ¡p tham chiáº¿u `_REF` vÃ  `ID_ARG_KEYS = (user_id, items, item_ids)`|
|`planner/_helper.py`|`_extract_plan`, `_resolve_refs`/`_resolve_path`, `_invented_ids`, `_unknown_args`; cho plan-reflect: `_is_time_budget`, `_is_bad_reference`, `_blocks_reflect`, `_reflect_problem`, `_step_report`; hÃ m cÃ´ng khai `check_time_budget_error` (dÃ¹ng chung vá»›i `layer5_deployment`)|
|`type1/type1_agent.py`|`Type1Agent` (má»¥c 9.2)|
|`toolkit/agent_tools.py`|`AgentTools`: **nÆ¡i duy nháº¥t liá»‡t kÃª tool cho agent**; `for_planner()` (5 tool: item_cf, reco, query, search, sql), `for_planner_memory()` (+ `MemoryTool`)|
|`toolkit/build_tools.py`|`build_tools(knn, scorer, user2id, item2id, interactions, corpus, â€¦)` â†’ `AgentTools`|
|`toolkit/build_tool_prompt.py`|tool â†’ text cho system prompt (render `input_schema` vÃ  `returns` = `output_schema`)|
|`results/extract_recommendations.py`|"ngÆ°á»i dÃ¹ng thá»±c sá»± tháº¥y gÃ¬": Æ°u tiÃªn `ranked` cá»§a `RecoModelTool` > retrieval > `QueryTool`. Chuyá»ƒn tá»« `agents/evaluation/` sang Ä‘Ã¢y Ä‘á»ƒ `inference`, `evaluation` dÃ¹ng chung mÃ  khÃ´ng vi pháº¡m hÆ°á»›ng phá»¥ thuá»™c|
|`_schema.py`|`TEMPLATES`: cÃ¢u request máº«u theo ngÃ´n ngá»¯ (`vi` / `en`) vÃ  kind â€” dÃ¹ng bá»Ÿi `evaluation/agent/build_requests.py` vÃ  `demo/samples/sample_requests.py`|
|`_limits.py`|`AgentLimits` tá»« `agent/agent.yaml` (validate; gá»“m `reflect_rounds â‰¥ 0`, `reflect_error_chars`, `type1_candidate_multiplier`, `type1_min_candidates`)|
|`__init__.py`|export `PlanExecutor`, `Type1Agent`, `AgentTools`, `build_tools`, `build_tool_prompt`, `extract_recommendations`, `get_agent_limits`, `TEMPLATES`|

(`package/evaluation/agent/` á»Ÿ má»¥c 10.3, `package/evaluation/ablation/` á»Ÿ má»¥c 10.4, `package/inference/` á»Ÿ má»¥c 9.4. ThÆ° má»¥c `agents/ablation/` vÃ  `agents/evaluation/` cÃ²n sÃ³t láº¡i trong zip nhÆ°ng **rá»—ng** â€” chá»‰ cÃ³ `__pycache__`.)

## 9.4. Inference â€” cÃ¢u tráº£ lá»i cuá»‘i (`package/inference/`)

**Vai trÃ²:** bÆ°á»›c _trÃ¬nh bÃ y_. Nháº­n káº¿t quáº£ agent Ä‘Ã£ chá»n vÃ  viáº¿t cÃ¢u tráº£ lá»i cho ngÆ°á»i dÃ¹ng; **khÃ´ng chá»n láº¡i, khÃ´ng thÃªm / bá»›t / Ä‘á»•i thá»© tá»± item**. KhÃ´ng pháº£i vÃ²ng láº·p "quan sÃ¡t káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿" (má»¥c 15). Config: `agent/inference.yaml`.

Luá»“ng: káº¿t quáº£ agent â†’ `outcome_from_*` â†’ `AgentOutcome` â†’ `classify_outcome` (status) â†’ `compose_answer` â†’ `Answer`.

|File|Viá»‡c|
|---|---|
|`_dataclass.py`|`AgentOutcome(request_text, items, question, errors, invented_ids, cold_start, n_steps)` â€” agent Ä‘Ã£ lÃ m gÃ¬; `Answer(status, text, items, grounded, composer, fallback_reason, usage, reason)` â€” ngÆ°á»i dÃ¹ng tháº¥y gÃ¬|
|`outcome/outcome_from_plan_results.py`|káº¿t quáº£ `PlanExecutor.run()` â†’ `AgentOutcome`: item = `extract_recommendations(...)` (tá»« `agents/results/`; cÃ¹ng id, cÃ¹ng thá»© tá»± vá»›i `trajectory["recommended"]`), bá» trÃ¹ng, cáº¯t `max_items`; metadata láº¥y tá»« output tool (`QueryTool` trÆ°á»›c, rá»“i dÃ²ng cá»§a search / ranker), khÃ´ng bá»‹a; lá»—i tool vÃ  lá»—i planner vÃ o `errors`|
|`outcome/outcome_from_type1.py`|output `Type1Agent.recommend()` â†’ `AgentOutcome`|
|`outcome/classify_outcome.py`|status theo luáº­t, khá»›p Ä‘áº§u tiÃªn tháº¯ng: `ask_user` (cÃ³ cÃ¢u há»i vÃ  0 step) â†’ `tool_error` (id bá»‹a; lá»—i planner) â†’ `ok` (cÃ³ item; náº¿u cÃ³ tool lá»—i thÃ¬ ghi `partial: â€¦ failed`) â†’ `tool_error` (cÃ³ lá»—i mÃ  khÃ´ng cÃ³ item) â†’ `no_result`|
|`compose/compose_template.py`|cÃ¢u tráº£ lá»i **táº¥t Ä‘á»‹nh, khÃ´ng LLM**: vÄƒn báº£n cá»‘ Ä‘á»‹nh (tiáº¿ng Viá»‡t) cho `no_result` / `tool_error`, cÃ¢u há»i cá»§a planner cho `ask_user`, danh sÃ¡ch Ä‘Ã¡nh sá»‘ cho `ok` (giÃ¡, rating, store náº¿u cÃ³)|
|`compose/compose_llm.py`|LLM viáº¿t (JSON `{answer, mentioned_item_ids}`), kiá»ƒm grounding, retry `llm_retries` láº§n kÃ¨m lÃ½ do; háº¿t lÆ°á»£t hoáº·c lá»—i provider thÃ¬ lÃ¹i vá» template (`fallback_reason`). **KhÃ´ng nÃ©m lá»—i**. Chá»‰ status `ok` má»›i gá»i LLM|
|`compose/compose_answer.py`|Ä‘iá»ƒm vÃ o `compose_answer(outcome, llm=None, mode=â€¦)`: mode `template`, status khÃ¡c `ok` hoáº·c `llm=None` â‡’ khÃ´ng gá»i LLM (`fallback_reason="no_llm"`)|
|`compose/item_view.py`, `compose/cut_title.py`|`item_view`: item nhÆ° LLM nhÃ¬n tháº¥y; `cut_title`: cáº¯t tiÃªu Ä‘á» cÃ²n `title_chars` (máº·c Ä‘á»‹nh 120) kÃ½ tá»±, thÃªm `â€¦`|
|`compose/_prompt.py`|system prompt + cÃ¡c cÃ¢u cá»‘ Ä‘á»‹nh (tiáº¿ng Viá»‡t)|
|`grounding/check_grounding.py`, `grounding/parse_llm_reply.py`, `grounding/_helper.py`|`parse_llm_reply`; `check_grounding` (JSON há»£p lá»‡, id cÃ³ trong dá»¯ liá»‡u, Ä‘á»§ item vÃ  Ä‘Ãºng thá»© tá»±; náº¿u `check_numbers` thÃ¬ giÃ¡ / rating trong cÃ¢u khÃ´ng lá»‡ch quÃ¡ `price_tolerance`); `ids_in_text` vÃ  trÃ­ch giÃ¡ / rating (ná»™i bá»™)|
|`cut.py`, `empty_usage.py`|`cut`: cáº¯t lÃ½ do / lá»—i cÃ²n `reason_chars` (máº·c Ä‘á»‹nh 300) kÃ½ tá»±; `empty_usage`: dict usage rá»—ng|
|`_schema.py`, `_limits.py`|`ITEM_FIELDS`, `STATUSES = (ok, ask_user, no_result, tool_error)`, `MODES = (llm, template)`; `InferenceLimits` tá»« `agent/inference.yaml` (validate)|
|`__init__.py`|export `compose_answer`, `compose_llm`, `compose_template`, `classify_outcome`, `outcome_from_plan_results`, `outcome_from_type1`, `empty_usage`, `AgentOutcome`, `Answer`, `MODES`, `get_inference_limits`|
|**Trong Ä‘Ã¡nh giÃ¡:** `run_agent_eval.py --inference-mode llm|template`gáº¯n cÃ¢u tráº£ lá»i vÃ o trajectory cá»§a`type1`,` planner`,` planner_memory `(`INFERENCE_AGENTS`; baseline khÃ´ng cÃ³). VÃ¬ chá»‰ trÃ¬nh bÃ y nÃªn` recommended`,` task_success`, recallâ€¦ **khÃ´ng Ä‘á»•i**; cÃ¢u tráº£ lá»i Ä‘Æ°á»£c cháº¥m báº±ng cá»™t riÃªng (má»¥c 10.3).` --resume` khÃ´ng trá»™n cÃ¢u tráº£ lá»i LLM vÃ  template trong má»™t thÃ­ nghiá»‡m.|

**Äiá»u cáº§n biáº¿t:** `docs/inference_contract.md` mÃ  báº£n cÅ© trÃ­ch **khÃ´ng tá»“n táº¡i** (má»¥c 16); luá»“ng vÃ  báº£ng Ã¡nh xáº¡ status náº±m ngay trong code â€” `outcome/classify_outcome.py` vÃ  `_schema.STATUSES`. `demo` **Ä‘Ã£** gá»i `compose_answer` (má»¥c 13.1).

---

# 10. Evaluation

CÃ³ **bá»‘n** loáº¡i Ä‘Ã¡nh giÃ¡: ba loáº¡i Ä‘áº§u tráº£ lá»i ba cÃ¢u há»i vá» mÃ´ hÃ¬nh / agent, loáº¡i thá»© tÆ° so sÃ¡nh cÃ¡c láº§n cháº¡y.

|Loáº¡i|CÃ¢u há»i|Script|Cáº§n LLM?|
|---|---|---|---|
|Offline recommender|Model nÃ o gá»£i Ã½ tá»‘t hÆ¡n trÃªn split?|`run_baselines`, `tune_baselines`|khÃ´ng|
|Candidate recall|Retrieval cÃ³ Ä‘Æ°a item held-out vÃ o tay reranker khÃ´ng?|`candidate_recall`|khÃ´ng|
|Agent eval|Táº§ng agent cÃ³ thÃªm giÃ¡ trá»‹ so vá»›i recommender thuáº§n khÃ´ng, vÃ  á»Ÿ Ä‘Ã¢u?|`run_agent_eval`|cÃ³ (trá»« `baseline`, `type1`)|
|So sÃ¡nh cÃ¡c láº§n cháº¡y (ablation)|Cáº¥u hÃ¬nh A cÃ³ hÆ¡n B khÃ´ng, cÃ³ Ã½ nghÄ©a thá»‘ng kÃª khÃ´ng?|`compare_experiments`|khÃ´ng (chá»‰ Ä‘á»c `exp_NNN`)|

## 10.1. Offline recommender â€” `package/tools/evaluation/`

(Náº±m trong `tools/` nhÆ°ng **khÃ´ng pháº£i Tool** â€” chá»‰ lÃ  bá»™ Ä‘Ã¡nh giÃ¡ offline.)

|File|Viá»‡c|
|---|---|
|`evaluate_recommender.py`|`evaluate_recommender(model, exclude, target, ks, sparse_max)` â†’ `EvaluationResult`: metric tá»•ng + theo segment cold/sparse/warm, `catalog_coverage@k`, `target_item_seen_ratio` (Ä‘Æ°á»ng chÃ­nh, há» matrix-based)|
|`metrics/`|`ranking_metrics_at_k(hits, num_relevant, k)`: precision/recall/hit-rate/NDCG/MRR/MAP@k vectorised, má»—i metric má»™t file (`recall_at_k.py`, `precision_at_k.py`, `hit_rate_at_k.py`, `ndcg_at_k.py`, `mrr_at_k.py`, `average_precision_at_k.py`, gá»™p bá»Ÿi `ranking_metrics_at_k.py`; cÅ©ng Ä‘Æ°á»£c `score_trajectory` cá»§a agent eval dÃ¹ng)|
|`evaluate_ranking.py`|`evaluate_ranking(model, interactions_df, ks)`: cÃ¹ng cÃ¡c metric nhÆ°ng vÃ²ng láº·p tá»«ng user, cho há» DataFrame-based; **chá»‰ dÃ¹ng trong test**|
|`_dataclass.py`|`EvaluationResult`|
|`_helper.py`|`assign_segments` (cold = 0 history, sparse â‰¤ `sparse_max`, warm), `_git_commit`|
|`segment_users_by_history.py`|`segment_users_by_history(users, history_sizes, sparse_max)` â†’ `{user_idx: segment}` theo sá»‘ interaction trong dá»¯ liá»‡u fit|
|`select_fit_target.py`|giao thá»©c fit/target dÃ¹ng chung: `validation` â†’ fit = train; `test` â†’ fit = train + validation|
|`save_experiment.py`|ghi `exp_NNN/{config.yaml, metrics.json, README.md}` (kÃ¨m git commit, pháº§n cá»©ng, seed, thá»i gian cháº¡y)|
|`next_experiment_dir.py`|tÃªn thÆ° má»¥c `exp_NNN` káº¿ tiáº¿p|
|`parameter_grid.py` / `merge_model_params.py`|khai triá»ƒn lÆ°á»›i tham sá»‘ / ghi Ä‘Ã¨ tham sá»‘ cá»§a má»™t model trong config baseline|
|`hardware_info.py`|platform, python, sá»‘ CPU|
|`evaluation_protocol.py`|`evaluation_protocol(..., eval_on, tag, fit_df, target_df, user2id, item2id, segments, sampled, metadata_policy, evaluation_kind)`: báº¯t fit **hoÃ n toÃ n trÆ°á»›c** target theo timestamp, cutoff metadata pháº£i báº±ng `target.min`, rá»“i tráº£ dict mÃ´ táº£ protocol (provenance ItemKNN, chÃ­nh sÃ¡ch label / cohort / history, cá»¡ máº«u theo segment)|
|`normalize_query_text.py`|`normalize_query_text(query, mode)`: `raw` (nguyÃªn vÄƒn) hoáº·c `ascii_fold` (bá» dáº¥u, kÃ½ tá»± > ASCII â†’ space); mode khÃ¡c â†’ `ValueError`|
|`ranking_run_store.py`|`RankingRunStore`: checkpoint SQLite + lock file cho ranking eval; `append` theo stream pháº£i lÃ  **tiá»n tá»‘ liá»n máº¡ch** (trÃ¹ng / lá»— há»•ng â†’ fail atomic), `rows` Ä‘á»c theo keyset, cÃ³ `export`, `timing`, `close`|
|`ranking_stream_summary.py`|`RankingStreamSummary`: cá»™ng dá»“n candidate + scored row thÃ nh metric retrieval / ranking, p50 / p95 latency theo segment, Ä‘áº¿m health vÃ  error|
|`stage_progress.py`|`StageProgress`: in tiáº¿n Ä‘á»™ `committed/total`, rate vÃ  ETA cho cÃ¡c vÃ²ng cháº¡y dÃ i|

## 10.2. Candidate recall â€” `scripts/evaluation/candidate_recall.py`

Vá»›i má»—i user máº«u, má»—i nguá»“n candidate (`popularity`, `item_cf`, `semantic`, `union`) tráº£ N item; loáº¡i item user Ä‘Ã£ cÃ³; Ä‘áº¿m bao nhiÃªu item held-out xuáº¥t hiá»‡n. CÃ¢u query cá»§a `semantic` Ä‘Æ°á»£c mÃ´ phá»ng báº±ng `history` (title item gáº§n nháº¥t â€” trung thá»±c nhÆ°ng rá»—ng vá»›i cold user) hoáº·c `category_oracle` (category cá»§a item held-out â€” **cáº­n trÃªn, khÃ´ng bÃ¡o cÃ¡o nhÆ° káº¿t quáº£ tháº­t**).

## 10.3. Agent eval â€” `package/evaluation/` (+ `requests/`)

Dá»±ng request giáº£ láº­p tá»« dá»¯ liá»‡u held-out (offline khÃ´ng cÃ³ query log tháº­t), gá»­i **cÃ¹ng táº­p request** cho tá»«ng agent, cháº¥m Ä‘iá»ƒm.

|File|Viá»‡c|
|---|---|
|`_schema.py`|`AGENTS`, `PLANNER_AGENTS`, `KIND_SEGMENTS`, `KINDS`, `ORACLE_KINDS`, `REFERENCE_PLANS` (nhÃ³m tool má»™t plan tá»‘t Ä‘i qua theo tá»«ng kind), `INFERENCE_AGENTS` (agent cÃ³ cÃ¢u tráº£ lá»i: type1, planner, planner_memory), `ANSWER_STATUSES` (láº·p láº¡i cá»§a `inference._schema.STATUSES`, cÃ³ test giá»¯ báº±ng nhau); `TEMPLATES` (cÃ¢u request) Ä‘Ã£ chuyá»ƒn sang `agents/_schema.py`; sau refactor `evaluation` Ä‘Æ°á»£c phÃ©p import `inference` nÃªn báº£n láº·p `ANSWER_STATUSES` cÃ³ thá»ƒ bá»|
|`requests/_dataclass.py`|`AgentRequest` (kind, segment, text, user, seed, targets, price_max, category, `oracle`); cÃ³ `to_dict()`|
|`requests/build_requests.py`|sinh request theo seed cá»§a `rng`; `constrained` láº¥y giÃ¡/category tá»« item held-out; `requests/filter_requests_by_scope.py` chá»n `realistic` hay `oracle` theo scope|
|`requests/reference_groups.py`|`reference_groups(kind, available_tools)`: cÃ¡c nhÃ³m tool cá»§a plan tham chiáº¿u (`REFERENCE_PLANS`) cÃ²n láº¡i sau khi lá»c theo tool agent cÃ³; dÃ¹ng trong `score_trajectory` cho `tool_selection_ok`|
|`agents/results/extract_recommendations.py`|"ngÆ°á»i dÃ¹ng thá»±c sá»± tháº¥y gÃ¬": Æ°u tiÃªn `ranked` cá»§a `RecoModelTool` > retrieval > `QueryTool`|
|`score_trajectory.py` (nay á»Ÿ gá»‘c `package/evaluation/`, ghÃ©p 5 lá»›p `score_layer1â€¦5`)|cháº¥m má»™t trajectory: metric xáº¿p háº¡ng, `tool_selection_ok`, `constraint_satisfaction`, `invented_ids`, `asked_clarification`, `task_success`, token/latency. Lá»—i tÃ­nh lÃ  0 chá»© khÃ´ng bá» máº«u; thÃªm cá»™t cÃ¢u tráº£ lá»i `answer_status_<status>`, `answer_grounded`, `answer_fallback`, `inference_{attempts,prompt_tokens,completion_tokens,latency_seconds}` (None khi trajectory khÃ´ng cÃ³ answer: baseline hoáº·c báº£n ghi cÅ©)|
|`summarize.py` (nay á»Ÿ gá»‘c `package/evaluation/`)|gá»™p theo agent â†’ kind â†’ segment (`all` = má»i segment)|
|`requests/_helper.py`|tra corpus: giÃ¡, category sÃ¢u nháº¥t, `items_satisfying`, `items_without_price`|

**5 lá»›p scoring (`layer1_outcome/` â€¦ `layer5_deployment/`)** â€” `score_trajectory` gá»i tá»«ng lá»›p rá»“i ghÃ©p thÃ nh má»™t hÃ ng pháº³ng:

|File|Viá»‡c|
|---|---|
|`layer1_outcome/layer1_outcome.py`|`score_layer1_outcome(request, trajectory, *, item2id, k, seen_item_ids)` â€” metric xáº¿p háº¡ng trÃªn `recommended` so vá»›i `targets`|
|`layer2_interaction/layer2_interaction.py`|`score_layer2_interaction(request, trajectory, *, corpus)` â€” `task_success` (v2: `plan_valid` âˆ§ `steps_ok` âˆ§ cÃ³ item âˆ§ thoáº£ rÃ ng buá»™c; `ambiguous` = há»i láº¡i), `constraint_satisfaction`|
|`layer3_grounding/layer3_grounding.py`|`score_layer3_grounding(trajectory)` â€” `answer_status_*`, `answer_grounded`, `answer_fallback` (None khi trajectory khÃ´ng cÃ³ answer)|
|`layer4_process/layer4_process.py`|`score_layer4_process(request, trajectory)` â€” `plan_valid`, `plan_attempts`, `plan_truncated`, `n_steps`, `steps_ok_rate`, `invented_ids`, `reflections`, `tool_selection_ok` (qua `_helper.check_tool_selection`)|
|`layer5_deployment/layer5_deployment.py`|`score_layer5_deployment(trajectory)` â€” token, `llm_latency_seconds`, `tool_latency_seconds`, `wall_seconds`, `inference_*`|
|`layer*/_schema.py`|háº±ng tÃªn cá»™t cá»§a tá»«ng lá»›p|

**Component benchmark â€” `package/evaluation/component/`** (Ä‘o tá»«ng component tÃ¡ch rá»i, khÃ´ng cáº§n LLM tháº­t / dá»¯ liá»‡u tháº­t):

|File|Viá»‡c|
|---|---|
|`_evaluator.py`|`ComponentEvaluator`: subclass cÃ i `run_component` / `score_component`; `run_case`, `run_benchmark(cases, runs, component_name, git_sha)`|
|`_schema.py`|`BenchmarkCase`, `BenchmarkResult`, `BenchmarkSummary`, `RegressionReport` (+ `to_dict` / `from_dict`)|
|`_loader.py`|`load_cases`, `save_cases`, `filter_cases_by_tag`, `filter_cases_by_metadata` (JSON / JSONL)|
|`_regression.py`|`compare_benchmarks` (ngÆ°á»¡ng 5% metric / 10% latency), `format_regression_report`|
|`run.py`, `run_all.py`|CLI cháº¡y má»™t benchmark / cháº¡y táº¥t cáº£ rá»“i gá»™p `unified_report` (`.json` + `.md`)|
|`link_e2e.py`|`link_component_to_e2e`, `create_traceback_tool` â€” ná»‘i Ä‘iá»ƒm component vá»›i lá»—i trajectory end-to-end|
|`benchmarks/planner_benchmark.py`, `planner_mock_llm.py`, `planner_mock_tools.py`|`PlannerBenchmark` trÃªn LLM + tool giáº£: chá»n tool, arg, schema, ref `$N.path`, rÃ ng buá»™c|
|`benchmarks/executor_benchmark.py`, `executor_mock_tools.py`|`ExecutorBenchmark` (executor + reflection) trÃªn tool giáº£ Ä‘iá»u khiá»ƒn Ä‘Æ°á»£c (fail / timeout / rá»—ng / sai schema)|
|`benchmarks/grounding_benchmark.py`|`GroundingBenchmark` â€” cháº¥m claim-level báº±ng Jev (`jev_product_evaluator`)|
|`benchmarks/integration_benchmark.py`|`IntegrationBenchmark` â€” kiá»ƒm ranh giá»›i giá»¯a cÃ¡c component|
|`benchmarks/memory_correctness_evaluator.py`, `memory_oracle.py`, `memory_correctness_setup.py`, `build_memory_correctness_dataset.py`|`MemoryCorrectnessEvaluator` cháº¥m theo **oracle Ä‘á»™c láº­p** (`compute_memory_oracle`, `leakage_probe`; oracle **khÃ´ng** import `MemoryTool`/`ItemCorpus`); script sinh dataset vÃ  `--check` phÃ¡t hiá»‡n lá»‡ch|
|`benchmarks/memory_utility.py`|phÃ¢n tÃ­ch **utility** ghÃ©p cáº·p nhiá»u run `planner` vs `planner_memory` (khÃ´ng gá»i LLM; nhÃ³m chá»‰ 1 run â†’ khÃ´ng káº¿t luáº­n)|
|`benchmarks/*.jsonl`|dataset: `planner`, `executor`, `grounding`, `integration`, `memory_correctness` (+ `dummy_memory_dataset.jsonl`)|
|`README.md`, `benchmarks/planner_README.md`|cÃ¡ch cháº¡y benchmark component|

**Cháº©n Ä‘oÃ¡n & judge:**

|File|Viá»‡c|
|---|---|
|`diagnostics/failure_rates.py`|`failure_rates(rows)` â€” tá»‰ lá»‡ lá»—i theo agent Ã— kind (gá»“m `answer_status_tool_error_rate`)|
|`diagnostics/error_taxonomy.py`|`error_taxonomy(trajectories)` â€” phÃ¢n loáº¡i lá»—i step / plan theo agent Ã— kind|
|`diagnostics/reflection_diagnostics.py`|`reflection_diagnostics(rows)` â€” hÃ nh vi reflection (láº§n Ä‘áº§u lá»—i, sá»‘ lÆ°á»£t, â€¦)|
|`judge/jev_client.py`|`JevClient` (TypeSafe AI): `evaluate`, `evaluate_noul`, `evaluate_choice`, `evaluate_score`|
|`jev_product_evaluator.py`|`evaluate_product_reply_with_jev(...)` â€” faithfulness (claim â†’ Noul) + communication (Score theo rubric); Ä‘á»c `configs/eval/judge.yaml`|
|`product_reply_evaluator.py`|`evaluate_product_reply(...)` â€” báº£n khÃ´ng cáº§n Jev|
|`build_run_provenance.py`|`build_run_provenance(planner_tools, memory_tools)` â€” hash prompt / tool schema / git state / limits cá»§a má»™t láº§n cháº¡y|

|Kind|Dá»±ng tá»«|Ghi chÃº|
|---|---|---|
|`similar`|item gáº§n nháº¥t trong history|trung thá»±c|
|`personalized`|chá»‰ history|trung thá»±c; cÃ´ láº­p tÃ¡c dá»¥ng cá»§a `MemoryTool`|
|`constrained`|category + giÃ¡ cá»§a item held-out|**ORACLE** (cáº­n trÃªn)|
|`cold_text`|category cá»§a item held-out|**ORACLE**|
|`ambiguous`|cÃ¢u mÆ¡ há»“ ("CÃ³ gÃ¬ má»›i khÃ´ng?")|thÃ nh cÃ´ng = agent **há»i láº¡i** thay vÃ¬ bá»‹a id|
||`exclusion`|exclude categories + items|trung thá»±c; kiá»ƒm tra kháº£ nÄƒng lá»c|
||`unanswerable`|query báº¥t kháº£ thi|trung thá»±c; kiá»ƒm tra xá»­ lÃ½ trÆ°á»ng há»£p null|

Bá»‘n agent so sÃ¡nh: `baseline` (ItemKNN, khÃ´ng LLM), `type1` (plan cá»‘ Ä‘á»‹nh, chá»‰ cho `similar`), `planner` (LLM + 4 tool), `planner_memory` (planner + `MemoryTool`).

**Plan-reflect trong eval:** trajectory cá»§a planner cÃ³ thÃªm `reflections` (sá»‘ lÆ°á»£t reflect), `first_attempt_ok` (láº§n cháº¡y Ä‘áº§u khÃ´ng lá»—i step vÃ  ra item hoáº·c há»i láº¡i) vÃ  `reflect_rounds` (giÃ¡ trá»‹ lÃºc cháº¡y; `--resume` chá»‰ dÃ¹ng láº¡i trajectory cÃ¹ng `reflect_rounds`). `steps` trong trajectory lÃ  cá»§a láº§n cháº¡y **cuá»‘i**, vÃ  `task_success` cháº¥m trÃªn káº¿t quáº£ cuá»‘i. Cá» `--reflect-rounds` ghi Ä‘Ã¨ `agent.reflect_rounds`. Script phÃ¢n tÃ­ch lá»—i theo tool `analyze_agent_failures.py` cÃ³ á»Ÿ báº£n 12/10 nhÆ°ng **khÃ´ng cÃ³ trong zip 17/10** (má»¥c 11.1).

**CÃ¢u tráº£ lá»i (Inference) trong eval:** `--inference-mode` (máº·c Ä‘á»‹nh láº¥y tá»« `inference.mode`) quyáº¿t Ä‘á»‹nh `llm` (LLM viáº¿t, kiá»ƒm grounding, lá»—i thÃ¬ dÃ¹ng template; tá»‘i Ä‘a `1 + llm_retries` láº§n gá»i thÃªm cho má»—i request Ä‘Æ°á»£c tráº£ lá»i) hay `template` (táº¥t Ä‘á»‹nh, khÃ´ng gá»i LLM). Trajectory cÃ³ thÃªm `answer`, `answer_status`, `answer_grounded`, `answer_composer`, `answer_fallback`, `answer_reason`, `inference_usage`, `inference_mode`; `inference_usage` tÃ¡ch riÃªng vá»›i `usage` cá»§a planner. Báº£n ghi cÅ© khÃ´ng cÃ³ cÃ¡c trÆ°á»ng nÃ y váº«n Ä‘Æ°á»£c dÃ¹ng láº¡i khi `--resume` (cá»™t answer Ä‘á»ƒ trá»‘ng).

## 10.4. So sÃ¡nh nhiá»u láº§n cháº¡y (ablation) â€” `package/evaluation/ablation/`

**Vai trÃ²:** so sÃ¡nh cÃ¡c thÃ­ nghiá»‡m `agent_eval` (`exp_NNN`) theo "nhÃ³m cáº¥u hÃ¬nh" (vÃ­ dá»¥ `reflect_rounds` 0 vÃ  1, má»—i nhÃ³m nhiá»u láº§n láº·p): Ä‘á»c `scored.jsonl` vÃ  `config.yaml` cá»§a tá»«ng exp, ghÃ©p cáº·p theo `request_id`, kiá»ƒm tÆ°Æ¡ng thÃ­ch config, trung bÃ¬nh qua cÃ¡c láº§n láº·p trong nhÃ³m, rá»“i bÃ¡o chÃªnh lá»‡ch theo kind Ã— segment Ã— metric kÃ¨m khoáº£ng tin cáº­y; metric nhá»‹ phÃ¢n cÃ³ thÃªm McNemar. Config: `agent/ablation.yaml` (nay **Ä‘Ã£ khai bÃ¡o** `groups` tháº­t: `reflect_0: [exp_012]`, `reflect_1: [exp_013]`, `infer_template: [exp_011]`; 6 `contrasts`; `output_subdir: agent_eval/ablation`). Script: `scripts/experiments/compare_experiments.py`. `docs/ablation_protocol.md` **khÃ´ng tá»“n táº¡i** trong repo vÃ  khÃ´ng cÃ²n chá»— nÃ o trÃ­ch tá»›i (má»¥c 16).

|File|Viá»‡c|
|---|---|
|`_limits.py`|`AblationLimits` tá»« `agent/ablation.yaml`|
|`_loader.py`|`load_scored_data`, `load_config_data`, `load_group_data`, `validate_contrast_config`, `check_compatibility`|
|`_compare.py`|`pair_by_request_id`, `average_across_runs`, `compute_metric_diff`, `compute_binary_disagreement`, `compare_two_groups`, `find_disagreements`|
|`_statistics.py`|`bootstrap_ci` (khoáº£ng tin cáº­y cho trung bÃ¬nh), `mcnemar_test` (xáº¥p xá»‰ chi-bÃ¬nh-phÆ°Æ¡ng; tráº£ `None` náº¿u sá»‘ cáº·p báº¥t nháº¥t `b + c < 10`; p-value **thÃ´**, chá»‰ láº¥y má»™t trong 4 má»©c 1.0 / 0.05 / 0.01 / 0.001)|
|`_report.py`|`render_markdown_report`, `write_csv`, `write_json`, `write_disagreements` (â†’ `disagreements.jsonl`)|

`compare_experiments.py` nay import Ä‘Ãºng `package.evaluation.ablation` (lá»—i import trÆ°á»›c refactor Ä‘Ã£ háº¿t; `test_import_resolution.py` cháº·n lá»—i loáº¡i nÃ y). `_compare.py` Ä‘Ã£ dÃ¹ng `kind_key` á»Ÿ nhÃ¡nh ghi káº¿t quáº£ McNemar; lá»—i `king_key` cá»§a báº£n 17/10 Ä‘Ã£ háº¿t (xÃ¡c nháº­n trong snapshot 20/10).

---

# 11. Scripts â€” `scripts/`

Script cháº¡y trá»±c tiáº¿p tá»« gá»‘c `src/`: `PYTHONPATH=. python scripts/<thÆ° má»¥c>/<tÃªn>.py [tham sá»‘]`. Chi tiáº¿t lá»‡nh: `--help` cá»§a tá»«ng script vÃ  `scripts/README.md` (mÃ´ táº£ bá»‘ cá»¥c 7 thÆ° má»¥c; khÃ´ng nháº¯c biáº¿n mÃ´i trÆ°á»ng `LLM_API_KEY` / `LLM_BASE_URL`).

## 11.1. Tá»«ng thÆ° má»¥c

| ThÆ° má»¥c           | File                          | Viá»‡c                                                                                                                                                                                                                                                                                                             | DÃ¹ng chÃ­nh                                                                                           |
| ----------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `data_pipeline/`  | `stage1_clean_domain.py`      | stage 1                                                                                                                                                                                                                                                                                                          | `data.clean`, SQLite dedupe, pyarrow                                                                 |
|                   | `stage2_merge_filter.py`      | stage 2                                                                                                                                                                                                                                                                                                          | `data.domain`, `data.filter`                                                                         |
|                   | `stage3_map_split.py`         | stage 3                                                                                                                                                                                                                                                                                                          | `data.mapping`, `data.split`, `data.leakage`                                                         |
| `eda_diagnostic/` | `run_eda.py`                  | EDA streaming trÃªn review thÃ´                                                                                                                                                                                                                                                                                    | `data.eda`                                                                                           |
|                   | `diagnose_splits.py`          | cháº©n Ä‘oÃ¡n split (má»¥c 4.1): `--tag`, `--out`; báº£n 29/10 in **riÃªng** máº«u sá»‘ theo event / pair / user (`print_diagnosis_report`) vÃ  khÃ´ng cÃ²n coi `*_reachable_pct` lÃ  tráº§n macro Recall@K                                                                                                                             | `data.eda.diagnose_splits`, `data.split`, `data.mapping`                                             |
| `evaluation/`     | `run_baselines.py`            | cháº¡y random/popularity/item_knn/bpr_mf, ghi `exp_NNN` trá»±c tiáº¿p trong `experiments/`                                                                                                                                                                                                                             | há» matrix-based + `tools/evaluation`                                                                 |
|                   | `tune_baselines.py`           | tune chá»‰ báº±ng validation; `--run-final-test` refit train+val vÃ  Ä‘o test má»™t láº§n                                                                                                                                                                                                                                  | há» matrix-based                                                                                      |
|                   | `candidate_recall.py`         | má»¥c 10.2; ghi vÃ o `<experiments_dir>/<candidate_recall.experiments_subdir>`                                                                                                                                                                                                                                      | `ItemCFTool`, `SemanticSearchTool`, `ItemCorpus`                                                     |
|                   | `run_agent_eval.py`           | má»¥c 10.3: so sÃ¡nh baseline / type1 / planner / planner_memory; `--resume` (trajectory ghi dáº§n), `--reflect-rounds` (ghi Ä‘Ã¨ `agent.reflect_rounds`), `--inference-mode` (llm hoáº·c template; ghi Ä‘Ã¨ `inference.mode`), `--eval-on test` má»›i Ä‘á»¥ng test; ghi vÃ o `<experiments_dir>/<agent_eval.experiments_subdir>` | `evaluation` (5 layer + `requests/`), `inference`                                                                      |
|                   | `benchmark_categories_any.py` | Ä‘o `SemanticSearchTool` + `categories_any` **cÃ³ / khÃ´ng cÃ³** index `idx_cat_item_cat` (dá»±ng corpus tá»« `meta_*.jsonl.gz`, in `EXPLAIN QUERY PLAN` vÃ  thá»i gian); `--tag`, `--queries-file` (JSONL), `--iterations`, `--limit`                                                                                     | corpus + `SemanticSearchTool`                                                                        |
|                   | `analyze_ranking_bottlenecks.py` | Ä‘á»c candidate / score Ä‘Ã£ lÆ°u: máº¥t mÃ¡t do retrieval, headroom cá»§a ranking, fusion nguá»“n; **khÃ´ng** fit model, **khÃ´ng** load corpus, **khÃ´ng** gá»i LLM (dÃ¹ng target chá»‰ Ä‘á»ƒ cháº©n Ä‘oÃ¡n)                                                                                                                            | `tools/evaluation` (metric), artifact ranking                                                                 |
|                   | `evaluate_product_reply.py`   | cháº¥m cÃ¢u tráº£ lá»i cuá»‘i theo 2 trá»¥c faithfulness + communication (`product_reply_evaluator`); `--input-file` JSONL hoáº·c `--request` + `--items-file` + `--answer`                                                                                                                                                    | `evaluation/product_reply_evaluator`                                                                 |
|                   | `evaluate_with_jev.py`        | nhÆ° trÃªn nhÆ°ng dÃ¹ng Jev (TypeSafe AI) lÃ m judge (`jev_product_evaluator`, `configs/eval/judge.yaml`)                                                                                                                                                                                                              | `evaluation/judge`, `evaluation/jev_product_evaluator`                                                |
| `experiments/`    | `compare_experiments.py`      | so sÃ¡nh cÃ¡c `exp_NNN` theo `agent/ablation.yaml` (`--config`) â†’ bÃ¡o cÃ¡o markdown / CSV / JSON (má»¥c 10.4; `docs/ablation_protocol.md`). Import Ä‘Ã£ Ä‘Ãºng sau refactor                                                                                                                                               | `evaluation/ablation`                                                                                |
| `tools/`          | `run_tools.py`                | cháº¡y má»i tool trÃªn dá»¯ liá»‡u tháº­t (`--model` knn hoáº·c popularity, `--neighbors`, `--eval-users`, `--negatives`); ghi `<log_dir>/run_tools.log` (log kiá»ƒm tool, khÃ´ng pháº£i káº¿t quáº£ thÃ­ nghiá»‡m)                                                                                                                      | corpus + há» DataFrame-based + `BaselineScorer`; **lÃ  nÆ¡i duy nháº¥t cháº¡y `SQLTool` trÃªn dá»¯ liá»‡u tháº­t** |
|                   | `check_llm_provider.py`       | gá»i thá»­ LLM tháº­t (`health_check` + má»™t request JSON)                                                                                                                                                                                                                                                             | `api/`                                                                                               |
| `llm_agent/`      | `smoke_real_llm.py`           | `PlanExecutor` + 5 tool trÃªn fixture synthetic, LLM tháº­t                                                                                                                                                                                                                                                         | `api/`, `agents/`                                                                                    |
| `demo/`           | `run_demo.py`                 | Gradio UI: `--mock` (khÃ´ng cáº§n dá»¯ liá»‡u / LLM / máº¡ng) hoáº·c backend tháº­t vá»›i `--tag`, `--domain`, `--eval-on`, `--host`, `--port`; cáº§n `pip install gradio`                                                                                                                                                        | `package/demo`                                                                                       |
|                   | `demo_full_agent.py`          | `build_tools()` / `build_executor()` **báº£n cÅ©** (5 tool, khÃ´ng cÃ³ `SQLTool`, khÃ´ng qua `AgentTools`); agent tháº­t dÃ¹ng `package/agents/toolkit/build_tools.py`. KhÃ´ng cháº¡y trá»±c tiáº¿p; chÆ°a quyáº¿t Ä‘á»‹nh xoÃ¡                                                                                                         | â€”                                                                                                    |

`analyze_agent_failures.py` (cÃ³ á»Ÿ báº£n 12/10) **khÃ´ng cÃ³ trong snapshot 17/10**: hiá»‡n chÆ°a cÃ³ script phÃ¢n tÃ­ch lá»—i step theo tool.

## 11.2. Thá»© tá»± cháº¡y

KhÃ´ng cÃ²n `sh/`: nhá»¯ng viá»‡c `_common.sh` tá»«ng lÃ m (Ä‘á»c `TAG`, láº·p qua domain, bá» qua stage Ä‘Ã£ cÃ³ output) **khÃ´ng tá»± Ä‘á»™ng**; dÃ¹ng tham sá»‘ cá»§a tá»«ng script: `data_pipeline/stage1_clean_domain.py` (`--domain`, `--review-path`, `--output-dir`, `--chunk-size`, `--force`) â†’ `stage2_merge_filter.py` (`--domain`, `--tag`, `--force`, `--cold-start-report`) â†’ `stage3_map_split.py` (`--tag`, `--force`) â†’ (tuá»³ chá»n) `eda_diagnostic/diagnose_splits.py --tag <tag>`. `evaluation/run_baselines.py`, `evaluation/candidate_recall.py`, `tools/run_tools.py` nháº­n `--tag`; `eda_diagnostic/run_eda.py` nháº­n `--domain` / `--path`. Script táº£i review/meta (`download_review_data.sh`) vÃ  `download.yaml` khÃ´ng cÃ²n trong repo: dá»¯ liá»‡u thÃ´ pháº£i Ä‘Æ°á»£c Ä‘áº·t sáºµn vÃ o `resource/raw/`.

---

# 12. Tests â€” `tests/`

Cháº¡y: `PYTHONPATH=. pytest tests -q`, hoáº·c `tests/run_all_tests.sh` (cÅ©ng cÃ³ `.bat`); má»—i thÆ° má»¥c con (`agents/`, `config/`, `data/`, `tools/`â€¦) cÃ³ `run_tests.sh` / `.bat` riÃªng; `tests/README.md` mÃ´ táº£ bá»‘ cá»¥c. **Snapshot 17/10 sau refactor (`src_e44a83.zip`), `pytest tests`: 952 pass, 1 Ä‘á», 1 skip** (trÆ°á»›c refactor, `src_1.zip`: 925 pass / 15 Ä‘á»). Sá»‘ test thu tháº­p theo thÆ° má»¥c: agents 115, config 37, data 62, demo 17, evaluation 72, tools 649, cá»™ng `test_package_import.py`. **1 test Ä‘á»:** `tests/demo/test_live_backend.py::test_live_backend_get_sample_users` cáº§n dá»¯ liá»‡u tháº­t `resource/splits/multi_domain/train.parquet` (Ä‘á» khi khÃ´ng cÃ³ dá»¯ liá»‡u, khÃ´ng pháº£i lá»—i code). **Log test:** `tests/README.md` ghi `experiments/test_logs/`, nhÆ°ng `run_all_tests.sh` vÃ  `results_report.py` (`DEFAULT_RESULTS_DIR`) váº«n ghi `tests/logs/`; zip Ä‘Ã£ chuyá»ƒn tay cÃ¡c file cÅ© sang `experiments/test_logs/`; `test_data_paths.py` kháº³ng Ä‘á»‹nh `tests/logs` **khÃ´ng** náº±m trong cáº¥u hÃ¬nh Ä‘Æ°á»ng dáº«n. (Báº£n 12/10: 796 test / 792 pass / 4 Ä‘á» trÃªn má»™t zip khÃ¡c.)

**31/10/2026 â€” Ä‘Ã£ cháº¡y láº¡i `pytest tests -q`** (sau khi sá»­a `package/__init__.py`, má»¥c 16, vÃ  sá»­a import `memory_tool.py`): **1212 test thu tháº­p Ä‘Æ°á»£c â†’ 1198 passed, 10 failed, 2 skipped, 2 xfailed.** Cháº¡y chia lÃ´ theo thÆ° má»¥c vÃ¬ giá»›i háº¡n thá»i gian cá»§a shell; `pytest tests --collect-only -q` xÃ¡c nháº­n tá»•ng 1212. 10 test Ä‘á» (**chÆ°a Ä‘iá»u tra nguyÃªn nhÃ¢n**): `config/test_data_paths.py::test_data_paths_layout_is_under_resource`, `config/test_data_paths.py::test_config_cli_resolves_paths_from_datapaths_for_shell_scripts`, `config/test_package_layout.py::test_every_public_module_has_one_public_symbol_named_after_the_file`, `config/test_package_layout.py::test_public_names_are_unique_across_the_package`, `config/test_path_hygiene.py::test_no_hardcoded_project_dirs_in_code`, `evaluation/ablation/test_loader.py::test_comparison_rejects_policy_and_protocol_mixing`, `evaluation/agent/test_behavior_snapshot.py::test_behavior_snapshot_matches_existing`, `evaluation/agent/test_eval_integration.py::{test_run_planner_adds_the_answer_without_touching_the_recommendation_or_planner_usage, test_end_to_end_scenario[llm]}`. **Test privacy `test_no_module_imports_a_private_module_of_another_folder` giá» pass** (memory_tool.py khÃ´ng cÃ²n import cross-folder private). `tests/demo` 46 passed â€” khÃ´ng cÃ³ test nÃ o Ä‘á» vÃ¬ thiáº¿u `resource/` trong láº§n cháº¡y nÃ y. Sá»‘ **file** test hiá»‡n táº¡i (Ä‘áº¿m `tests/**/test_*.py`): `agents/` 17, `config/` 8, `data/` 16, `demo/` 5, `evaluation/` 13, `tools/` 34, vÃ  1 file á»Ÿ gá»‘c `tests/` (`test_package_import.py`).

|File|Kiá»ƒm gÃ¬|
|---|---|
|`conftest.py`, `tools_helpers.py`, `results_report.py`|fixture dÃ¹ng chung: `corpus` (5 item máº«u), `cf_setup` (interactions + mapping); plugin ghi káº¿t quáº£ tá»«ng test|
|`test_package_import.py`|import `package.*` pháº£i nháº¹ (CLI `python -m package.config` cháº¡y tá»« shell)|
|**`config/`**||
|`test_config_loader.py`|thay biáº¿n mÃ´i trÆ°á»ng, `${VAR:-default}`, thiáº¿u file/biáº¿n, `llm.yaml` khÃ´ng chá»©a credential, CLI `python -m package.config`|
|`test_data_paths.py`|má»i key `data_paths` â†” field `DataPaths`, cÃ¡c thÆ° má»¥c phÃ¢n biá»‡t vÃ  náº±m trong project, `tag` chá»‰ Ä‘á»•i thÆ° má»¥c theo run|
|`test_domain_registry.py`|`namespaced_item_id`, `tag_domain`, `merge_domains` (khÃ´ng Ä‘á»¥ng id, giá»¯ `user_id`), `domain_breakdown`|
|`test_path_hygiene.py`|AST cáº¥m hard-code `resource/â€¦`, `experiments/â€¦`; **code trong `package/` vÃ  `scripts/` khÃ´ng tá»± Ä‘á»c má»¥c `paths` thÃ´ cá»§a `data_paths.yaml`** (pháº£i qua `DataPaths`); khÃ´ng cÃ²n `_config.py`; khÃ´ng cÃ³ secret trong config|
|`test_package_layout.py`|**má»™t file, má»™t symbol**; tÃªn cÃ´ng khai duy nháº¥t toÃ n package; module `_xxx` riÃªng theo thÆ° má»¥c (má»¥c 2.6). **Test privacy giá» pass** cho `memory_tool.py` (Ä‘Ã£ xoÃ¡ khá»i `EXEMPT_FILES`, import dÃ¹ng public API). CÃ²n 1 vi pháº¡m á»Ÿ `layer5_deployment.py` (Ä‘Ã£ exempt).|
|`test_dependency_direction.py`|hÆ°á»›ng phá»¥ thuá»™c giá»¯a `tools`, `agents`, `inference`, `evaluation`, `demo` (má»¥c 2.5); danh sÃ¡ch ngoáº¡i lá»‡ pháº£i cÃ²n Ä‘Æ°á»£c dÃ¹ng|
|`test_import_resolution.py`|má»i `package.*` import trong `package/`, `scripts/`, `tests/` trá» tá»›i file tá»“n táº¡i|
|`test_tool_limits.py`|giá»›i háº¡n láº¥y tá»« `tools.yaml`, `check_top_k`, giÃ¡ trá»‹ sai bá»‹ tá»« chá»‘i|
|**`data/`**||
|`test_clean.py`, `test_mapping.py`, `test_temporal_split.py`, `test_load_splits.py`, `test_split_paths.py`, `test_load_item_metadata.py`|cÃ¡c hÃ m tÆ°Æ¡ng á»©ng trong `package/data`|
|`test_leakage_check.py`|**cáº£ hai chiá»u**: pass khi há»£p lá»‡, raise khi vi pháº¡m|
|`test_eda.py`, `test_streaming_eda.py`, `test_metadata_eda.py`|cÃ¡c hÃ m EDA (ká»ƒ cáº£ `segment_users`, `compute_metadata_stats`)|
|`test_eval_helpers.py`|`select_fit_target`, `segment_users_by_history`, `build_corpus` (Ä‘á»™ phá»§ quÃ¡ tháº¥p â†’ lá»—i), `parameter_grid`|
|`test_diagnose_splits.py`|`diagnose_splits` / `SplitDiagnosis` (cÃ¡c chá»‰ sá»‘ item Ä‘Ã£ tháº¥y, cáº·p láº·p, `reachable`, tá»‰ lá»‡ domain â€¦)|
|**`agents/`**||
|`test_plan_executor.py`|retry JSON sai, cáº¯t `max_steps`, id bá»‹a khÃ´ng cháº¡y tool, ref `$N`, `ask_user`, arg sai chá»— cÃ³ gá»£i Ã½, má»i tool tá»± mÃ´ táº£|
|`test_plan_reflect.py`|plan-reflect: sá»­a plan khi step lá»—i / khÃ´ng ra item, giá»›i háº¡n `reflect_rounds`, khÃ´ng reflect khi id bá»‹a hoáº·c timeout SQL, reply reflect há»ng bá»‹ bá», `last_reflections` / `last_first_attempt_ok`|
|`test_memory_tool.py`|`MemoryTool`: user 300 interaction, user láº¡, 0 interaction, giÃ¡ toÃ n NULL, dÃ¹ng lÃ m ref trong plan|
|`test_llm_provider.py`|factory + provider (HTTP bá»‹ fake)|
|`test_phase1_smoke.py`|config â†’ factory â†’ provider end-to-end (fake `urlopen`) vÃ  náº¡p config dá»¯ liá»‡u|
|`test_baselines.py`, `test_item_knn_equivalence.py`|popularity loáº¡i item Ä‘Ã£ tháº¥y, ItemKNN, metric macro-average, top_k; hai há» ItemKNN cho cÃ¹ng ma tráº­n similarity|
|`inference/`: `test_limits.py`, `test_adapters.py`, `test_compose.py`|`package/inference`: validate `inference.yaml`, `outcome_from_*`, `classify_outcome`, template / LLM (grounding, retry, fallback)|
|`fakes/` (thÆ° viá»‡n, khÃ´ng pháº£i test): `fake_tools.py`, `sample_data.py`, `scripted_llm.py`|tool giáº£ khá»›p schema tool tháº­t, builder dá»¯ liá»‡u máº«u, `ScriptedLLM` táº¥t Ä‘á»‹nh (khÃ´ng gá»i API)|
|`test_executor_guards.py`, `test_plan_building.py`, `test_reflection_behavior.py`, `test_classify_outcome.py`, `test_inference_behavior.py`, `test_end_to_end.py`, `test_fake_contracts.py`|guard cá»§a `_execute` (tool láº¡, id bá»‹a, arg sai chá»—, ref há»ng, cáº¯t `max_steps`), retry plan JSON, plan-reflect, báº£ng status cá»§a `classify_outcome`, grounding / fallback cá»§a inference, pipeline planner â†’ executor â†’ outcome â†’ compose, há»£p Ä‘á»“ng fake tool â†” tool tháº­t|
|**`demo/`**||
|`test_demo_config.py`, `test_demo_backend.py`, `test_inference_adapter.py`, `test_live_backend.py`, `test_gradio_ui.py`|`demo.yaml`, `MockBackend`, adapter (`adapt_from_inference` â€¦), `LiveBackend`, giao diá»‡n Gradio. `test_live_backend_get_sample_users` cáº§n dá»¯ liá»‡u tháº­t|
|**`evaluation/`**||
|`agent/`: `test_agent_eval.py`, `test_eval_integration.py`|`build_requests`, `extract_recommendations`, `score_trajectory`, `summarize`, cá»™t reflect trong trajectory/summary, `--resume` theo `reflect_rounds`. náº¡p `scripts/evaluation/run_agent_eval.py` (Ä‘Æ°á»ng dáº«n Ä‘Ã£ sá»­a sau refactor) `test_eval_integration.py`: tÃ­ch há»£p `run_agent_eval` vá»›i `inference` (`--inference-mode`, cá»™t answer, `--resume`; dÃ¹ng chung loader `_load_run_agent_eval` cá»§a `test_agent_eval.py`)|
|`ablation/`: `test_limits.py`, `test_loader.py`, `test_compare.py`, `test_statistics.py`, `test_report.py`, `test_integration.py`|`package/evaluation/ablation`: validate config, náº¡p `scored.jsonl` / `config.yaml`, ghÃ©p cáº·p theo `request_id`, bootstrap CI, McNemar, bÃ¡o cÃ¡o, so sÃ¡nh hai nhÃ³m. (NhÃ¡nh `king_key` á»Ÿ `_compare.py:256` chÆ°a cÃ³ test cháº¡m tá»›i)|
|`component/`: `test_loader.py`, `test_regression.py`, `test_memory_correctness.py`, `test_memory_utility.py`|loader dataset cá»§a component benchmark, so sÃ¡nh hai láº§n cháº¡y (regression), `MemoryCorrectnessEvaluator` Ä‘á»‘i chiáº¿u oracle Ä‘á»™c láº­p + phÃ¡t hiá»‡n leakage cÃ i vÃ o, phÃ¢n tÃ­ch memory utility ghÃ©p cáº·p nhiá»u run|
|`agent/` (má»›i 29/10): `test_behavior_snapshot.py` (+ `behavior_snapshot.json`)|khoÃ¡ hÃ nh vi cháº¥m Ä‘iá»ƒm trÆ°á»›c / sau refactor 5 lá»›p: so `score_trajectory` vá»›i snapshot Ä‘Ã£ lÆ°u|
|**`tools/`** (má»—i module má»™t thÆ° má»¥c con; fixture "tiny world" trong `tools/conftest.py`, giÃ¡ trá»‹ mong Ä‘á»£i tÃ­nh tay)||
|`base/`: `test_tool_call_logger.py`, `test_validation.py`|há»£p Ä‘á»“ng log cá»§a má»i tool (field, `input_hash` á»•n Ä‘á»‹nh, JSONL); `validate_list_like` / `validate_int`â€¦|
|`corpus/`: `test_contract_corpus.py`, `test_corpus_regressions.py`|`ItemCorpus`: namespace id, giÃ¡/NULL, id trÃ¹ng, báº¯t buá»™c domain, categories, cá»™t sá»‘, chá»‰ Ä‘á»c (authorizer cháº·n ghi), `item_domains` chia chunk, `from_parquet`; **`SCHEMA_HINT` chá»‰ nÃªu báº£ng/cá»™t cÃ³ tháº­t** (so vá»›i `SELECT â€¦ LIMIT 0` vÃ  `sqlite_master`, vÃ¬ `PRAGMA` bá»‹ cháº·n; khÃ´ng so kiá»ƒu cá»™t)|
|`sql_query/`: `test_contract_sql_query.py`, `test_sql_filter_semantics.py`, `test_sql_filter_validation.py`, `test_query_tool_regressions.py`, `test_sql_hardening.py`|`SQLTool` / `QueryTool` / `compile_filters`: filter giÃ¡, categories any/all, domain, key láº¡ bá»‹ tá»« chá»‘i, wildcard `LIKE` lÃ  literal, kiá»ƒu sai bá»‹ tá»« chá»‘i rÃµ rÃ ng, `total_matches`/`truncated`, tráº§n `max_rows`, timeout, SQL nhiá»u cÃ¢u / ghi bá»‹ cháº·n|
|`retrieval/`: `test_contract_retrieval.py`, `test_semantic_search_regressions.py`|`SemanticSearchTool` (lexical FTS5/BM25): tokenizer (giá»¯ `usb-c`), match tá»‘t nháº¥t trÆ°á»›c, filter, output Ä‘Æ°a Ä‘Æ°á»£c sang tool khÃ¡c, khÃ´ng match â†’ rá»—ng, khÃ´ng inject FTS, limit, **truy váº¥n Ä‘áº¿m háº¿t giá» â†’ `total_matches=None` váº«n cÃ³ candidates; truy váº¥n chÃ­nh háº¿t giá» â†’ `ok=False`**|
|`ranking/`: `test_item_cf_tool.py`, `test_reco_model_tool.py`, `test_ranking_hardening.py`, `test_contract_ranking_extras.py`|`ItemCFTool` (cá»™ng nhiá»u seed, `unknown_items`, validate), `RecoModelTool` (loáº¡i/giá»¯ item Ä‘Ã£ tháº¥y, nháº­n output tool khÃ¡c, `unscored_item_ids`, `has_personal_signal`, cold start, note khi má»i á»©ng viÃªn Ä‘Ã£ xem) vÃ  há»£p Ä‘á»“ng scorer|
|`score/`: `test_contract_baseline_scorer.py`, `test_baseline_scorer_validation.py`|`BaselineScorer`: cÃ´ng thá»©c, tie-break, user láº¡, validate|
|`recommenders/`: `test_base_recommender.py`, `test_contract_recommenders.py`|`Recommender` base, cáº£ hai há» API, factory, fallback, negative sampling cá»§a BPR|
|`evaluation/`: `test_contract_evaluation.py`, `test_evaluator.py`|metric, `evaluate_recommender`, `EvaluationResult`, phÃ¢n Ä‘oáº¡n user|
|`utilities/`: `test_contract_utilities.py`|`merge_model_params`, `hardware_info`, `select_fit_target`, `parameter_grid`, lÆ°u experiment|
|`integration/`: `test_tools_integration.py`|cÃ¡c module khá»›p nhau á»Ÿ ranh giá»›i (tiny world)|
|`corpus/` (má»›i 29/10): `test_metadata_policy.py`|policy metadata Ã©p **á»Ÿ táº§ng SQL**: mask `price` / `average_rating` / `rating_number`, khÃ´ng cÃ³ Ä‘Æ°á»ng vÃ²ng SQL, policy chá»‘t má»™t láº§n (má»¥c 5)|
|`evaluation/` (má»›i 29/10): `test_protocol.py`, `test_query_normalization.py`, `test_ranking_bottlenecks.py`, `test_ranking_checkpoint.py`, `test_ranking_streaming.py`|`evaluation_protocol` (máº«u sá»‘, cutoff), `ascii_fold`, replay bottleneck, checkpoint / resume / export cá»§a ranking eval â€” cháº¡y end-to-end vá»›i tool tháº­t, khÃ´ng cáº§n LLM|

KhÃ´ng cÃ³ file test riÃªng cho `agents/_limits.py` (chá»‰ Ä‘Æ°á»£c dÃ¹ng giÃ¡n tiáº¿p qua `reflect_rounds`).

---

# 13. Pháº§n cÃ²n láº¡i

|NÆ¡i|Tráº¡ng thÃ¡i|
|---|---|
|`demo/`|backend + view model cá»§a demo UI (má»¥c 13.1)|
|`utils/ensure_utf8_stdout.py`|`ensure_utf8_stdout()` (export qua `package.utils`) â€” trÃ¡nh `UnicodeEncodeError` trÃªn Windows khi in tiáº¿ng Viá»‡t|
|`memory/__init__.py`|export `MemoryTool`, `get_memory_limits`, `MemoryLimits` (code á»Ÿ `memory/memory_tool.py`, `memory/limits.py`; má»¥c 6.3)|
|`tools/embeddings/`|**placeholder** (`__init__.py` 3 dÃ²ng, chÆ°a cÃ³ code). Dá»± kiáº¿n: embedding retrieval|

CÃ¡c package `embeddings/`, `features/`, `sequential/` á»Ÿ cáº¥p `package/` Ä‘Ã£ bá»; `api/` (má»¥c 8) vÃ  `inference/` (má»¥c 9.4) Ä‘Ã£ cÃ³ code.

## 13.1. `package/demo/` â€” backend cá»§a demo UI

**Vai trÃ²:** tÃ¡ch "nhá»¯ng gÃ¬ UI hiá»ƒn thá»‹" khá»i agent. `scripts/demo/run_demo.py` dá»±ng giao diá»‡n Gradio trÃªn cÃ¡c lá»›p nÃ y. Config: `agent/demo.yaml`. CÃ¡ch cháº¡y: `--help` cá»§a `scripts/demo/run_demo.py` (`docs/demo.md` mÃ  báº£n cÅ© trÃ­ch **khÃ´ng tá»“n táº¡i**).

|File|Viá»‡c|
|---|---|
|`view/_dataclass.py`|`DemoItem`, `DemoRequest` (cÃ³ `inference_mode`, `use_memory`), `DemoTrace` (plan, steps, `ask_user`, `reflections`, `first_attempt_ok`, `truncated`, `usage`, `inference`), `DemoResult` (`status`, `text`, `items`, `trace`), `DemoProfile`, `MemoryView`|
|`view/format_items.py`, `view/format_trace.py`, `view/status_badge.py`|Ä‘á»‹nh dáº¡ng danh sÃ¡ch item thÃ nh báº£ng, váº¿t thá»±c thi thÃ nh markdown, badge theo status|
|`adapter/adapt_from_plan_executor.py`|káº¿t quáº£ `PlanExecutor` â†’ `DemoResult`; `text` do hÃ m máº«u táº¥t Ä‘á»‹nh, **khÃ´ng pháº£i LLM**|
|`adapter/adapt_from_plan_executor_error.py`|khi `PlanExecutor` nÃ©m ngoáº¡i lá»‡|
|`adapter/adapt_from_inference.py`|`adapt_from_inference(answer, *, request, item_id_to_metadata, trace=None)`: `Answer` â†’ `DemoResult`; bá»• sung metadata cÃ²n thiáº¿u tá»« corpus, `error` chá»‰ khi status `tool_error`, gáº¯n `trace.inference` (composer / grounded / fallback_reason / reason / usage). **ÄÃ£ cÃ i Ä‘áº·t â€” khÃ´ng cÃ²n `raise NotImplementedError`**|
|`adapter/_helper.py`|vÄƒn báº£n tráº¡ng thÃ¡i dÃ¹ng chung cho cÃ¡c adapter|
|`backend/mock_backend.py`|`MockBackend`: tráº£ káº¿t quáº£ cÃ³ sáºµn (phÆ°Æ¡ng Ã¡n dá»± phÃ²ng khi demo lá»—i; khÃ´ng cáº§n dá»¯ liá»‡u / LLM / máº¡ng)|
|`backend/live_backend.py`|`LiveBackend`: táº£i dá»¯ liá»‡u **má»™t láº§n** (`initialize`), dá»±ng executor vÃ  `Type1Agent`, xá»­ lÃ½ request tuáº§n tá»± cÃ³ khoÃ¡ (`respond`); nay `respond` cháº¡y cáº£ `compose_answer(outcome, llm, mode=request.inference_mode)` â†’ `adapt_from_inference`, vÃ  chá»¥p memory trÆ°á»›c / sau báº±ng `take_memory_snapshot` khi `use_memory`; `get_sample_users`, `build_profiles`|
|`samples/sample_requests.py`, `samples/sample_users.py`|`sample_requests(language)` (tá»« `TEMPLATES` cá»§a `agents/_schema.py`), `sample_users(â€¦)` (chá»n user tháº­t theo segment cold / sparse / warm)|
|`samples/_identity_injection.py`|`identity_injection_vi` / `identity_injection_en`: cÃ¢u gáº¯n danh tÃ­nh user vÃ o request máº«u|
|`_profile_builder.py`|`build_profiles(...)` â€” Ä‘á»c `agent/demo_profiles.yaml` (`demo_profiles.pinned`) vÃ  dá»±ng profile `blank` / `pinned` / `auto` cho UI|
|`_consumed_by.py`|`detect_consumed_by(steps, memory_step_indices)`: step nÃ o Ä‘Ã£ dÃ¹ng output `MemoryTool` qua ref `$<n>`|
|`_memory_snapshot.py`|`take_memory_snapshot(memory_tool, user_id)`: chá»¥p profile trÆ°á»›c / sau má»™t request Ä‘á»ƒ UI so sÃ¡nh|
|`view/format_memory.py`|`format_memory(view, item_id_to_metadata=None)`: render `MemoryView` thÃ nh markdown|
|`_limits.py`|`DemoLimits` tá»« `agent/demo.yaml` (validate)|

**Äiá»u cáº§n biáº¿t:** demo **Ä‘Ã£ dÃ¹ng** `package/inference` â€” `live_backend.respond` gá»i `compose_answer(...)` rá»“i `adapt_from_inference(...)`, nÃªn `text` láº¥y tá»« `Answer` (háº¿t "hÃ m máº«u"). CÃ¡c import thá»«a cá»§a `LiveBackend` **chÆ°a Ä‘á»‘i chiáº¿u láº¡i** (`.venv` khÃ´ng cÃ³ `pyflakes`).

---

# 14. VÃ­ dá»¥ end-to-end

Dá»¯ liá»‡u trong vÃ­ dá»¥ lÃ  **minh hoáº¡**; luá»“ng, tÃªn tool, tÃªn trÆ°á»ng vÃ  status láº¥y tá»« code (`agents/planner/*`, `agents/results/extract_recommendations.py`, `inference/**`).

## 14.1. Má»™t dÃ²ng

```text
request â”€â–º PlanExecutor.plan()      1 LLM call; JSON há»ng thÃ¬ retry plan_retries láº§n
        â”€â–º _execute()               má»—i step: validate â†’ gá»i tool â†’ ghi entry
        â”€â–º (REFLECT náº¿u step lá»—i / khÃ´ng ra item, â‰¤ reflect_rounds) â”€â–º _execute láº¡i
        â”€â–º outcome_from_plan_results() â”€â–º AgentOutcome
        â”€â–º compose_answer(): classify_outcome â†’ status â†’ template | LLM (+grounding)
        â”€â–º Answer
```

Ba loáº¡i viá»‡c tÃ¡ch riÃªng, khÃ´ng tool nÃ o lÃ m hai viá»‡c:

|Tool|Viá»‡c|Tráº£ vá»|
|---|---|---|
|ItemCF / SemanticSearch / SQL|**tÃ¬m á»©ng viÃªn**|`candidates` (id + Ä‘iá»ƒm/metadata thÃ´)|
|RecoModel|**xáº¿p háº¡ng** á»©ng viÃªn cho má»™t user|`ranked` (id + score, **khÃ´ng** cÃ³ tÃªn/giÃ¡)|
|Query|**láº¥y metadata** theo id|`items` (title, store, price, ratingâ€¦)|
|Memory|**tÃ³m táº¯t lá»‹ch sá»­** user|`top_categories`, `price_range`, `recent_items`|

QueryTool á»Ÿ cuá»‘i lÃ  Ä‘á»ƒ Inference cÃ³ title/price mÃ  viáº¿t cÃ¢u tráº£ lá»i vÃ  kiá»ƒm grounding; nÃ³ **bá»• sung thÃ´ng tin hiá»ƒn thá»‹**, khÃ´ng Ä‘á»•i thá»© tá»±.

## 14.2. Ká»‹ch báº£n A â€” Ä‘Æ°á»ng thÃ nh cÃ´ng

**Request:** `TÃ´i lÃ  u1, vá»«a mua Video_Games::B00X1, gá»£i Ã½ game tÆ°Æ¡ng tá»±.`

```json
{"steps": [
  {"tool": "ItemCFTool",    "args": {"items": ["Video_Games::B00X1"], "top_k": 30}},
  {"tool": "RecoModelTool", "args": {"user_id": "u1", "candidates": "$1.candidates", "top_k": 5}},
  {"tool": "QueryTool",     "args": {"item_ids": "$2.ranked.*.item_id"}}
], "ask_user": null}
```

- Step 1 â†’ 30 dÃ²ng `candidates`; step 2 â†’ `ranked` 5 dÃ²ng (theo Ä‘iá»ƒm, `cold_start=false`); step 3 â†’ metadata 5 item.
- Má»—i step ghi `{tool, ok, data, error, invented_ids, args (Ä‘Ã£ resolve, cáº¯t gá»n), output_summary, latency_seconds, error_kind}`. KhÃ´ng step lá»—i + cÃ³ item â‡’ `first_attempt_ok=true` â‡’ khÃ´ng reflect.
- Inference: `extract_recommendations` láº¥y 5 id **theo `ranked`** â†’ `classify_outcome` â‡’ `ok` â†’ `compose_answer(mode="llm")`; `check_grounding` kiá»ƒm 4 Ä‘iá»u: id láº¡, `mentioned_item_ids` khá»›p text, Ä‘á»§ item + Ä‘Ãºng thá»© tá»±, giÃ¡ trong `price_tolerance`. TrÆ°á»£t â‡’ retry `llm_retries` láº§n â‡’ háº¿t lÆ°á»£t thÃ¬ lÃ¹i template (`fallback_reason`).

## 14.3. Ká»‹ch báº£n B â€” Ä‘Æ°á»ng lá»—i

|Lá»—i trong plan|Chá»‘t cháº·n|Káº¿t quáº£ step|
|---|---|---|
|tool khÃ´ng cÃ³ trong danh sÃ¡ch|`unknown tool`|`ok=false`, **khÃ´ng gá»i tool**|
|id khÃ´ng xuáº¥t hiá»‡n trong request|`_invented_ids`|`ok=false`, `invented_ids=[â€¦]`, **khÃ´ng gá»i**|
|arg khÃ´ng cÃ³ trong `input_schema` (vd `price_max` ngoÃ i `filters`)|`_unknown_args` (cÃ³ gá»£i Ã½)|`ok=false`, khÃ´ng gá»i|
|ref há»ng (`$5.x` khi má»›i 3 step, step Ä‘Æ°á»£c tham chiáº¿u Ä‘Ã£ lá»—i)|`_resolve_refs` nÃ©m `ValueError`|step Ä‘Ã³ lá»—i (`bad_reference`), step khÃ¡c váº«n cháº¡y|
|plan dÃ i hÆ¡n `max_steps`|cáº¯t bá»›t|`last_truncated=true`|
|LLM tráº£ rá»—ng / khÃ´ng pháº£i JSON|`_extract_plan` nÃ©m `ValueError`|retry `plan_retries`, háº¿t thÃ¬ `run()` nÃ©m lá»—i|

**Reflect** cháº¡y khi plan cháº¡y xong nhÆ°ng cÃ³ step lá»—i **hoáº·c** khÃ´ng ra item (vÃ  khÃ´ng pháº£i `ask_user`): gá»­i LLM `_step_report` (tÃªn khoÃ¡ + Ä‘á»™ dÃ i list, khÃ´ng gá»­i dá»¯ liá»‡u), cháº¡y plan Ä‘Ã£ sá»­a. **KhÃ´ng** reflect khi cÃ³ id bá»‹a, SQL háº¿t time budget, hoáº·c `reflect_rounds=0`; reply reflect há»ng â‡’ bá», giá»¯ káº¿t quáº£ cÅ©. **Cold start:** `RecoModelTool` khÃ´ng lá»—i â€” tráº£ `cold_start=true`, `has_personal_signal=false`.

|Äiá»u kiá»‡n (rule Ä‘áº§u tiÃªn khá»›p tháº¯ng)|Status|
|---|---|
|cÃ³ `question`, khÃ´ng step nÃ o cháº¡y|`ask_user`|
|cÃ³ `invented_ids`, hoáº·c lá»—i á»Ÿ planner|`tool_error`|
|cÃ³ item (dÃ¹ cÃ³ step lá»—i)|`ok` (reason `partial: <tool> failed`)|
|khÃ´ng item + cÃ³ lá»—i|`tool_error`|
|khÃ´ng item + khÃ´ng lá»—i|`no_result`|

`ask_user`, `no_result`, `tool_error` **khÃ´ng bao giá» gá»i LLM**.

## 14.4. Ká»‹ch báº£n C â€” cÃ¡ nhÃ¢n hoÃ¡ vá»›i `MemoryTool`

**Request:** `TÃ´i lÃ  u1, gá»£i Ã½ game cho tÃ´i.` â†’ plan: `MemoryTool` â†’ `SQLTool(filters.categories_any="$1.top_categories")` â†’ `RecoModelTool` â†’ `QueryTool`.

- `known=false` (user láº¡) â‡’ `top_categories=[]`, `price_range=None` â‡’ `$1.price_range.max` **lá»—i tham chiáº¿u** â‡’ step 2 lá»—i â‡’ reflect.
- CÃ¡ch khÃ¡c: dÃ¹ng `$1.recent_items` lÃ m seed cho `ItemCFTool`.

## 14.5. Chá»— vÃ­ dá»¥ cÅ© (PDF Â§14) lá»‡ch code

1. **"ThÃ­ch Elden Ring"** pháº£i lÃ  id namespaced (`Video_Games::B00X1`) **vÃ ** xuáº¥t hiá»‡n trong request, náº¿u khÃ´ng `_invented_ids` cháº·n; tÃªn â†’ id cáº§n má»™t bÆ°á»›c tra cá»©u (`SemanticSearchTool`) mÃ  prompt chÆ°a dáº¡y.
2. **"DÆ°á»›i $60" + "giá»‘ng item nÃ y" khÃ´ng Ä‘i cÃ¹ng má»™t plan:** `ItemCFTool` khÃ´ng cÃ³ tham sá»‘ giÃ¡; `price_max` chá»‰ cÃ³ trong `filters` cá»§a `SQLTool`/`SemanticSearchTool`; `SQLTool` khÃ´ng nháº­n `candidates`. VÃ¬ váº­y request `constrained` nÃªn cháº¥m theo "thoáº£ rÃ ng buá»™c giÃ¡", khÃ´ng Ä‘Ã²i giá»‘ng item gá»‘c.
3. `SQLTool` **Ä‘Ã£** náº±m trong `for_planner()` (báº£n PDF ghi lÃ  khÃ´ng).
4. Memory khÃ´ng cÃ³ trong vÃ­ dá»¥ cÅ© dÃ¹ `for_planner_memory` cÃ³ `MemoryTool`.

## 14.6. Äiá»ƒm nÃªn thÃ nh test

Má»—i hÃ ng cá»§a hai báº£ng á»Ÿ 14.3 = má»™t test vá»›i plan viáº¿t sáºµn, kiá»ƒm `entry.error` + viá»‡c tool **khÃ´ng** Ä‘Æ°á»£c gá»i; grounding: mutate cÃ¢u tráº£ lá»i (thÃªm id láº¡, Ä‘á»•i thá»© tá»±, Ä‘á»•i giÃ¡) vÃ  kiá»ƒm `check_grounding` báº¯t Ä‘Æ°á»£c.

---

# 15. Kiáº¿n trÃºc hiá»‡n táº¡i vs. Ä‘Ã­ch (báº£n nÃ©n)

**Hiá»‡n táº¡i:** `User â†’ LLM â†’ plan hoÃ n chá»‰nh â†’ PlanExecutor â†’ tools â†’ Inference` â€” má»™t lÆ°á»£t, khÃ´ng cÃ³ vÃ²ng láº·p cÃ³ state. **ÄÃ­ch:** `User â†’ LLM â†’ chá»n tool â†’ káº¿t quáº£ â†’ LLM â†’ â€¦` (tool-calling láº·p, multi-turn, memory ghi Ä‘Æ°á»£c).

ÄÃ£ cÃ³: planning, plan-reflect háº¹p (Â§9.1), memory read-only (Â§6.3), inference trÃ¬nh bÃ y (Â§9.4), bá»™ Ä‘Ã¡nh giÃ¡ nhiá»u táº§ng (Â§10). CÃ²n thiáº¿u: vÃ²ng láº·p "quan sÃ¡t káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿", conversation state, memory ghi/forget.

> Timeline 06/10 â†’ 20/10 cá»§a má»¥c 15 cÅ© vÃ  má»¥c 17 (káº¿ hoáº¡ch 17/10), 18 (snapshot 19/10) Ä‘Ã£ bá» khi tinh gá»n ngÃ y 30/10 â€” má»‘c thá»i gian xem Â§1.1, sá»‘ liá»‡u 20/10 xem Â§19, sá»‘ liá»‡u má»›i nháº¥t xem Â§21.

---

# 16. Issue tracker â€” phÃ¡t hiá»‡n theo snapshot vÃ  tráº¡ng thÃ¡i cáº§n xÃ¡c minh

> **LÆ°u Ã½ Ä‘á»“ng bá»™ theo tuáº§n:** má»¥c nÃ y lÃ  issue tracker tÃ­ch luá»¹ tá»« cÃ¡c snapshot 06/10, 12/10 vÃ  17/10, khÃ´ng pháº£i toÃ n bá»™ Ä‘á»u Ä‘Æ°á»£c xÃ¡c minh láº¡i á»Ÿ `src(8).zip` ngÃ y 20/10. NhÃ£n dÆ°á»›i Ä‘Ã¢y pháº£n Ã¡nh báº±ng chá»©ng táº¡i thá»i Ä‘iá»ƒm ghi chÃº; khÃ´ng tá»± Ä‘á»™ng pháº£n Ã¡nh tráº¡ng thÃ¡i hiá»‡n táº¡i. Khi má»™t má»¥c chÆ°a Ä‘Æ°á»£c Ä‘á»‘i chiáº¿u láº¡i vá»›i zip 20/10, hÃ£y xem lÃ  **historical / cáº§n re-check**, khÃ´ng pháº£i kháº³ng Ä‘á»‹nh Ä‘ang cÃ²n lá»—i.
>
> Quy Æ°á»›c nhÃ£n lá»‹ch sá»­: **[ÄÃ£ sá»­a]** Ä‘Ã£ xÃ¡c nháº­n trong snapshot ghi chÃº; **[CÃ²n]** cÃ²n tá»“n táº¡i á»Ÿ snapshot Ä‘Æ°á»£c nÃªu; **[ChÆ°a Ä‘á»‘i chiáº¿u láº¡i]** khÃ´ng cÃ³ xÃ¡c nháº­n má»›i; **[ChÆ°a Ä‘o]** lÃ  giáº£ thuyáº¿t chÆ°a kiá»ƒm trÃªn dá»¯ liá»‡u tháº­t. Snapshot 17/10 Ä‘Ã£ cháº¡y thá»­ `ItemCFTool(items=str)`, `candidate_ids(str)`, `k_core_filter` (chuá»—i 30 vÃ²ng), `mcnemar_test`, pyflakes vÃ  test suite theo ghi chÃº lÃºc Ä‘Ã³. ÄÃ¢y lÃ  káº¿t quáº£ cá»§a má»‘c 17/10, khÃ´ng nÃªn diá»…n Ä‘áº¡t nhÆ° vá»«a cháº¡y láº¡i ngÃ y 20/10.

**Äá»‘i chiáº¿u cÆ¡ há»c ngÃ y 29/10/2026 (commit `7c1144a`) â€” chá»‰ cÃ¡c má»¥c kiá»ƒm Ä‘Æ°á»£c báº±ng má»™t lá»‡nh:**

- **[ÄÃ£ sá»­a 29/10]** `package/__init__.py` â€” trÆ°á»›c lÃ  `from .judge import JevClient` trong khi `package/judge/` Ä‘Ã£ chuyá»ƒn sang `package/evaluation/judge/` (commit `7c1144a`), lÃ m má»i `import packageâ€¦` nÃ©m `ModuleNotFoundError: No module named 'package.judge'` vÃ  `pytest` dá»«ng ngay á»Ÿ `tests/conftest.py`. ÄÃ£ tráº£ file vá» **rá»—ng** (Ä‘Ãºng tráº¡ng thÃ¡i 20/10): `import package` khÃ´ng náº¡p subpackage nÃ o (thoáº£ `tests/test_package_import.py`), cÃ²n `from package.evaluation.judge import JevClient` váº«n dÃ¹ng Ä‘Æ°á»£c. Sau Ä‘Ã³ `pytest`: 1212 test â†’ 1198 passed / 10 failed / 2 skipped / 2 xfailed (má»¥c 12).
- **[CÃ²n â€” 10 test Ä‘á» khi cháº¡y láº¡i 29/10]** danh sÃ¡ch Ä‘áº§y Ä‘á»§ á»Ÿ má»¥c 12; **chÆ°a Ä‘iá»u tra nguyÃªn nhÃ¢n** nÃªn chÆ°a gáº¯n nhÃ£n lá»—i cá»¥ thá»ƒ.
- **[ÄÃ£ sá»­a 29/10]** `package/demo/adapter/adapt_from_inference.py` khÃ´ng cÃ²n `raise NotImplementedError` (grep = 0 káº¿t quáº£); `live_backend.respond` Ä‘Ã£ gá»i `compose_answer` + adapter nÃ y.
- **[ÄÃ£ sá»­a 29/10]** `tests/config/test_path_hygiene.py` khÃ´ng cÃ²n glob `scripts/sh/*.sh` (grep = 0 káº¿t quáº£).
- **[ÄÃ£ sá»­a 29/10]** tham chiáº¿u `docs/decisions.md` Ä‘Ã£ bá» (`configs/agent/llm.yaml:2` D-003b, `configs/path/domains.yaml:2` D-010); báº£n thÃ¢n `docs/decisions.md` váº«n khÃ´ng tá»“n táº¡i nhÆ°ng khÃ´ng cÃ²n ai trÃ­ch.
- **[ÄÃ£ sá»­a 29/10]** `docs/inference_contract.md`, `docs/ablation_protocol.md`, `docs/demo.md` **khÃ´ng tá»“n táº¡i á»Ÿ báº¥t ká»³ má»‘c nÃ o trong git** (`git ls-tree -r 40d31f2 -- docs` rá»—ng; `docs/` chá»‰ xuáº¥t hiá»‡n tá»« 26/10). Hai chá»— trÃ­ch trong code Ä‘Ã£ bá» (`configs/agent/inference.yaml:1`, `package/inference/outcome/classify_outcome.py:10`); má»¥c 9.4 / 10.4 / 13.1 nay ghi rÃµ file khÃ´ng tá»“n táº¡i.
- **[CÃ²n]** trong `docs/evaluation/` cÃ²n 2 chá»— trÃ­ch `PR_DESCRIPTION_PHASE0.md` (`component_evaluation_summary.md`, `FINAL_SUMMARY.md`) â€” file nÃ y khÃ´ng cÃ³ trong repo (chÆ°a sá»­a vÃ¬ lÃ  tÃ i liá»‡u phÃ¢n tÃ­ch cá»§a báº¡n).
- **[CÃ²n â€” cáº§n hiá»ƒu láº¡i]** `tools/corpus/_sql.py::ITEMS_TABLE_SCHEMA`: **khÃ´ng** dÃ¹ng Ä‘á»ƒ táº¡o báº£ng (báº£ng do `DataFrame.to_sql` táº¡o) nhÆ°ng **cÃ³** Ä‘Æ°á»£c dÃ¹ng Ä‘á»ƒ tÃ­nh `_CORPUS_SCHEMA_FINGERPRINT` (`_sql.py:79`). CÃ¢u "khÃ´ng Ä‘Æ°á»£c dÃ¹ng" á»Ÿ Â§5 vÃ  Â§16.2 vÃ¬ váº­y khÃ´ng cÃ²n Ä‘Ãºng theo nghÄ©a Ä‘en.
- **[CÃ²n]** `scripts/evaluation/analyze_agent_failures.py` váº«n khÃ´ng cÃ³ (Ä‘Ã£ cÃ³ script khÃ¡c: `analyze_ranking_bottlenecks.py`).
- **[CÃ²n]** `package/agents/{ablation,evaluation}/` váº«n tá»“n táº¡i vÃ  chá»‰ chá»©a `__pycache__`.
- **[CÃ²n]** `scripts/demo/demo_full_agent.py` váº«n cÃ²n báº£n `build_tools()` riÃªng (5 tool).
- **[CÃ²n]** `package/tools/__init__.py` váº«n import eager `evaluation` / `recommenders` vÃ  khÃ´ng export `Tool`, `ToolResult`, `ToolInputError`, `candidate_ids`, `MemoryTool`.
- **[CÃ²n]** `tools/base/candidate_results.py` váº«n chÆ°a tool nÃ o dÃ¹ng (chá»‰ `tools/base/__init__.py` export vÃ  test).
- **[ÄÃ£ sá»­a 29/10]** docstring lá»‡ch: `package/evaluation/jev_product_evaluator.py:37` ghi "default configs/agent/judge.yaml" trong khi dÃ²ng 51 Ä‘á»c `configs/eval/judge.yaml` â€” nay docstring ghi Ä‘Ãºng `configs/eval/judge.yaml`.
- **[ChÆ°a Ä‘á»‘i chiáº¿u láº¡i 29/10]** danh sÃ¡ch import thá»«a (pyflakes) á»Ÿ Â§16.2 â€” `.venv` khÃ´ng cÃ³ `pyflakes` nÃªn khÃ´ng cháº¡y láº¡i Ä‘Æ°á»£c.

## 16.1. ÄÃ£ sá»­a á»Ÿ cÃ¡c snapshot trÆ°á»›c (nÃ©n)

13 nhÃ³m lá»—i Ä‘Ã£ xÃ¡c nháº­n sá»­a trong giai Ä‘oáº¡n 17/10â€“20/10: kiá»ƒm kiá»ƒu Ä‘áº§u vÃ o (`ToolInputError` rÃµ rÃ ng), `MemoryTool` tÃ­nh báº±ng SQL (háº¿t cáº¯t 100 dÃ²ng), `RecoModelTool` bÃ¡o `unscored_item_ids`/`has_personal_signal`, `ItemCorpus` cÃ³ authorizer + time budget + `ValueError` khi domain/id mÃ¢u thuáº«n, `SQLTool` filter semantics (store khÃ´ng phÃ¢n biá»‡t hoa/thÆ°á»ng, `price_min > price_max` bÃ¡o lá»—i), `QueryTool` giá»¯ thá»© tá»± `item_ids`, `SemanticSearchTool` dÃ¹ng `compile_filters` cÃ´ng khai, `Tool.__init_subclass__` báº¯t buá»™c khai bÃ¡o schema, `compare_experiments` import Ä‘Ãºng, 14 test trá» `scripts/run_agent_eval.py` Ä‘Ã£ sá»­a, `infer_matrix_shape` háº¿t báº£n trÃ¹ng, vÃ  quy Æ°á»›c Â§2.6 Ä‘Æ°á»£c test Ã©p.

> Danh sÃ¡ch chi tiáº¿t tá»«ng má»¥c Ä‘Ã£ bá» khi tinh gá»n 30/10. Tráº¡ng thÃ¡i hiá»‡n táº¡i kiá»ƒm báº±ng test (Â§12) vÃ  báº±ng má»¥c 29/10 á»Ÿ trÃªn.

## 16.2. [CÃ²n táº¡i snapshot cÅ© / cáº§n re-check vá»›i `src(8).zip`] (cÃ¡c má»¥c ban Ä‘áº§u xÃ¡c nháº­n 12/10; má»™t pháº§n Ä‘á»‘i chiáº¿u 19/10)

- **`SCHEMA_HINT` lá»‡ch kiá»ƒu:** ghi `rating_number REAL`, nhÆ°ng báº£ng tháº­t lÃ  INTEGER khi má»i giÃ¡ trá»‹ nguyÃªn (REAL náº¿u cÃ³ thiáº¿u). Test chá»‰ so tÃªn báº£ng/cá»™t, khÃ´ng so kiá»ƒu. Äá»•i cÃ¡ch táº¡o báº£ng sáº½ Ä‘á»•i giÃ¡ trá»‹ tool tráº£ ra (`200` â†’ `200.0`) nÃªn chÆ°a lÃ m.
- **GiÃ¡ dáº¡ng khoáº£ng** `"10 - 20"` thÃ nh NULL, khÃ´ng phÃ¢n biá»‡t Ä‘Æ°á»£c vá»›i giÃ¡ vá»‘n trá»‘ng.
- **`SQLTool`:** `include_missing_price` Ä‘á»©ng má»™t mÃ¬nh váº«n khÃ´ng cÃ³ tÃ¡c dá»¥ng.
- **`ItemCFTool`:** lá»c domain **sau** khi cáº¯t top-k lÃ¡ng giá»ng nÃªn cÃ³ thá»ƒ ra Ã­t hÆ¡n `top_k` (Ä‘Ã£ ghi trong docstring).
- **Planner khÃ´ng cÃ³ `SQLTool`** (má»¥c 2.4); **plan-reflect khÃ´ng cá»©u Ä‘Æ°á»£c timeout SQL vÃ  id bá»‹a** (do thiáº¿t káº¿).
- **Test vÃ  script:** 1 test demo cáº§n dá»¯ liá»‡u tháº­t (má»¥c 12). `scripts/README.md` cÃ³ nhÆ°ng khÃ´ng nháº¯c biáº¿n mÃ´i trÆ°á»ng; `analyze_agent_failures.py` (cÃ³ á»Ÿ báº£n 12/10) **khÃ´ng cÃ³** trong zip. (14 test trá» Ä‘Æ°á»ng dáº«n cÅ© cá»§a script Ä‘Ã£ Ä‘Æ°á»£c sá»­a sau refactor.)
- **CÃ²n import thá»«a / lá»—i nhá» (pyflakes, zip sau refactor):** `tools/corpus/item_corpus.py` (`warnings`, `Iterable`, `numpy as np`), `tools/ranking/item_cf_tool.py` (`Sequence`), `tools/sql_query/compile_filters.py` (`FILTER_KEYS`; f-string thiáº¿u placeholder ~dÃ²ng 255), `tools/score/baseline_scorer.py` (`math`), `agents/toolkit/agent_tools.py` (`ItemCorpus`), `data/split/load_splits.py` (`infer_matrix_shape` import Ä‘á»ƒ re-export), `inference/grounding/_helper.py` (`Any`), `demo/` (`adapter/_helper.py`: f-string thiáº¿u placeholder; `backend/live_backend.py`: `ItemCorpus`, biáº¿n `k`, `as_of`; `backend/mock_backend.py`: `Any`), `evaluation/ablation/` (`_compare`: `json`, `Path`, `ORACLE_KINDS`, `load_group_data`, `get_ablation_limits`; `_loader`: `get_ablation_limits`; `_statistics`: `Any`), `scripts/` (`diagnose_splits`: `pd`; `compare_experiments`: `json`, `Path`, `Any`; `demo_full_agent`: `load_config`, `build_llm_provider`; `run_demo`: `Any`, `get_data_paths`, `get_domains`).
- **`tools/corpus/_sql.py::ITEMS_TABLE_SCHEMA` khÃ´ng Ä‘Æ°á»£c dÃ¹ng** (`from_dataframe` táº¡o báº£ng báº±ng `to_sql`; `item_id` chá»‰ cÃ³ `UNIQUE INDEX`, khÃ´ng pháº£i PRIMARY KEY nhÆ° DDL gá»£i Ã½). XoÃ¡ háº±ng sá»‘ hoáº·c dÃ¹ng tháº­t; dÃ¹ng tháº­t sáº½ Ä‘á»•i kiá»ƒu cá»™t (xem dÃ²ng `SCHEMA_HINT` á»Ÿ trÃªn).
- **`scripts/demo/demo_full_agent.py`** cÃ²n báº£n `build_tools()` riÃªng, cÅ©, trÃ¹ng vai trÃ² vá»›i `agents/toolkit/build_tools.py`.
- **[ÄÃ£ sá»­a sau refactor]** `data/split/infer_matrix_shape.py` khÃ´ng cÃ²n lÃ  báº£n trÃ¹ng cá»§a hÃ m trong `load_splits.py` (xem má»¥c 4.2).
- **`tools/__init__`** váº«n import eager `evaluation`/`recommenders` vÃ  khÃ´ng export `Tool`, `ToolResult`, `ToolInputError`, `candidate_ids`, `MemoryTool` (import tá»« `package.tools.base` / `package.memory`).
- **[Cáº­p nháº­t 17/10: Ä‘Ã£ thÃªm index `idx_cat_item_cat`, chÆ°a Ä‘o trÃªn dá»¯ liá»‡u tháº­t â€” xem 16.1]** **Timeout SQL = `SemanticSearchTool` + `categories_any` (Ä‘Ã£ Ä‘o trÃªn log tháº­t; cÆ¡ cháº¿ Ä‘Ã£ tÃ¡i hiá»‡n trÃªn corpus giáº£):**
    - _Log tháº­t_ (`exp_002`, `exp_003` trong zip, cÃ¡c step `SemanticSearchTool` cá»§a planner / planner_memory, Ä‘áº¿m theo `latency_seconds â‰¥ 4 s` vÃ¬ step phá»¥ thuá»™c cÅ©ng mang chuá»—i `interrupted` trong thÃ´ng bÃ¡o lá»—i): **11 step timeout, latency p50 â‰ˆ 5,01 s, max 5,04 s (Ä‘Ãºng budget `sql_time_budget_seconds = 5.0`)**. Cáº£ 11 Ä‘á»u cÃ³ `filters.categories_any`; trong 17 lá»i gá»i cÃ³ `categories_any` thÃ¬ 11 timeout, 6 cháº¡y xong; trong 19 lá»i gá»i khÃ´ng cÃ³ `categories_any` thÃ¬ **0** timeout. `QueryTool`, `RecoModelTool`, `ItemCFTool` khÃ´ng cÃ³ timeout riÃªng. Máº«u nhá» (n = 20 request/exp).
    - _CÆ¡ cháº¿:_ filter `categories_any` biÃªn dá»‹ch thÃ nh `EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id AND c.category IN (â€¦))`. `EXPLAIN QUERY PLAN` cho tháº¥y SQLite dÃ¹ng `idx_cat_cat (category=?)` (khÃ´ng dÃ¹ng `idx_cat_item`), tá»©c **vá»›i má»—i dÃ²ng FTS khá»›p nÃ³ duyá»‡t cáº£ danh má»¥c** rá»“i má»›i so `item_id`: chi phÃ­ â‰ˆ (sá»‘ dÃ²ng khá»›p) Ã— (kÃ­ch thÆ°á»›c danh má»¥c), ráº¥t cháº­m vá»›i danh má»¥c lá»›n nhÆ° `Cases`, `Earbud Headphones`. CÃ¹ng filter áº¥y dÃ¹ng trong `SQLTool`, vÃ  `categories_all` cÅ©ng cÃ³ dáº¡ng tÆ°Æ¡ng tá»±.
    - _TÃ¡i hiá»‡n (corpus GIáº¢ 300k item, 40% thuá»™c `Cases`, khÃ´ng pháº£i dá»¯ liá»‡u tháº­t):_ query `cases black` + `categories_any=["Cases"]` + `price_max=15` â†’ **5,01 s, `ok=False`, `query exceeded the time budget`**; thÃªm index `CREATE INDEX idx_cat_item_cat ON item_categories(item_id, category)` â†’ **0,22 s, `ok=True`**. CÃ¹ng query khÃ´ng cÃ³ `categories_any`: 0,4 s (trÆ°á»›c) / 0,28 s (sau).
    - **[ChÆ°a Ä‘o]** trÃªn corpus tháº­t (631k item) vÃ  chÆ°a sá»­a code: cáº§n táº¡o index nÃ y trÃªn `ItemCorpus` rá»“i cháº¡y láº¡i Ä‘Ãºng cÃ¡c query bá»‹ timeout trong log (xem Â§16.2 vÃ  Â§20.7). Giáº£ thuyáº¿t cÅ© "FTS5 OR trÃªn 631k item vÆ°á»£t budget" **khÃ´ng Ä‘Æ°á»£c á»§ng há»™**: query khÃ´ng cÃ³ `categories_any` cháº¡y < 1,4 s trong log tháº­t.

**Má»›i á»Ÿ báº£n 17/10:**

- **[ÄÃ£ sá»­a sau refactor]** `scripts/experiments/compare_experiments.py` trÆ°á»›c Ä‘Ã¢y import `package.agents.evaluation.ablation._compare` (khÃ´ng tá»“n táº¡i) nÃªn `--help` Ä‘Ã£ `ModuleNotFoundError`; nay import `package.evaluation.ablation`.
- **[ÄÃ£ sá»­a trong `src(7).zip`] `package/evaluation/ablation/_compare.py`:** nhÃ¡nh McNemar hiá»‡n ghi `results[kind_key]`, khÃ´ng cÃ²n `king_key`. Tuy nhiÃªn váº«n nÃªn giá»¯ test há»“i quy cháº¡m nhÃ¡nh McNemar (â‰¥ 10 cáº·p báº¥t nháº¥t), vÃ¬ test chá»‰ xÃ¡c nháº­n tÃªn biáº¿n Ä‘Ãºng chÆ°a chá»©ng minh bÃ¡o cÃ¡o end-to-end trÃªn experiment tháº­t.
- **`candidate_results`** (`tools/base/candidate_results.py`, giá»¯ `score` / `similarity`) **chÆ°a tool nÃ o dÃ¹ng**, chá»‰ cÃ³ test â€” liÃªn quan quyáº¿t Ä‘á»‹nh ranking vs retrieval score (16.3).
- **[ÄÃ£ sá»­a 29/10] `demo` Ä‘Ã£ ná»‘i `inference`:** `adapt_from_inference` Ä‘Ã£ cÃ i Ä‘áº·t, `live_backend.respond` gá»i `compose_answer`; (báº£n 20/10: cÃ²n `raise NotImplementedError`, `text` cá»§a demo lÃ  hÃ m máº«u).
- **Tham chiáº¿u tÃ i liá»‡u:** `docs/inference_contract.md`, `docs/ablation_protocol.md`, `docs/demo.md` nay cÃ³ trong zip; **`docs/decisions.md` váº«n khÃ´ng cÃ³** (`llm.yaml` D-003b, `domains.yaml` D-010). Nhiá»u docstring cÃ²n trÃ­ch sá»‘ má»¥c cá»§a spec cÅ© ("má»¥c XX", "spec má»¥c XXI" á»Ÿ `api/llm_provider.py`, `api/build_llm_provider.py`, `config/load_config.py`).
- **Bá»‘ cá»¥c `experiments/` vÃ  log test chÆ°a thá»‘ng nháº¥t:** zip cÃ³ `experiments/{baselines,agent_eval}/â€¦`, `experiments/README.md` (mÃ´ táº£ cáº£ `phase4_baselines/`) vÃ  `experiments/test_logs/` (chuyá»ƒn tay), nhÆ°ng `run_baselines` / `tune_baselines` váº«n ghi `exp_NNN` tháº³ng trong `experiments/`, `run_agent_eval` / `candidate_recall` ghi vÃ o subdir theo config, `run_all_tests.sh` / `results_report.py` váº«n ghi `tests/logs/` (README nÃ³i `experiments/test_logs/`); comment `data_paths.yaml` liá»‡t kÃª `experiments/{baselines,data_pipeline,smoke_tests,test_logs}/`.
- **`tests/config/test_path_hygiene.py`** cÃ²n glob `scripts/sh/*.sh` (thÆ° má»¥c khÃ´ng cÃ²n) nÃªn kiá»ƒm tra Ä‘Ã³ luÃ´n qua mÃ  khÃ´ng kiá»ƒm gÃ¬.

## 16.3. Quyáº¿t Ä‘á»‹nh cÃ²n treo (giá»¯ láº¡i tá»« báº£n 06/10, Ä‘Ã£ nÃ©n)

- **Ranking vs retrieval score:** `RecoModelTool` bá» `similarity` cá»§a retrieval rá»“i cháº¥m láº¡i tá»« lá»‹ch sá»­ user; ba hÆ°á»›ng (trá»™n hybrid / chá»‰ rank khi cáº§n / Ä‘á»•i model) chÆ°a chá»n. CÃ¢u há»i gá»‘c: agent tráº£ lá»i "giá»‘ng cÃ¡i nÃ y" hay "há»£p vá»›i tÃ´i"?
- **Hai há» ItemKNN:** `history @ S` vs `history @ S.T` cho thá»© háº¡ng khÃ¡c nhau khi cáº¯t top-k â†’ chÆ°a chá»‘t há» nÃ o lÃ  chuáº©n (test `test_contract_recommenders.py` chá»‰ kháº³ng Ä‘á»‹nh chÃºng khá»›p khi **khÃ´ng** cáº¯t lÃ¡ng giá»ng).
- **Default lá»‡ch YAML:** ItemKNN matrix `k=50` vs DataFrame `neighbors=20`; BPR `learning_rate` 0.05 vs 0.001; lÆ°á»›i tuning `[0.001, 0.005]` khÃ´ng thá»­ 0.05.
- **`Type1Agent`** khÃ´ng clamp `top_k` theo `max_candidates`: `top_k â‰¥ 201` (5 Ã— 201 > 1000) â‡’ lá»—i á»Ÿ bÆ°á»›c retrieve.

---

# 17. Snapshot 20/10 â€” `src(8).zip`

> Sá»‘ liá»‡u Ä‘á»c tá»« `experiments/agent_eval/*/metrics.json` vÃ  bÃ¡o cÃ¡o ablation, **khÃ´ng** cháº¡y láº¡i. Má»¥c 21 lÃ  snapshot má»›i hÆ¡n (27/10); chá»— nÃ o khÃ¡c nhau thÃ¬ Â§21 Ä‘Ãºng hÆ¡n.

## 17.1. Báº±ng chá»©ng cÃ³ trong zip

| NhÃ¡nh | Báº±ng chá»©ng | Káº¿t luáº­n Ä‘Æ°á»£c Ä‘áº¿n Ä‘Ã¢u |
|---|---|---|
| Offline recommender | `baselines/exp_001`â€“`exp_003`, `phase4_baselines/` | CÃ³ sá»‘ baseline cÅ©; chÆ°a chá»©ng minh káº¿t quáº£ má»›i hay nguyÃªn nhÃ¢n recall tháº¥p |
| Agent evaluation | `agent_eval/exp_002`â€“`exp_008` (requests / trajectories / scored / metrics) | PhÃ¢n tÃ­ch Ä‘Æ°á»£c theo kind Ã— segment; pháº£i ghi rÃµ config, n, loáº¡i request |
| Memory ablation | `ablation/memory_vs_no_memory/` | GhÃ©p cáº·p 146 request, nhÆ°ng **1 run/nhÃ³m** â‡’ chÆ°a cÃ³ phÆ°Æ¡ng sai |
| Reflection ablation | `ablation/planner_reflect0_vs_reflect1/`, `planner_memory_reflect0_vs_reflect1/` | NhÆ° trÃªn; thÃªm ná»¯a inference mode khÃ¡c nhau á»Ÿ 007/008 |
| Inference ablation | `planner_template_vs_llm/`, `planner_memory_template_vs_llm/`, `type1_template_vs_llm/` | LÃ  cháº¥t lÆ°á»£ng/chi phÃ­ **cÃ¢u tráº£ lá»i**, khÃ´ng pháº£i cháº¥t lÆ°á»£ng gá»£i Ã½ |
| Candidate retrieval | `candidate_recall/exp_001`â€“`exp_018` | 18 bá»™ artifact; pháº£i tá»•ng há»£p theo nguá»“n Ã— budget Ã— segment |
| Multi-turn | trajectory + request hiá»‡n cÃ³ | **KhÃ´ng Ä‘á»§** chá»©ng minh multi-turn |

## 17.2. Agent eval `exp_004`â€“`exp_008`

Dataset tag `multi_domain`, 2,76 triá»‡u user / 678.281 item, validation. `exp_004`â€“`006` khÃ¡c scope vá»›i `exp_007`â€“`008` nÃªn **khÃ´ng** gá»™p thÃ nh má»™t xu hÆ°á»›ng.

| Run | Cáº¥u hÃ¬nh | Request | Káº¿t quáº£ Ä‘Ã¡ng chÃº Ã½ | Giá»›i háº¡n |
|---|---|---:|---|---|
| `exp_004` | planner + planner_memory, realistic, template | 86 | `planner_memory` recall@10 0.1917 á»Ÿ `cold_text` (planner 0.0417); cáº£ hai 0.175 á»Ÿ `constrained`; 0 á»Ÿ `personalized`/`similar` | `cold_text`/`constrained` lÃ  ORACLE |
| `exp_005` | baseline + type1, realistic, template | 86 | `similar`: task success 1.0 nhÆ°ng recall@10 = 0 | task success khÃ´ng thay Ä‘Æ°á»£c relevance |
| `exp_006` | baseline + type1, cÃ¹ng scope | 86 | Láº·p láº¡i Ä‘Ãºng pattern cá»§a 005 | KhÃ´ng pháº£i láº·p Ä‘á»™c láº­p |
| `exp_007` | planner + planner_memory, `reflect_rounds=0`, inference LLM | 146 | `cold_text` recall 0.0667/0.0917; `constrained` 0.200/0.225; 0 á»Ÿ `personalized`/`similar` | ORACLE + 1 run |
| `exp_008` | 4 agent, `reflect_rounds=1`, inference template | 146 | `planner_memory` 0.0917 `cold_text`, 0.250 `constrained`; planner 0.0667 / 0.175 | KhÃ´ng pháº£i ablation cá»§a 007 (khÃ¡c inference mode + danh sÃ¡ch agent) |

**Äiá»ƒm cáº§n nháº¥n máº¡nh:** `task_success = 1.0` váº«n cÃ³ thá»ƒ Ä‘i cÃ¹ng `recall@10 = 0` â€” hai metric Ä‘o hai thá»© khÃ¡c nhau. `cold_text`/`constrained` láº¥y category/price tá»« item held-out â‡’ **ORACLE upper bound**, khÃ´ng bÃ¡o nhÆ° query tháº­t. `ambiguous` cÃ³ ground truth riÃªng: thÃ nh cÃ´ng = **há»i láº¡i**.

## 17.3. Reflection (20/10) â€” chÆ°a pháº£i so sÃ¡nh sáº¡ch

Hai cáº·p bÃ¡o cÃ¡o, 146 paired request, bootstrap 10.000, 95% â€” nhÆ°ng **1 run/nhÃ³m** (bÃ¡o cÃ¡o ghi "Only 1 run per group, cannot compute variance"). VÃ­ dá»¥ `planner_reflect0_vs_reflect1`, `cold_text` (n=20, ORACLE): task success 1.00 â†’ 0.85, recall@10 0.0667 â†’ 0.0417. KhÃ´ng Ä‘á»§ Ä‘á»ƒ nÃ³i reflection lÃ m tÄƒng **hay** giáº£m cháº¥t lÆ°á»£ng. Cáº·p so sÃ¡nh sáº¡ch Ä‘áº§u tiÃªn chá»‰ cÃ³ á»Ÿ **Â§21.3** (`exp_012` vs `exp_013`, cÃ¹ng inference mode).

## 17.4. Memory (20/10) â€” tÃ­n hiá»‡u cá»¥c bá»™

`memory_vs_no_memory` (146 paired request): `cold_text` recall@10 **+0.1500** (0.0417 â†’ 0.1917), NDCG@10 +0.0579; `constrained` khÃ´ng Ä‘á»•i (0.1750). ChÆ°a káº¿t luáº­n vÃ¬: ORACLE, `personalized`/`similar` váº«n recall 0, 1 run/nhÃ³m, chÆ°a kiá»ƒm cÃ¹ng request + snapshot. KhÃ´ng chá»n má»™t metric Ä‘áº¹p rá»“i suy rá»™ng.

## 17.5. Inference (20/10)

Ba bÃ¡o cÃ¡o `*_template_vs_llm` Ä‘Ã£ cÃ³. Inference **khÃ´ng chá»n item** â€” nÃ³ diá»…n Ä‘áº¡t láº¡i danh sÃ¡ch agent Ä‘Ã£ chá»n, nÃªn pháº£i bÃ¡o riÃªng 4 táº§ng: (1) recommendation quality (Recall/NDCG/candidate recall), (2) agent/tool behavior (plan valid, tool selection, first-attempt, reflections), (3) answer generation (grounding, fallback, latency, token), (4) task behavior (clarification, constraint). KhÃ´ng gá»™p thÃ nh má»™t Ä‘iá»ƒm "agent tá»‘t hÆ¡n".

## 17.6. Candidate recall â€” `candidate_recall/exp_018`

Run 1.000 user/segment, validation, 4.147 target interaction á»Ÿ segment cold. ÄÃ¢y lÃ  Recall cá»§a **candidate set trÆ°á»›c ranking**:

| Segment | Nguá»“n | Recall@50 | Recall@100 | Recall@200 |
|---|---|---:|---:|---:|
| cold | Popularity | 0.0153 | 0.0207 | 0.0345 |
| cold | ItemCF | 0.0000 | 0.0000 | 0.0000 |
| cold | Semantic | 0.0000 | 0.0000 | 0.0000 |
| cold | Union-RR / Union-all | 0.0153 | 0.0207 | 0.0345 |
| sparse | Popularity | 0.0166 | 0.0215 | 0.0355 |
| sparse | ItemCF | 0.0092 | 0.0102 | 0.0102 |
| sparse | Semantic | 0.0098 | 0.0116 | 0.0154 |
| sparse | Union-RR | 0.0155 | 0.0229 | 0.0324 |
| sparse | **Union-all** | **0.0286** | **0.0353** | **0.0520** |
| warm | Popularity | 0.0128 | 0.0179 | 0.0283 |
| warm | ItemCF | 0.0028 | 0.0090 | 0.0090 |
| warm | Semantic | 0.0053 | 0.0067 | 0.0106 |
| warm | Union-RR | 0.0105 | 0.0179 | 0.0235 |
| warm | **Union-all** | **0.0191** | **0.0292** | **0.0414** |

**Äá»c tháº­n trá»ng:** Union-all tá»‘t nháº¥t á»Ÿ sparse/warm (Recall@200 0.0520 vs 0.0355; 0.0414 vs 0.0283); á»Ÿ cold, ItemCF vÃ  Semantic tráº£ rá»—ng nÃªn union khÃ´ng cáº£i thiá»‡n Ä‘Æ°á»£c Popularity. Recall váº«n tháº¥p á»Ÿ cáº£ 3 segment â‡’ candidate generation cÃ³ thá»ƒ lÃ  nÃºt tháº¯t, **nhÆ°ng** pháº£i kiá»ƒm reachable target vÃ  evaluator trÆ°á»›c khi quy háº¿t lá»—i cho retrieval. ÄÃ¢y lÃ  1 run/seed.

## 17.7. Multi-turn â€” chÆ°a Ä‘á»§ báº±ng chá»©ng

`requests.jsonl` + `trajectories.jsonl` khÃ´ng tá»± chá»©ng minh multi-turn. Cáº§n: (a) request cÃ³ phá»¥ thuá»™c thÃ´ng tin lÆ°á»£t trÆ°á»›c, (b) agent nháº­n conversation state tháº­t, (c) scoring Ä‘o viá»‡c dÃ¹ng thÃ´ng tin qua lÆ°á»£t. Náº¿u má»—i request cháº¡y Ä‘á»™c láº­p thÃ¬ Ä‘Ã³ lÃ  **single-request evaluation**, dÃ¹ cÃ¢u chá»¯ lÃ  há»™i thoáº¡i.

## 17.8. Káº¿ hoáº¡ch experiment

ÄÃ£ thay báº±ng **Â§21.7** (Æ°u tiÃªn: láº·p `exp_012/013` Ä‘á»ƒ cÃ³ phÆ°Æ¡ng sai, cháº¡y láº¡i `memory_utility` trÃªn run cÃ¹ng cáº¥u hÃ¬nh, giáº£i thÃ­ch `recall@10 = 0` trÆ°á»›c khi tune planner).

---

# 18. Performance review (báº£n nÃ©n, 20/10)

> Static review Ä‘á»c tá»« code, **chÆ°a pháº£i benchmark runtime**. Ba loáº¡i "performance" pháº£i Ä‘o riÃªng: latency/runtime, recommendation quality, agent reliability â€” tá»‘i Æ°u latency **khÃ´ng** tá»± Ä‘á»™ng tÄƒng Recall@K.

## 18.1. Request cháº¡y qua Ä‘Ã¢u

```text
User request
  â”œâ”€ Type1Agent   ItemCFTool â†’ RecoModelTool â†’ QueryTool            (khÃ´ng LLM planning)
  â””â”€ PlanExecutor LLM plan â†’ validate tool/args â†’ resolve $N.path â†’ cháº¡y tool tuáº§n tá»±
                  â†’ reflect náº¿u lá»—i/rá»—ng â†’ AgentOutcome â†’ Inference (template | LLM + grounding)
Tools: Tool.__call__ (validation + logging + error contract) bá»c ItemCF / SemanticSearch /
       SQL / RecoModel / Query / Memory
Ná»n:   Recommender + ma tráº­n sparse | ItemCorpus (SQLite + FTS5) | user2id / item2id + interactions
```

## 18.2. Æ¯u tiÃªn phÃ¡t hiá»‡n tá»« code

| Æ¯u tiÃªn | Component | Quan sÃ¡t trá»±c tiáº¿p trong code | HÆ°á»›ng kiá»ƒm tra/tá»‘i Æ°u |
|---|---|---|---|
| **P0 â€” correctness** | `BaselineScorer.score` vs `ItemKNNMatrixRecommender.score_batch` | CÃ¡c implementation khÃ´ng thá»‘ng nháº¥t hÆ°á»›ng nhÃ¢n: `BaselineScorer.score` dÃ¹ng `history @ similarity`, cÅ©ng nhÆ° `BaselineItemKNNRecommender.recommend`; `ItemKNNMatrixRecommender.score_batch` láº¡i dÃ¹ng `history @ similarity.T`. VÃ¬ top-k truncation cÃ³ thá»ƒ lÃ m similarity báº¥t Ä‘á»‘i xá»©ng, káº¿t quáº£ ranking cÃ³ thá»ƒ khÃ¡c nhau khi Ä‘á»•i model implementation. | Viáº¿t test vá»›i ma tráº­n similarity báº¥t Ä‘á»‘i xá»©ng Ä‘á»ƒ khÃ³a contract cho tá»«ng recommender vÃ  báº£o Ä‘áº£m `RecoModelTool` Ä‘ang nháº­n Ä‘Ãºng loáº¡i scorer/model. KhÃ´ng tá»± Ã½ Ä‘á»•i transpose: `BaselineScorer` hiá»‡n cÃ³ váº» nháº¥t quÃ¡n vá»›i `BaselineItemKNNRecommender`, nhÆ°ng cáº§n xÃ¡c minh khi dÃ¹ng `ItemKNNMatrixRecommender` hoáº·c thay model family. |
| **P1 â€” hot path** | `Tool.__call__` / `ToolCallLogger` | Má»—i call hash toÃ n bá»™ kwargs báº±ng JSON; rá»“i táº¡o `len(str(result.data))`; logger giá»¯ má»i record trong list vÃ  cÃ³ thá»ƒ má»Ÿ file/append Ä‘á»“ng bá»™ á»Ÿ má»—i call. Vá»›i candidate list lá»›n, serialization/logging cÃ³ thá»ƒ tá»‘n thÃªm Ä‘Ã¡ng ká»ƒ. | Benchmark cÃ¹ng input vá»›i logger tá»‘i giáº£n/Ä‘áº§y Ä‘á»§; log `candidate_count`, `data_keys`, bytes Æ°á»›c lÆ°á»£ng thay vÃ¬ stringify toÃ n bá»™ output; cÃ¢n nháº¯c táº¯t retention in-memory hoáº·c batch file writes cho benchmark dÃ i. Giá»¯ hash náº¿u cáº§n traceability nhÆ°ng Ä‘o chi phÃ­. |
| **P1 â€” hot path** | `MemoryTool.execute` | Má»—i request lá»c toÃ n bá»™ `interactions` Ä‘á»ƒ tÃ¬m user; náº¿u cÃ³ timestamp láº¡i lá»c toÃ n frame trÆ°á»›c, sau Ä‘Ã³ lá»c user history thÃªm láº§n ná»¯a. ÄÃ¢y lÃ  O(N_interactions) scan láº·p láº¡i cho má»—i láº§n gá»i. | Tiá»n xá»­ lÃ½/index theo `user_idx` khi build tool, giá»¯ Ä‘Ãºng `as_of_timestamp`; Ä‘o memory tÄƒng thÃªm so vá»›i giáº£m latency. ThÃªm test leakage Ä‘á»ƒ chá»©ng minh history táº¡i cutoff khÃ´ng chá»©a tÆ°Æ¡ng tÃ¡c tÆ°Æ¡ng lai. |
| **P1 â€” hot path** | `BaselineScorer.score` + `has_personal_signal` | Scoring tÃ­nh `user_items.getrow(user_idx) @ similarity`; sau Ä‘Ã³ `RecoModelTool` gá»i `has_personal_signal`, phÃ©p nÃ y nhÃ¢n láº¡i cÃ¹ng user-history vá»›i similarity. | Sau khi xá»­ lÃ½ P0 vá» hÆ°á»›ng ma tráº­n, dÃ¹ng má»™t phÃ©p tÃ­nh per-user tÃ¡i sá»­ dá»¥ng trong cÃ¹ng request, hoáº·c tÃ­nh score trá»±c tiáº¿p cho candidates. TrÃ¡nh cache vÃ´ háº¡n náº¿u user cardinality lá»›n; benchmark cache theo request trÆ°á»›c. |
| **P1 â€” retrieval** | `SQLTool.execute` | Cháº¡y query láº¥y candidates rá»“i cháº¡y thÃªm `COUNT(*)` riÃªng qua `corpus.count`. CÃ¹ng Ä‘iá»u kiá»‡n lá»c cÃ³ thá»ƒ khiáº¿n SQLite quÃ©t/index lookup hai láº§n. | Äo riÃªng SELECT vÃ  COUNT theo filter. Náº¿u `total_matches` khÃ´ng cáº§n chÃ­nh xÃ¡c trong má»i request, thÃªm cháº¿ Ä‘á»™ khÃ´ng Ä‘áº¿m hoáº·c tráº£ total Ä‘Ã£ biáº¿t/truncated; Ä‘á»«ng Ã¢m tháº§m Ä‘á»•i contract vÃ¬ eval/UI Ä‘ang dÃ¹ng field nÃ y. |
| **P1 â€” retrieval** | `SemanticSearchTool.execute` | Cháº¡y FTS query Ä‘á»ƒ láº¥y candidates, sau Ä‘Ã³ cháº¡y thÃªm COUNT JOIN FTS/filters. `ORDER BY score DESC, rating_number DESC, item_id` cáº§n sort; BM25 vÃ  filter káº¿t há»£p quyáº¿t Ä‘á»‹nh chi phÃ­. | Äo query time vÃ  COUNT time riÃªng; thá»­ `EXPLAIN QUERY PLAN` trÃªn cÃ¡c query thá»±c táº¿; giá»¯ query an toÃ n báº±ng parameterized match/filter. So sÃ¡nh recall trÆ°á»›c khi Ä‘á»•i FTS query/filters. |
| **P1 â€” planner** | `PlanExecutor` | Má»™t request cÃ³ Ã­t nháº¥t má»™t LLM call; JSON lá»—i thÃ¬ retry; `reflect_rounds > 0` cÃ³ thá»ƒ thÃªm nhiá»u LLM call vÃ  cháº¡y láº¡i toÃ n bá»™ plan. `build_tool_prompt` serializes description + input/output schema cá»§a táº¥t cáº£ tools vÃ o system prompt má»—i plan. | Äo latency/tokens theo plan attempt, reflect, sá»‘ steps; giáº£m schema/prompt dÆ° thá»«a hoáº·c expose tools theo task náº¿u Ä‘Ã¡nh giÃ¡ chá»©ng minh khÃ´ng lÃ m giáº£m tool-selection accuracy. TrÆ°á»›c tiÃªn xem P95 vÃ  sá»‘ call thá»±c táº¿. |
| **P1 â€” candidate reach** | `ItemCFTool` / retrieval candidates | ItemCF chá»‰ cÃ³ top-k neighbors Ä‘Ã£ lÆ°u cho má»—i seed; lá»c domain sau khi tá»•ng há»£p, nÃªn cÃ³ thá»ƒ tráº£ Ã­t hÆ¡n `top_k`. `RecoModelTool` chá»‰ xáº¿p háº¡ng danh sÃ¡ch Ä‘áº§u vÃ o; khÃ´ng tá»± tÃ¬m item bá»‹ retriever bá» sÃ³t. | Candidate Recall@K theo tá»«ng retriever/segment lÃ  cá»•ng báº¯t buá»™c. TÄƒng `top_k` chá»‰ cÃ³ Ã­ch náº¿u candidate pool chá»©a target; theo dÃµi candidate count, duplicate rate, target reach. |
| **P2 â€” scoring** | `RecoModelTool.execute` | Táº¡o NumPy array candidate IDs, score toÃ n bá»™ candidate, rá»“i `argsort` toÃ n bá»™ danh sÃ¡ch Ä‘á»ƒ láº¥y `top_k`. | Náº¿u candidate pool thá»±c táº¿ lá»›n, dÃ¹ng partial top-k (`argpartition` + sort top-k) cÃ³ thá»ƒ giáº£m sorting; cáº§n tie-break á»•n Ä‘á»‹nh vÃ  test thá»© tá»±. Vá»›i giá»›i háº¡n candidates hiá»‡n táº¡i nhá», cÃ³ thá»ƒ chÆ°a Ä‘Ã¡ng lÃ m. |
| **P2 â€” model fit** | `ItemKNNMatrixRecommender._fit` | XÃ¢y similarity theo block nhÆ°ng má»—i block váº«n materialize ma tráº­n dense `(block_items, num_items)`; `block_elements` giá»›i háº¡n pháº§n tá»­, khÃ´ng pháº£i peak RSS toÃ n hÃ m. | Äo peak RAM vÃ  fit time theo catalog size; kiá»ƒm tra dtype trÆ°á»›c `toarray()`/`astype(float32)` Ä‘á»ƒ trÃ¡nh báº£n sao dÆ°; tÄƒng/giáº£m `block_elements` theo RAM thá»±c. KhÃ´ng Æ°u tiÃªn trÆ°á»›c correctness/latency request. |
| **P2 â€” eval** | `Recommender.recommend` / `evaluate_recommender` | Ranking full catalog cáº§n táº¡o score matrix cho batch user vÃ  sau Ä‘Ã³ chá»n top-k. Batch Ä‘Æ°á»£c giá»›i háº¡n qua `batch_elements`, nhÆ°ng cÃ³ thá»ƒ tá»‘n CPU/RAM. | Cháº¡y benchmark theo `num_users Ã— num_items`, theo dÃµi peak RAM; giáº£m batch khi OOM, tÄƒng batch chá»‰ khi throughput tÄƒng vÃ  RAM cÃ²n dÆ°. TÃ¡ch fit time khá»i eval time. |
| **P2 â€” final answer** | `compose_llm` | Khi mode LLM, answer generation lÃ  má»™t call ná»¯a; grounding/JSON lá»—i cÃ³ thá»ƒ kÃ­ch hoáº¡t retry, rá»“i template fallback. NÃ³ trÃ¬nh bÃ y items, khÃ´ng sá»­a ranking. | Náº¿u metric chÃ­nh lÃ  ranking, Ä‘Ã¡nh giÃ¡ `template` trÆ°á»›c Ä‘á»ƒ cÃ´ láº­p agent/retriever. Chá»‰ báº­t LLM inference khi Ä‘o answer quality, grounding, token cost vÃ  latency riÃªng. |

## 18.3. Tá»«ng tool: chi phÃ­, giá»›i háº¡n, hÆ°á»›ng tá»‘i Æ°u

|Tool|Chi phÃ­ chÃ­nh|Giá»›i háº¡n|Tá»‘i Æ°u há»£p lÃ½|
|---|---|---|---|
|`ItemCFTool`|tá»•ng non-zero similarity cá»§a cÃ¡c seed row + sort candidate há»£p nháº¥t|chá»‰ cÃ³ top-k neighbors Ä‘Ã£ lÆ°u; lá»c `domain` **sau** khi cáº¯t â‡’ cÃ³ thá»ƒ tráº£ Ã­t hÆ¡n `top_k`|Ä‘o candidate count/latency theo sá»‘ seed Ã— domain; khÃ´ng densify|
|`RecoModelTool`|O(C) map/filter + scorer + O(C log C) sort|chá»‰ xáº¿p háº¡ng candidate Ä‘áº§u vÃ o, khÃ´ng tÃ¬m item bá»‹ bá» sÃ³t; `unscored_item_ids` bá»‹ loáº¡i|partial top-k náº¿u C lá»›n; cache `seen_items` trong pháº¡m vi 1 request|
|`SemanticSearchTool`|FTS match + JOIN/filter + ORDER BY + **COUNT láº§n hai**|**lexical** (FTS5/BM25), khÃ´ng pháº£i embedding; query cáº§n tiáº¿ng Anh; category pháº£i exact|tÃ¡ch timing fetch/count; `EXPLAIN QUERY PLAN`; Ä‘o empty-result rate|
|`SQLTool`|2 query (SELECT + `COUNT(*)`)|`limit` khÃ´ng giáº£m chi phÃ­ sort/count|cháº¿ Ä‘á»™ `include_total=False` náº¿u caller khÃ´ng cáº§n; index theo query plan|
|`QueryTool`|1 query `IN (â€¦)` theo batch|tráº§n `MAX_QUERY_ROWS`; nhiá»u placeholder náº¿u list dÃ i|má»™t batch id list, khÃ´ng gá»i láº·p tá»«ng item|
|`MemoryTool`|scan/filter cáº£ DataFrame má»—i call + 2 query `IN (â€¦)`|category Ä‘áº¿m theo interaction (1 category láº·p nhiá»u láº§n)|index history theo user lÃºc build (giá»¯ cutoff); benchmark build-time vs per-call|
|`Tool.__call__`|hash kwargs báº±ng JSON + `len(str(data))` + logger giá»¯ má»i record + append file má»—i call|chi phÃ­ tÄƒng theo kÃ­ch thÆ°á»›c candidate list|summary cÃ³ cáº¥u trÃºc (`candidate_count`, `n_keys`); logger `off/basic/full`; batch writes|

## 18.4. Agent / framework

- **`PlanExecutor`**: â‰¥ 1 LLM call má»—i request; JSON lá»—i thÃ¬ retry; `reflect_rounds > 0` thÃªm call + cháº¡y láº¡i plan. Äo `first_attempt_ok`, `reflections`, `plan_attempts`, `n_steps`, latency/token theo tá»«ng attempt.
- **`build_tool_prompt`**: description + input/output schema cá»§a **má»i** tool vÃ o system prompt â‡’ context cost. Äo prompt tokens; náº¿u compact theo intent thÃ¬ pháº£i kiá»ƒm `tool_selection_ok` vÃ  Ä‘á»«ng xoÃ¡ field cáº§n cho ref `$N.path`.
- **`Type1Agent`**: deterministic, khÃ´ng tá»‘n LLM planning, dá»… benchmark â€” nhÆ°ng chá»‰ ItemCF + seed, cold/seed rá»—ng lÃ  fail sá»›m.
- **`extract_recommendations`**: Æ°u tiÃªn `ranked` > retrieval > `QueryTool` â‡’ Ä‘á»c `tool_selection_ok`/`n_steps`, khÃ´ng chá»‰ "list cÃ³ rá»—ng hay khÃ´ng".
- **Inference**: template Ä‘á»ƒ cÃ´ láº­p agent/retriever; chá»‰ báº­t LLM khi Ä‘o answer quality + grounding + token/latency.
- **Provider**: `urllib` Ä‘á»“ng bá»™, khÃ´ng batch/async; má»i so sÃ¡nh pháº£i ghi model, base_url, timeout, retries, tokens.

## 18.5. Model / data / evaluation

- **ItemKNN fit:** má»—i block váº«n materialize ma tráº­n dense `(block_items, num_items)` â€” `block_elements` khÃ´ng pháº£i peak RSS. Äo fit time + peak RAM + nnz.
- **Offline eval:** `Recommender.recommend` cháº¥m toÃ n catalog theo batch, khÃ¡c `RecoModelTool` (rank subset) â‡’ **khÃ´ng** dÃ¹ng timing offline lÃ m latency online.
- **Cháº©n Ä‘oÃ¡n theo báº­c:** candidate recall tháº¥p â†’ retriever/query/seed; candidate recall tá»‘t mÃ  Recall@10 tháº¥p â†’ scorer/seen/mapping/split; ranking tá»‘t mÃ  task success tháº¥p â†’ constraint/tool lá»—i; task success cao mÃ  Recall@10 = 0 â†’ metric success khÃ´ng Ä‘áº¡i diá»‡n relevance.

## 18.6. Protocol benchmark (trÆ°á»›c khi sá»­a code)

Ghi Ä‘á»§: commit/hash + config snapshot + fingerprint dataset/split; model/scorer, seed, `top_k`, segment, request IDs cá»‘ Ä‘á»‹nh; warm-up + sá»‘ láº§n láº·p + median/P95 (khÃ´ng chá»‰ mean) + peak RAM; per-request `wall_seconds`, per-step tool name/ok/latency, LLM calls/tokens, reflection/retry counts; candidate count trÆ°á»›c/sau filter, `unscored_item_ids`, target-in-candidates; **cÃ¹ng má»™t táº­p request** cho before/after (khÃ´ng trá»™n Ä‘á»•i prompt + model + split + tool trong má»™t ablation).

## 18.7. Bá»‘n Ä‘á»£t tá»‘i Æ°u

1. **Äá»£t 0 â€” baseline, khÃ´ng Ä‘á»•i behavior:** cháº¡y táº­p request cá»‘ Ä‘á»‹nh, lÆ°u trajectory + tool log; bÃ¡o median/P95 theo agent Ã— kind Ã— segment; ghi cáº£ candidate reach + ranking metrics.
2. **Äá»£t 1 â€” correctness trÆ°á»›c tá»‘c Ä‘á»™:** test ma tráº­n báº¥t Ä‘á»‘i xá»©ng Ä‘á»ƒ khoÃ¡ convention `BaselineScorer` / `BaselineItemKNNRecommender` / `ItemKNNMatrixRecommender`; kiá»ƒm mapping id, exclude-seen, unknown, cold start; xá»­ lÃ½ segment cÃ³ Recall@K = 0 trÆ°á»›c khi tune.
3. **Äá»£t 2 â€” hot path cÃ³ báº±ng chá»©ng:** logger on/off/basic; index `MemoryTool` theo user; bá» phÃ©p nhÃ¢n sparse láº·p giá»¯a `score` vÃ  `has_personal_signal`; tuá»³ chá»n bá» COUNT; chá»‰ sau Ä‘Ã³ má»›i tá»›i partial top-k / prompt compression.
4. **Äá»£t 3 â€” quality cÃ³ ablation:** so Popularity / ItemCF / Semantic / SQL / union theo Recall@50/100/200 + latency; tÄƒng pool chá»‰ khi candidate recall cÃ²n room; tune ranker sau khi target reach Ä‘Æ°á»£c.

## 18.8. Káº¿t luáº­n

Äá»«ng tá»‘i Æ°u táº¥t cáº£ tool cÃ¹ng lÃºc: **xÃ¡c minh correctness cá»§a scorer trÆ°á»›c**, rá»“i Ä‘o vÃ  giáº£m overhead trong `Tool.__call__`/logger vÃ  `MemoryTool`, sau Ä‘Ã³ profile COUNT vÃ  planner LLM call. Song song, candidate recall quyáº¿t Ä‘á»‹nh tráº§n cháº¥t lÆ°á»£ng cá»§a ranker. Má»i cáº£i tiáº¿n pháº£i bÃ¡o **cáº£ latency láº«n quality**.

> Checklist "sá»­a ngay / chÆ°a nÃªn sá»­a" vÃ  20.9 chi tiáº¿t Ä‘Ã£ bá» khi tinh gá»n 30/10; ná»™i dung Ä‘Ã£ gá»™p vÃ o 4 Ä‘á»£t á»Ÿ 20.7.

---

# 19. Snapshot artifact 27/10 â€” `exp_009`â€“`exp_013`, ablation, component benchmark

> **Pháº¡m vi:** cÃ¡c artifact trong `experiments/agent_eval/` sinh ngÃ y **26â€“27/10**, Ä‘á»c ngÃ y **29/10**. Sá»‘ liá»‡u láº¥y trá»±c tiáº¿p tá»« `config.yaml`, `metrics.json`, `scored.jsonl`, `ablation/*/report.md` + `comparison.json`, `component_benchmarks/*.json`, `memory_utility_analysis/memory_utility.md`. **KhÃ´ng** pháº£i tÃ´i cháº¡y láº¡i experiment. Má»¥c 19â€“20 (snapshot 20/10) giá»¯ nguyÃªn Ä‘á»ƒ Ä‘á»‘i chiáº¿u lá»‹ch sá»­; chá»— nÃ o khÃ¡c nhau thÃ¬ má»¥c nÃ y má»›i hÆ¡n.

## 19.1. NÄƒm run agent_eval má»›i â€” cáº¥u hÃ¬nh thá»±c táº¿

| Run | Thá»i Ä‘iá»ƒm (UTC) | Commit | `reflect_rounds` | `inference_mode` | `per_segment` | `n_requests` | runtime |
|---|---|---|---|---|---|---|---|
| `exp_009` | 26/10 09:35 | `ec14e6d` | 0 | template | 15 | 66 | 851 s |
| `exp_010` | 26/10 10:09 | `ec14e6d` | 1 | template | 15 | 66 | 961 s |
| `exp_011` | 27/10 09:39 | `7828141` | 1 | llm | 2 | 14 | 571 s |
| `exp_012` | 27/10 10:16 | `7828141` | 0 | llm | 15 | 66 | 2.203 s |
| `exp_013` | 27/10 11:05 | `7828141` | 1 | llm | 15 | 66 | 2.339 s |

Chung cho cáº£ 5 run: `eval_on=validation`, `seed=42`, `k=10`, `request_scope=realistic`, `sparse_max=4`, `item_knn_k=20`, `llm_model=gpt-5.4`, agent `baseline / type1 / planner / planner_memory`.

Ba Ä‘iá»ƒm dá»… Ä‘á»c sai:

- **KhÃ´ng cÃ²n kind ORACLE.** `request_scope=realistic` â‡’ chá»‰ cÃ³ `personalized` (30), `similar` (30), `ambiguous` (6); **khÃ´ng cÃ³ `constrained` / `cold_text`**. VÃ¬ váº­y má»i so sÃ¡nh ORACLE á»Ÿ má»¥c 19 (exp_004/007/008) khÃ´ng ná»‘i tiáº¿p Ä‘Æ°á»£c vá»›i loáº¡t run nÃ y.
- **`exp_011` lÃ  smoke run** (`per_segment=2` â‡’ 4 request/kind, 14 request), Ä‘á»«ng so trá»±c tiáº¿p vá»›i run 66 request.
- **26/10 â‰  27/10 vá» artifact:** `mapping_hash` cá»§a `exp_009/010` lÃ  `13e3e5b3â€¦`, cá»§a `exp_011â€“013` lÃ  `1160c09bâ€¦`; tá»« 27/10 má»›i cÃ³ `mapping_hash_protocol: sorted_key_index_json_v1` vÃ  `sha256` cho tá»«ng split (`train/validation/test` giá»‘ng nhau giá»¯a 011â€“013). KhÃ´ng gá»™p hai nhÃ³m nÃ y thÃ nh má»™t chuá»—i.

## 19.2. `personalized` (n = 30 má»—i Ã´) â€” nÆ¡i khÃ¡c biá»‡t náº±m á»Ÿ Ä‘Ã¢u

| Run (reflect / inference) | Agent | recall@10 | task_success | first_attempt_ok | reflections | steps_ok_rate | answer_status_ok | answer_status_tool_error | wall p50 (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `exp_009` (0 / template) | `planner` | 0.000 | â€” | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.44 |
| `exp_009` (0 / template) | `planner_memory` | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.31 |
| `exp_010` (1 / template) | `planner` | 0.000 | â€” | 1.000 | 0.000 | 1.000 | 0.967 | 0.000 | 6.46 |
| `exp_010` (1 / template) | `planner_memory` | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.46 |
| `exp_012` (0 / llm) | `planner` | 0.000 | â€” | 0.400 | 0.000 | 0.600 | 0.400 | 0.600 | 5.85 |
| `exp_012` (0 / llm) | `planner_memory` | 0.000 | 0.400 | 0.400 | 0.000 | 0.577 | 0.533 | 0.467 | 5.49 |
| `exp_013` (1 / llm) | `planner` | 0.000 | â€” | 0.567 | 0.433 | 0.949 | 0.800 | 0.067 | 5.50 |
| `exp_013` (1 / llm) | `planner_memory` | 0.000 | 0.933 | 0.500 | 0.500 | 0.964 | 0.967 | 0.033 | 8.66 |

Ã” `task_success = â€”` cá»§a `planner` **khÃ´ng pháº£i lá»—i dá»¯ liá»‡u**: `score_trajectory.py:66-70` chá»§ Ä‘á»™ng Ä‘áº·t `task_success = tool_selection_ok = None` cho `personalized` + planner **khÃ´ng cÃ³** `MemoryTool`, vÃ¬ planner Ä‘Ã³ khÃ´ng cÃ³ cÃ¡ch cÃ¡ nhÃ¢n hoÃ¡ trung thá»±c (há»i láº¡i váº«n Ä‘Æ°á»£c coi lÃ  há»£p lá»‡). Há»‡ quáº£: muá»‘n nÃ³i vá» memory trÃªn `personalized` thÃ¬ pháº£i so `planner_memory` vá»›i baseline, hoáº·c cháº¥p nháº­n Ã´ `planner` bá»‹ bá» trá»‘ng.

- `similar` (n = 30) vÃ  `ambiguous` (n = 6): `task_success` = 1.000 cho má»i agent á»Ÿ cáº£ 5 run; `ambiguous` cÃ³ `asked_clarification` = 1.000; `recall@10` = 0.000 á»Ÿ má»i Ã´ `similar`.
- **`recall@10` vÃ  `ndcg@10` = 0.000 á»Ÿ *toÃ n bá»™* 5 run**, ká»ƒ cáº£ `baseline` vÃ  `type1`. ÄÃ¢y váº«n lÃ  váº¥n Ä‘á» cá»§a Â§19.6 chá»© khÃ´ng pháº£i phÃ¡t hiá»‡n má»›i, nhÆ°ng nÃ³ cÃ³ nghÄ©a: **khÃ´ng thá»ƒ dÃ¹ng loáº¡t run nÃ y Ä‘á»ƒ so cháº¥t lÆ°á»£ng gá»£i Ã½**; chá»‰ so Ä‘Æ°á»£c hÃ nh vi agent (plan, step, tool, answer).

## 19.3. Reflection: cáº·p so sÃ¡nh **sáº¡ch** Ä‘áº§u tiÃªn â€” `exp_012` vs `exp_013`

ÄÃ¢y lÃ  Ä‘iá»ƒm má»›i quan trá»ng nháº¥t cá»§a loáº¡t artifact nÃ y. Má»¥c 19 tá»«ng káº¿t luáº­n "chÆ°a cÃ³ ablation reflection sáº¡ch" vÃ¬ `exp_007`/`exp_008` khÃ¡c inference mode. `exp_012` vÃ  `exp_013` **giá»‘ng nhau má»i thá»©** (cÃ¹ng commit, cÃ¹ng split + `mapping_hash`, cÃ¹ng 66 request, `inference_mode=llm`, `seed=42`), chá»‰ khÃ¡c `reflect_rounds` 0 â†’ 1. BÃ¡o cÃ¡o: `ablation/planner_reflect0_vs_reflect1/` (66 paired requests, bootstrap 10.000, 95%).

| `personalized` (n = 30) | `exp_012` (r0) | `exp_013` (r1) | Diff | 95% CI |
|---|---:|---:|---:|---|
| `first_attempt_ok` | 0.400 | 0.567 | **+0.167** | [âˆ’0.133, +0.467] â€” McNemar b=8, c=13, **p = 1.000** |
| `reflections` | 0.000 | 0.433 | +0.433 | [+0.267, +0.600] |
| `steps_ok_rate` | 0.600 | 0.949 | +0.349 | (tá»« `metrics.json`) |
| `answer_status_ok` | 0.400 | 0.800 | +0.400 | (tá»« `metrics.json`) |
| `answer_status_tool_error` | 0.600 | 0.067 | **âˆ’0.533** | (tá»« `metrics.json`) |
| `llm_latency_seconds` | 5.98 | 7.41 | **+1.43 s** | [+0.226, +2.643] |
| `completion_tokens` | 346.0 | 457.9 | +111.9 | [+17.6, +208.0] |
| `inference_latency_seconds` | 3.29 | 5.82 | **+2.53 s** | [+0.578, +4.329] |
| `inference_completion_tokens` | 304.7 | 579.8 | +275.1 | [+88.6, +441.3] |

á»ž `similar` vÃ  `ambiguous` hai run gáº§n nhÆ° trÃ¹ng nhau (`first_attempt_ok` = 1.000 cáº£ hai; `llm_latency` 4.43 â†’ 4.19 s á»Ÿ `similar`, 3.25 â†’ 3.85 s á»Ÿ `ambiguous`).

**Äá»c tháº¿ nÃ o cho Ä‘Ãºng:**

1. CÃ³ **tÃ­n hiá»‡u rÃµ** ráº±ng reflection sá»­a Ä‘Æ°á»£c lá»—i tool á»Ÿ `personalized`: 60% request lá»—i á»Ÿ láº§n Ä‘áº§u (r0) xuá»‘ng cÃ²n 6,7% (r1); 43% request thá»±c sá»± pháº£i reflect.
2. **ChÆ°a pháº£i báº±ng chá»©ng thá»‘ng kÃª:** má»—i nhÃ³m chá»‰ **1 run** (bÃ¡o cÃ¡o ghi "Only 1 run per group, cannot compute variance"), n = 30, vÃ  McNemar cho `first_attempt_ok` ra **p = 1.000** â€” tá»©c chÆ°a Ä‘á»§ Ä‘á»ƒ káº¿t luáº­n.
3. **GiÃ¡ pháº£i tráº£:** +1,4 s planner latency vÃ  +2,5 s inference latency má»—i request `personalized`, cá»™ng thÃªm ~390 completion tokens.
4. Reflection **khÃ´ng** cáº£i thiá»‡n `recall@10` (váº«n 0.000 á»Ÿ má»i Ã´) â€” nÃ³ sá»­a *cÃ¡ch cháº¡y*, khÃ´ng sá»­a *cháº¥t lÆ°á»£ng gá»£i Ã½*.

## 19.4. Memory: `planner_memory` vs `planner` trÃªn cÃ¹ng run

**Trong `exp_013`** (`ablation/memory_vs_no_memory/`, cÃ¹ng 66 request):

- `similar`: hai agent **giá»‘ng há»‡t** (`task_success` 1.000, `first_attempt_ok` 1.000, `recall@10` 0.000). Chi phÃ­ cá»§a memory: `llm_latency` 4.357 â†’ 6.351 s á»Ÿ segment `warm` (+1.99 s), `answer_fallback` 0 â†’ 0.033.
- `personalized`: `planner` **khÃ´ng Ä‘Æ°á»£c cháº¥m** `task_success` (má»¥c 21.2) nÃªn chá»‰ so Ä‘Æ°á»£c hÃ nh vi: `first_attempt_ok` 0.567 vs 0.500; `steps_ok_rate` 0.949 vs 0.964; `answer_status_ok` 0.800 vs **0.967**; `answer_status_tool_error` 0.067 vs **0.033**; `wall p50` 5.50 s vs 8.66 s. `planner_memory` cÃ³ `task_success` = 0.933.
- Contrast nÃ y **bá» sÃ³t `personalized`**: `configs/agent/ablation.yaml` khai bÃ¡o `memory_vs_no_memory.kinds: [similar, constrained, cold_text]`, mÃ  `constrained`/`cold_text` khÃ´ng tá»“n táº¡i trong run realistic â‡’ bÃ¡o cÃ¡o chá»‰ cÃ²n `similar`, Ä‘Ãºng loáº¡i request mÃ  memory khÃ´ng thá»ƒ giÃºp gÃ¬.

**Trong `planner_memory_reflect0_vs_reflect1`** (r0 vs r1, cÃ¹ng `exp_012`/`exp_013`): `personalized` lÃ  nÆ¡i duy nháº¥t thay Ä‘á»•i máº¡nh â€” `task_success` 0.333 â†’ 0.933 á»Ÿ segment `sparse` (+0.600) vÃ  0.467 â†’ 0.933 á»Ÿ `warm` (+0.467); `llm_latency` +3.42 s / +2.19 s. CÆ¡ cháº¿ khá»›p vá»›i 21.3: `task_success` (v2) Ä‘Ã²i `answer_status = ok` **vÃ ** grounded, nÃªn sá»­a lá»—i tool báº±ng reflection lÃ  Ä‘iá»u kiá»‡n Ä‘á»ƒ Ã´ nÃ y cÃ³ Ä‘iá»ƒm.

**`memory_utility_analysis/`** (sinh 27/10 09:16) lÃ  phÃ¢n tÃ­ch ghÃ©p cáº·p 3 run/arm, bootstrap 5.000, `min_n = 20` â€” nhÆ°ng trÃªn **run cÅ© 20 request** (6 ORACLE + 14 realistic; `docs/evaluation/FINAL_SUMMARY.md` ghi lÃ  `exp_002`â€“`exp_004`), **khÃ´ng pháº£i** `exp_012/013`. Káº¿t quáº£: **má»i nhÃ³m Ä‘á»u `inconclusive`** vÃ¬ n < 20. VÃ i con sá»‘ Ä‘á»ƒ tham kháº£o, khÃ´ng Ä‘á»ƒ trÃ­ch dáº«n nhÆ° káº¿t luáº­n:

| Metric | Realistic (n=14) | Personalized (n=4) |
|---|---|---|
| `task_success` | 0.857 â†’ 0.929 (+0.071, CI [0.000, +0.214]) | 0.500 â†’ 0.750 (+0.250, CI [0.000, +0.750]) |
| `recall@10` | 0.000 â†’ 0.000 | 0.000 â†’ 0.000 |
| `llm_latency_seconds` | 12.25 â†’ 11.43 | 13.24 â†’ 15.04 |

â‡’ Káº¿t luáº­n trung thá»±c: **chÆ°a cÃ³ báº±ng chá»©ng memory cáº£i thiá»‡n cháº¥t lÆ°á»£ng**; chá»‰ cÃ³ tÃ­n hiá»‡u vá» hÃ nh vi/Ä‘á»™ trá»…, vÃ  má»i verdict Ä‘á»u `inconclusive`.

**Cháº¡y láº¡i `memory_utility.py` trÃªn 2 run má»›i (29/10)** â€” lá»‡nh: `--dirs experiments/agent_eval/exp_012 experiments/agent_eval/exp_013 --min-n 20 --resamples 5000` (66 request, **2 run/arm**, output ghi ra ngoÃ i repo):

| Metric | `realistic` (n = 66) | `personalized` (n = 30) | verdict |
|---|---|---|---|
| `task_success` | +0.000 [+0.000, +0.000] | **`no_pairs`** â€” planner khÃ´ng cháº¥m, `unscored` 30/0 | inconclusive / no_pairs |
| `recall@10`, `ndcg@10` | +0.000 (30 cáº·p) | +0.000 (30 cáº·p) | inconclusive |
| `first_attempt_ok` | âˆ’0.015 [âˆ’0.098, +0.068] | âˆ’0.033 [âˆ’0.217, +0.150] | inconclusive |
| `completion_tokens` | +7.3 [âˆ’18.6, +33.7] | +6.2 [âˆ’50.3, +63.7] | inconclusive |
| `llm_latency_seconds` | +0.323 [âˆ’0.272, +1.073] | +0.206 [âˆ’0.628, +1.049] | inconclusive |
| `constraint_satisfaction` | `no_pairs` (66/66) | `no_pairs` (30/30) | â€” |

Tá»•ng: **1 `memory_worse`, 46 `inconclusive`, 16 `no_pairs`**. Verdict duy nháº¥t: `completion_tokens` á»Ÿ `similar` +11,3 token [+2,75, +19,98] (W/L/T 22/7/1) â€” memory **tá»‘n token hÆ¡n** ngay cáº£ á»Ÿ loáº¡i request mÃ  nÃ³ khÃ´ng giÃºp gÃ¬.

> **Cáº£nh bÃ¡o phÆ°Æ¡ng phÃ¡p:** hai run nÃ y khÃ¡c `reflect_rounds` (0 vs 1), nÃªn bÆ°á»›c "trung bÃ¬nh qua cÃ¡c run" Ä‘ang trá»™n **hai Ä‘iá»u kiá»‡n**; cá»™t `run-std` vÃ¬ tháº¿ pháº£n Ã¡nh hiá»‡u á»©ng reflection chá»© khÃ´ng pháº£i nhiá»…u LLM. `memory_utility.py` **khÃ´ng** kiá»ƒm tra tÆ°Æ¡ng thÃ­ch config giá»¯a cÃ¡c run (khÃ¡c `ablation/_loader.check_compatibility`). VÃ¬ váº­y láº§n cháº¡y nÃ y chá»‰ dÃ¹ng Ä‘á»ƒ **kiá»ƒm tra pipeline cháº¡y Ä‘Ãºng**, khÃ´ng dÃ¹ng Ä‘á»ƒ káº¿t luáº­n vá» memory.

## 19.5. Component benchmark â€” `experiments/agent_eval/component_benchmarks/`

Sá»‘ dÆ°á»›i Ä‘Ã¢y láº¥y tá»« file **má»›i nháº¥t** cá»§a tá»«ng component (26â€“27/10), `run_count` ghi trong file.

| Component | File | Cases | Runs | Metric chÃ­nh | Latency |
|---|---|---:|---:|---|---|
| `memory` (fixture) | `memory_benchmark_20261027_114412.json` | 16 | 3 | `known_correct` 0.188, `n_interactions_correct` 0.188, `price_range_correct` 0.313, `recent_items_match` 0.250, `top_categories_match` 0.250 | ~0 |
| `memory_correctness` (oracle) | `memory_correctness_current.json` | 16 | 1 | `all_fields_match` 1.000, `error_behavior_correct` 1.000, `future_leakage` **0.000** (khÃ´ng rÃ²) | ~1 ms |
| `planner` (LLM tháº­t) | `planner_benchmark_20261027_084904.json` | 4 | 1 | `plan_validity` 1.000, `tool_selection_accuracy` 0.500, `argument_correctness` **0.375**, `constraint_handling` 0.500, `reference_correctness` 0.750, `clarification_precision` 0.500 / `recall` 0.750 | mean **5.29 s**, p95 7.84 s |
| `executor` + reflection | `executor_benchmark_20261027_084905.json` | 5 | 1 | `all_steps_ok` 0.600, `reflection_triggered` 0.400, `reflection_rescued` **0.000**, `reflection_worsened` 0.000, `reflection_no_change` 1.000 | ~0.1 ms |
| `grounding` (rule-based) | `grounding_benchmark_20261027_084906.json` | 5 | 1 | `grounding_rate` 0.800, `hallucination_rate` 0.200, `prompt_injection_detected` 0.200 | ~0 |
| `integration` | `integration_benchmark_20261027_114417.json` | 7 | 3 | `contract_valid` 0.571, `no_mismatch` 0.571 | ~0 |

Ba Ä‘iá»u cáº§n biáº¿t khi Ä‘á»c báº£ng nÃ y:

- **Hai benchmark memory cho káº¿t quáº£ trÃ¡i ngÆ°á»£c** (0.188 vs 1.000) vÃ¬ Ä‘o hai thá»© khÃ¡c nhau: `memory_benchmark` so vá»›i **fixture ká»³ vá»ng** trong `memory_correctness_dataset.jsonl`, cÃ²n `memory_correctness` so vá»›i **oracle Ä‘á»™c láº­p** (`memory_oracle.py`, khÃ´ng import `MemoryTool`/`ItemCorpus`). ChÃªnh lá»‡ch nÃ y **chÆ°a Ä‘Æ°á»£c Ä‘iá»u tra** â€” cÃ³ thá»ƒ fixture sai, cÃ³ thá»ƒ hai bÃªn hiá»ƒu khÃ¡c nhau vá» `recent_items`/`top_categories`. Äá»«ng trÃ­ch "memory Ä‘Ãºng 100%" mÃ  bá» qua Ã´ 0.188 (vÃ  ngÆ°á»£c láº¡i).
- **`run_all.py` chÆ°a gom Ä‘Æ°á»£c Ä‘á»§ 5 component:** `unified_report_20261027_184417.md` ghi 2/5 success, cÃ²n `planner` / `executor` / `grounding` lÃ  "Benchmark did not run". CÃ¡c file benchmark riÃªng cá»§a 3 component Ä‘Ã³ **váº«n cÃ³** (báº£ng trÃªn), nÃªn Ä‘Ã¢y lÃ  lá»—i cá»§a bÆ°á»›c tá»•ng há»£p, chÆ°a pháº£i lá»—i benchmark.
- TÃ¡c giáº£ Ä‘Ã£ tá»± tá»•ng há»£p trong `docs/evaluation/FINAL_SUMMARY.md` + 6 file theo phase; cÃ¡c "missing parts" Ä‘Æ°á»£c ghi á»Ÿ Ä‘Ã³ váº«n Ä‘Ãºng: **Jev cáº§n Typesafe API key** (OpenRouter key tráº£ 401), **reflection cáº§n LLM tháº­t** (mock LLM khÃ´ng táº¡o Ä‘Æ°á»£c plan sá»­a), **sample size 4â€“16 case** lÃ  quÃ¡ nhá».

## 19.6. CÃ¡i gÃ¬ Ä‘Ã£ chá»©ng minh Ä‘Æ°á»£c, cÃ¡i gÃ¬ chÆ°a

| Nháº­n Ä‘á»‹nh | Báº±ng chá»©ng trong artifact | Tráº¡ng thÃ¡i |
|---|---|---|
| Reflection sá»­a Ä‘Æ°á»£c lá»—i tool á»Ÿ `personalized` | `exp_012` vs `exp_013`: `answer_status_tool_error` 0.600 â†’ 0.067; `steps_ok_rate` 0.600 â†’ 0.949 | **TÃ­n hiá»‡u máº¡nh**, nhÆ°ng 1 run/nhÃ³m, n = 30, McNemar p = 1.000 â†’ chÆ°a káº¿t luáº­n |
| Reflection lÃ m agent "gá»£i Ã½ tá»‘t hÆ¡n" | `recall@10` = 0.000 á»Ÿ cáº£ hai run | **KhÃ´ng** â€” khÃ´ng cÃ³ báº±ng chá»©ng |
| Memory cáº£i thiá»‡n cháº¥t lÆ°á»£ng gá»£i Ã½ | `memory_utility_analysis` má»i nhÃ³m `inconclusive`; `recall@10` = 0 | **ChÆ°a chá»©ng minh** |
| Memory lÃ m cÃ¢u tráº£ lá»i á»•n Ä‘á»‹nh hÆ¡n | `answer_status_ok` 0.800 â†’ 0.967 vÃ  `tool_error` 0.067 â†’ 0.033 (`exp_013`, `personalized`) | TÃ­n hiá»‡u, cÃ¹ng run, chÆ°a láº·p |
| Agent > baseline vá» recommendation | `baseline`/`type1`/`planner` Ä‘á»u `recall@10` = 0 á»Ÿ `similar` | **KhÃ´ng thá»ƒ káº¿t luáº­n** â€” metric chÆ°a phÃ¢n biá»‡t Ä‘Æ°á»£c |
| Tá»«ng component cháº¡y Ä‘Ãºng há»£p Ä‘á»“ng | planner `plan_validity` 1.000 nhÆ°ng `argument_correctness` 0.375; integration `contract_valid` 0.571 | **Má»™t pháº§n** â€” cÃ²n lá»—i há»£p Ä‘á»“ng cá»¥ thá»ƒ |
| Há»‡ thá»‘ng eval Ä‘Ã£ Ä‘á»§ tin Ä‘á»ƒ viáº¿t káº¿t quáº£ | 10 test Ä‘á» (má»¥c 12), `run_all` 2/5 component, Jev 401, ORACLE kind bá»‹ bá» khá»i run má»›i | **ChÆ°a** |

## 19.7. Viá»‡c tiáº¿p theo (Ä‘á» xuáº¥t, theo thá»© tá»±)

1. **Láº·p `exp_012`/`exp_013` â‰¥ 3 láº§n** Ä‘á»ƒ cÃ³ phÆ°Æ¡ng sai cho cÃ¢u "reflection giáº£m lá»—i tool" â€” **cáº§n LLM tháº­t** (`LLM_BASE_URL` + `LLM_API_KEY`), má»—i run ~37â€“39 phÃºt nÃªn 3+3 run â‰ˆ 4 giá»; **chÆ°a cháº¡y Ä‘Æ°á»£c á»Ÿ mÃ´i trÆ°á»ng hiá»‡n táº¡i** (ba biáº¿n `LLM_*` Ä‘á»u rá»—ng). Lá»‡nh (Ä‘Ã£ kiá»ƒm qua `--help`): `python scripts/evaluation/run_agent_eval.py --reflect-rounds 0 --inference-mode llm --trajectory-file agent_llm_r0_rep2.jsonl`, láº·p láº¡i vá»›i `--reflect-rounds 1`; má»—i láº§n tá»± sinh `exp_NNN` má»›i.
2. **`memory_utility.py`**: pipeline Ä‘Ã£ cháº¡y Ä‘Æ°á»£c (29/10 â€” báº£ng á»Ÿ 21.4) nhÆ°ng trÃªn 2 run **khÃ¡c Ä‘iá»u kiá»‡n**, nÃªn chá»‰ Ä‘á»ƒ kiá»ƒm tra cÃ´ng cá»¥; muá»‘n káº¿t luáº­n cáº§n â‰¥ 3 run **cÃ¹ng cáº¥u hÃ¬nh**. Äá»“ng thá»i **thÃªm `personalized`** vÃ o `memory_vs_no_memory.kinds` (hiá»‡n chá»‰ cÃ²n `similar`) vÃ  nÃªn bá»• sung kiá»ƒm tra tÆ°Æ¡ng thÃ­ch config nhÆ° `ablation/_loader.check_compatibility`.
3. **Tráº£ lá»i "vÃ¬ sao recall@10 = 0"** trÆ°á»›c khi tune planner: cháº¡y `diagnose_splits.py` + `candidate_recall.py` trÃªn Ä‘Ãºng split Ä‘Ã£ dÃ¹ng cho `exp_012/013` vÃ  lÆ°u JSON.
4. **Sá»­a `run_all.py`** Ä‘á»ƒ report gom Ä‘á»§ 5 component (hiá»‡n 3 component bÃ¡o "Benchmark did not run"), vÃ  nÃ¢ng case planner/executor/grounding tá»« 4â€“5 lÃªn â‰¥ 20.
5. **LÃ m rÃµ chÃªnh lá»‡ch memory 0.188 vs 1.000** (fixture vs oracle) â€” chá»n má»™t Ä‘á»‹nh nghÄ©a "Ä‘Ãºng" vÃ  ghi vÃ o `memory_correctness_dataset.jsonl`/`memory_oracle.py`.
6. Náº¿u cáº§n má»™t káº¿t luáº­n vá» cháº¥t lÆ°á»£ng gá»£i Ã½: pháº£i cÃ³ Ã­t nháº¥t má»™t cáº¥u hÃ¬nh cho `recall@10 > 0` (ká»ƒ cáº£ baseline) â€” náº¿u khÃ´ng, má»i so sÃ¡nh agent chá»‰ Ä‘ang so hÃ nh vi, khÃ´ng so relevance.

---

# 20. Bá»©c tranh tá»•ng thá»ƒ

## 20.1. Cáº¥u trÃºc thÆ° má»¥c

```
src/
â”œâ”€â”€ configs/     20 file YAML, 4 thÆ° má»¥c con: path/ (3), data/ (3), eval/ (6), agent/ (8)
â”œâ”€â”€ package/     toÃ n bá»™ logic (import lÃ  `package.*`): config, data, api, tools, memory, agents, inference, evaluation, demo, utils
â”‚                `evaluation/`: ablation/, requests/, layer1_outcome/ â€¦ layer5_deployment/, component/ (+ benchmarks/), diagnostics/, judge/, score_trajectory.py, summarize.py
â”œâ”€â”€ scripts/     7 thÆ° má»¥c theo chá»©c nÄƒng + README.md (cháº¡y `PYTHONPATH=. python scripts/<thÆ° má»¥c>/<tÃªn>.py`)
â”œâ”€â”€ tests/       pytest: agents/ (+ fakes/), config/, data/, demo/, evaluation/ (agent/, component/, ablation/), tools/ (má»—i module má»™t thÆ° má»¥c con) + README.md, logs/
â”œâ”€â”€ docs/        EVALUATION_PROTOCOL.md + evaluation/ (16 file); **khÃ´ng cÃ³** ablation_protocol.md / demo.md / inference_contract.md / decisions.md
â”‚
â”œâ”€â”€ resource/    (sinh ra khi cháº¡y, .gitignore) raw â†’ cleaned â†’ filtered â†’ mapped â†’ splits; corpus/ (SQLite cache), item_knn/ (.npz cache)
â””â”€â”€ experiments/ README.md + exp_NNN/{config.yaml, metrics.json, README.md}; baselines/, agent_eval/ (kÃ¨m exp_009â€“exp_013, component_benchmarks/, memory_utility_analysis/, requests / trajectories / scored .jsonl), candidate_recall/, ranking_eval/, ranking_diagnostics/, data_pipeline/, smoke_tests/, test_logs/, logs/<tag>/
```

`pyproject.toml`, `PACKAGE_SETUP.md`, `.gitattributes` **khÃ´ng cÃ²n trong `src/`** â€” Ä‘Ã£ chuyá»ƒn lÃªn gá»‘c repo trong commit `7c1144a` (29/10).

## 20.2. NguyÃªn táº¯c xuyÃªn suá»‘t

- **Tham sá»‘ náº±m trong YAML, há»£p Ä‘á»“ng (schema) náº±m trong code.** VÃ­ dá»¥ `configs/agent/tools.yaml` chá»©a giá»›i háº¡n runtime (Ä‘á»c bá»Ÿi `tools/_limits.py`), cÃ²n tÃªn cá»™t / filter key lÃ  há»£p Ä‘á»“ng nÃªn náº±m á»Ÿ `tools/_schema.py`.
- **ÄÆ°á»ng dáº«n chá»‰ láº¥y qua `package.config.get_data_paths()`**; cÃ³ test AST (`test_path_hygiene.py`) cáº¥m hard-code `resource/â€¦`, `experiments/â€¦`.
- **Business logic chá»‰ phá»¥ thuá»™c interface `LLMProvider`**, khÃ´ng import SDK cá»§a má»™t provider cá»¥ thá»ƒ.
- **Quy Æ°á»›c Ä‘áº·t tÃªn:** file báº¯t Ä‘áº§u báº±ng `_` lÃ  ná»™i bá»™ cá»§a folder Ä‘Ã³ (`_schema.py`, `_helper.py`, `_dataclass.py`, `_error.py`, `_limits.py`, `_constants.py`); má»—i hÃ m/class cÃ´ng khai náº±m trong file cÃ¹ng tÃªn.
- `load_config` nháº­n tÃªn **cÃ³ thÆ° má»¥c**: `load_config("agent/tools")`, `load_config("path/data_paths")`.

## 20.3. Hai luá»“ng cháº¡y

- **Luá»“ng offline (khÃ´ng LLM):** review thÃ´ â†’ pipeline dá»¯ liá»‡u (má»¥c 4) â†’ fit recommender (má»¥c 7) â†’ Ä‘Ã¡nh giÃ¡ (má»¥c 10).
- **Luá»“ng online (cÃ³ LLM):** cÃ¢u request â†’ `PlanExecutor` (má»¥c 9) â†’ tool (má»¥c 6) â†’ káº¿t quáº£ â†’ `Inference` (má»¥c 9.4) â†’ cÃ¢u tráº£ lá»i. Tool dá»±a trÃªn `ItemCorpus` (má»¥c 5) vÃ  recommender Ä‘Ã£ fit (má»¥c 7).

## 20.4. SÆ¡ Ä‘á»“ runtime

```mermaid
flowchart TB
    USER["User"]

    subgraph AGENT_LAYER["Agent layer â€” package/agents, package/api"]
        LLM["LLMProvider<br/>(OpenAICompatibleProvider)"]
        EXEC["PlanExecutor<br/>LLM viáº¿t plan JSON â†’ cháº¡y tá»«ng step"]
        T1["Type1Agent<br/>plan cá»‘ Ä‘á»‹nh, khÃ´ng LLM"]
    end

    subgraph INFER_LAYER["Inference â€” package/inference"]
        ANS["compose_answer<br/>item agent Ä‘Ã£ chá»n â†’ cÃ¢u tráº£ lá»i<br/>(LLM + kiá»ƒm grounding, hoáº·c template)"]
    end

    subgraph TOOL_LAYER["Tool layer â€” package/tools, package/memory"]
        SEARCH["SemanticSearchTool<br/>text â†’ candidates (BM25)"]
        CF["ItemCFTool<br/>seed items â†’ similar items"]
        RECO["RecoModelTool<br/>candidates â†’ ranked"]
        QUERY["QueryTool<br/>item_ids â†’ metadata"]
        MEMORY["MemoryTool<br/>user_id â†’ profile tá»« history"]
        SQL["SQLTool<br/>filter â†’ candidates<br/>(chÆ°a cáº¥p cho planner)"]
    end

    subgraph KNOWLEDGE["Item knowledge"]
        CORPUS["ItemCorpus<br/>SQLite in-memory, read-only<br/>items Â· item_categories Â· items_fts"]
    end

    subgraph MODELS["Recommendation models â€” tools/recommenders, tools/score"]
        POP["PopularityRecommender"]
        KNN["ItemKNNRecommender"]
        SCORER["CandidateScorer (Protocol)<br/>â”” BaselineScorer"]
    end

    INTERACT["Userâ€“item interactions<br/>(splits/train.parquet)"]

    USER --> LLM --> EXEC
    EXEC --> SEARCH & CF & RECO & QUERY & MEMORY

    SEARCH --> CORPUS
    SEARCH -.->|"mÆ°á»£n bá»™ compile filter"| SQL
    SQL -.-> CORPUS
    QUERY --> CORPUS
    MEMORY --> CORPUS
    MEMORY --> INTERACT

    INTERACT --> POP
    INTERACT --> KNN
    KNN -->|"similarity matrix"| CF
    POP --> SCORER
    KNN --> SCORER
    SCORER --> RECO

    T1 --> CF
    T1 --> RECO
    T1 --> QUERY

    EXEC --> ANS
    T1 --> ANS
    ANS -.->|"mode = llm"| LLM
    ANS --> USER
```

~~Ba Ä‘iá»ƒm dá»… nháº§m:~~

1. ~~ðŸ”´**Planner khÃ´ng cÃ³ `SQLTool`.** `agents/toolkit/build_tools.py` (`build_tools()` â†’ `AgentTools`; `for_planner()` = 4 tool: ItemCF, RecoModel, Query, SemanticSearch; `for_planner_memory()` = thÃªm `MemoryTool`) â€” dÃ¹ng bá»Ÿi `run_agent_eval.py` vÃ  `smoke_real_llm.py` â€” khÃ´ng Ä‘Æ°a `SQLTool` vÃ o. `SQLTool` váº«n Ä‘Æ°á»£c code, test vÃ  cháº¡y trong `scripts/tools/run_tools.py`, vÃ  `SemanticSearchTool` dÃ¹ng chung hÃ m `compile_filters` (`sql_query/compile_filters.py`) vá»›i nÃ³. Náº¿u muá»‘n planner dÃ¹ng filter thuáº§n cáº¥u trÃºc (khÃ´ng text) thÃ¬ pháº£i thÃªm vÃ o `agents/toolkit/build_tools.py` **vÃ ** cáº­p nháº­t `agents/planner/_prompt.py`. (`scripts/demo/demo_full_agent.py` cÃ²n báº£n `build_tools()` riÃªng, cÅ©, 5 tool, khÃ´ng qua `AgentTools` â€” Ä‘á»«ng nháº§m vá»›i báº£n tháº­t.)~~
2. ~~`PlanExecutor.run()` **tráº£ vá» danh sÃ¡ch káº¿t quáº£ tool**; cÃ¢u tráº£ lá»i cuá»‘i do `package/inference` (má»¥c 9.4) sinh sau Ä‘Ã³ vÃ  **chá»‰ trÃ¬nh bÃ y** cÃ¡c item agent Ä‘Ã£ chá»n (khÃ´ng chá»n láº¡i, khÃ´ng Ä‘á»•i thá»© tá»±). ChÆ°a cÃ³ vÃ²ng láº·p "LLM Ä‘á»c káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿" (má»¥c 15). `demo` chÆ°a gá»i `inference` (má»¥c 13.1).~~
3. ~~ðŸ”´`MemoryTool` Ä‘á»c **cáº£** `interactions` (DataFrame) vÃ  `ItemCorpus`.~~

## 20.5. Chiá»u phá»¥ thuá»™c giá»¯a cÃ¡c package

HÆ°á»›ng **Ä‘Æ°á»£c phÃ©p** (test `test_dependency_direction.py` Ã©p cÃ¡c cáº·p **bá»‹ cáº¥m** á»Ÿ cá»™t pháº£i):

```
tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º data, config                              tools âœ— agents
memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º tools, data.leakage
api â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º config
agents â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º tools, memory, api                        agents âœ— inference, demo, evaluation
inference â”€â”€â”€â”€â”€â”€â–º agents, api                               inference âœ— demo, evaluation
evaluation â”€â”€â”€â”€â”€â–º agents, inference, tools, data            evaluation âœ— demo
demo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º agents, inference, tools, memory, data    demo âœ— evaluation
má»i nÆ¡i â”€â”€â”€â”€â”€â”€â”€â”€â–º config
```

`config` vÃ  `data` khÃ´ng import `tools`/`agents` (ngoáº¡i lá»‡: `tools/corpus` dÃ¹ng `data.namespaced_item_id`; `DataPaths.split_path` import `data.split` lazily). VÃ¬ `agents` khÃ´ng Ä‘Æ°á»£c import `evaluation`, `extract_recommendations` vÃ  `TEMPLATES` náº±m trong `agents/` (`agents/results/`, `agents/_schema.py`) Ä‘á»ƒ `inference`, `evaluation` vÃ  `demo` cÃ¹ng dÃ¹ng. `evaluation/agent/_schema.py` váº«n **láº·p láº¡i** `ANSWER_STATUSES` cá»§a `inference` (cÃ³ test giá»¯ hai báº£n báº±ng nhau); lÃ½ do ban Ä‘áº§u lÃ  trÃ¡nh vÃ²ng import, nay `evaluation` Ä‘Æ°á»£c phÃ©p import `inference` nÃªn báº£n láº·p cÃ³ thá»ƒ bá». `package/__init__.py` **rá»—ng**; `tools/__init__.py` váº«n import eager `evaluation`, `recommenders`â€¦ (má»¥c 16.2). `tests/test_package_import.py` giá»¯ cho import nháº¹.

## 20.6. Quy Æ°á»›c cáº¥u trÃºc (Ä‘Æ°á»£c test Ã©p)

Ba file test trong `tests/config/` biáº¿n quy Æ°á»›c thÃ nh luáº­t (`scripts/` Ä‘Æ°á»£c kiá»ƒm cÃ¹ng `package/`; `tests/` Ä‘Æ°á»£c miá»…n vÃ¬ lÃ  white-box):

- **Má»™t file, má»™t symbol** (`test_package_layout.py`): module cÃ´ng khai (khÃ´ng báº¯t Ä‘áº§u báº±ng `_`, khÃ´ng pháº£i `__init__` / `__main__`) cÃ³ **Ä‘Ãºng má»™t** class / hÃ m cÃ´ng khai á»Ÿ cáº¥p module, vÃ  tÃªn Ä‘Ã³ trÃ¹ng tÃªn file (bá» dáº¥u `_`, khÃ´ng phÃ¢n biá»‡t hoa thÆ°á»ng): `ItemCFTool` â†” `item_cf_tool.py`. VÃ¬ váº­y `candidate_results` tÃ¡ch khá»i `candidate_ids.py`, má»—i recommender má»™t file, má»—i hÃ m demo má»™t file.
- **TÃªn cÃ´ng khai duy nháº¥t toÃ n package** (cÃ¹ng file test): vÃ¬ tháº¿ hai lá»›p ma tráº­n Ä‘á»•i tÃªn `PopularityMatrixRecommender` / `ItemKNNMatrixRecommender`, cÃ²n tÃªn cÅ© `PopularityRecommender` / `ItemKNNRecommender` Ä‘Æ°á»£c giá»¯ báº±ng **lá»›p con rá»—ng** cá»§a lá»›p DataFrame-based.
- **RiÃªng tÆ° theo thÆ° má»¥c** (cÃ¹ng file test): module `_xxx` chá»‰ Ä‘Æ°á»£c import trong chÃ­nh thÆ° má»¥c chá»©a nÃ³; ngoÃ i thÆ° má»¥c pháº£i Ä‘i qua `__init__.py` hoáº·c má»™t module cÃ´ng khai. VÃ¬ tháº¿ `compile_filters.py` (dÃ¹ng chung cho `retrieval/`) lÃ  module cÃ´ng khai thay vÃ¬ `_helper.py`.
- **HÆ°á»›ng phá»¥ thuá»™c** (`test_dependency_direction.py`): báº£ng á»Ÿ má»¥c 2.5; danh sÃ¡ch ngoáº¡i lá»‡ hiá»‡n rá»—ng.
- **Import pháº£i trá» tá»›i module cÃ³ tháº­t** (`test_import_resolution.py`): ra Ä‘á»i tá»« lá»—i `compare_experiments.py` import `package.agents.evaluation.ablation` (khÃ´ng tá»“n táº¡i).

Há»‡ quáº£ khi Ä‘á»c code: hÃ m / class `X` náº±m á»Ÿ file cÃ¹ng tÃªn; `_dataclass.py`, `_helper.py`, `_schema.py`, `_limits.py`, `_error.py`, `_prompt.py` lÃ  ná»™i bá»™ cá»§a thÆ° má»¥c chá»©a chÃºng; `__init__.py` lÃ  máº·t tiá»n cÃ´ng khai cá»§a thÆ° má»¥c.

## 20.7. Báº£ng Ä‘á»•i tÃªn (trÆ°á»›c â†’ sau refactor 17/10)

| TrÆ°á»›c | Sau |
|---|---|
| `config/loader.py` | `config/load_config.py` |
| `utils/console.py` | `utils/ensure_utf8_stdout.py` |
| `tools/corpus/corpus.py` | `tools/corpus/item_corpus.py` |
| `tools/sql_query/_helper.py` | `tools/sql_query/compile_filters.py` (cÃ´ng khai) |
| `api/{base,factory,openai_compatible}.py` | `api/{llm_provider,build_llm_provider,openai_compatible_provider}.py` |
| `tools/base/candidate_ids.py` (kÃ¨m `candidate_results`) | `candidate_ids.py` + `candidate_results.py` |
| `popularity.py`, `item_knn.py` (matrix) | `popularity_matrix_recommender.py`, `item_knn_matrix_recommender.py` |
| `baseline_{popularity,item_knn}.py` | `baseline_*_recommender.py` + lá»›p con rá»—ng giá»¯ tÃªn cÅ© (`popularity_recommender.py`, `item_knn_recommender.py`) |
| `tools/evaluation/{evaluator,recommendation_metrics,segment_users}.py` | `evaluate_recommender.py`, `evaluate_ranking.py`, `segment_users_by_history.py` |
| `agents/{plan_executor,_prompt,_schema,_helper}.py` | `agents/planner/â€¦` |
| `agents/evaluation/â€¦`, `agents/ablation/â€¦` | `package/evaluation/agent/â€¦` â†’ nay lÃ  `evaluation/{requests/,score_trajectory.py,summarize.py}`; `evaluation/ablation/â€¦` |
| `inference/_helper.py` | `inference/grounding/*`, `inference/cut.py`, `inference/empty_usage.py` |
| `demo/_view_model.py`, `_formatter.py`, `_adapter.py`, `_samples.py` | `demo/view/*`, `demo/adapter/*`, `demo/samples/*` |
| `configs/agent/judge.yaml` | `configs/eval/judge.yaml` |

CÃ¡c Ä‘á»•i tÃªn cÃ²n láº¡i theo cÃ¹ng quy Æ°á»›c á»Ÿ Â§2.6 (má»—i file má»™t symbol cÃ´ng khai, tÃªn trÃ¹ng tÃªn file; `_xxx.py` lÃ  ná»™i bá»™ thÆ° má»¥c): `metrics/*.py` â†’ `*_at_k.py`, `bpr_mf.py`/`random_rec.py`/`fallback.py`/`factory.py` â†’ `*_recommender.py` + `build_model.py`.

---

# 21. Config

**Vai trÃ²:** má»i giÃ¡ trá»‹ chá»‰nh Ä‘Æ°á»£c náº±m trong `configs/*.yaml`; `package/config` Ä‘á»c YAML (cÃ³ thay biáº¿n mÃ´i trÆ°á»ng) vÃ  lÃ  **nguá»“n duy nháº¥t** cho Ä‘Æ°á»ng dáº«n.

## 21.1. `configs/`

|File|Giá»¯ gÃ¬|Ai Ä‘á»c|
|---|---|---|
|`path/data_paths.yaml`|Má»i thÆ° má»¥c: `raw_dir`, `cleaned_dir`, `filtered_dir`, `mapped_dir`, `splits_dir`, `item_knn_dir` (cache `.npz`), `corpus_dir` (cache `.sqlite`), `log_dir` (= `experiments/logs`, trÆ°á»›c lÃ  `resource/logs`), `experiments_dir`. ChÃº thÃ­ch Ä‘áº§u file liá»‡t kÃª `experiments/{logs,test_logs,baselines,agent_eval,data_pipeline,smoke_tests}/` â€” váº«n **chÆ°a khá»›p** code (`candidate_recall`, `ranking_eval`, `ranking_diagnostics` khÃ´ng Ä‘Æ°á»£c nháº¯c; má»¥c 16.2)|`get_data_paths()` â†’ má»i script|
|`path/run_tag.yaml`|`tag: multi_domain` â€” tÃªn má»™t láº§n cháº¡y; stage 2/3 ghi vÃ o `<dir>/<tag>/`|`get_data_paths()`|
|`path/domains.yaml`|3 domain báº­t (`Video_Games` primary; `Toys_and_Games`, `Electronics` secondary)|`get_domains()`. TrÆ°á»ng `role` **khÃ´ng cÃ³ code nÃ o Ä‘á»c**|
|`data/cleaning.yaml`|`chunk_size: 250000`|stage 1|
|`data/filtering.yaml`|k-core `min_user_interactions=5`, `min_item_interactions=5`|stage 2|
|`data/split.yaml`|0.8 / 0.1 / 0.1 (luÃ´n temporal)|stage 3|
|`eval/baselines.yaml`|`seed`, `models`, `popularity_fallback`, `item_knn.{k,block_elements}`, `bpr_mf.{â€¦}`|`run_baselines`, `tune_baselines`, `candidate_recall`, `run_agent_eval` (láº¥y `item_knn.k`, `seed`)|
|`eval/tuning.yaml`|`selection_metric: ndcg@10`, lÆ°á»›i tham sá»‘ cho `item_knn`, `bpr_mf`|`tune_baselines`|
|`eval/recommendation_metrics.yaml`|`k_values: [5, 10, 20]`|`run_baselines`, `tune_baselines`|
|`eval/segment_thresholds.yaml`|`sparse_max_history: 4` (cold = 0, sparse 1â€“4, warm â‰¥ 5)|evaluator, `candidate_recall`, `run_agent_eval`|
|`eval/candidate_recall.yaml`|`budgets [50,100,200]`, `per_segment 1000`, `seed_items 10`, `query_items 3`, `min_metadata_coverage 0.5`, `experiments_subdir candidate_recall`|`candidate_recall`|
|`agent/tools.yaml`|`max_candidates 1000`, `max_query_rows 100`, `sql_time_budget_seconds 5`, `max_output_summary_chars 500`, `defaults.{sql_limit 100, item_cf_top_k 20, query_max_rows 20, memory_top_n_categories 3, memory_recent_items 5}`, `semantic_search.{default_limit 50, max_query_tokens 20}`|`tools/_limits.py` (**validate lÃºc load, Ä‘á»c má»™t láº§n lÃºc import**)|
|`agent/agent.yaml`|`max_steps 8`, `plan_retries 1`, `reflect_rounds 1` (0 = táº¯t plan-reflect), `max_tokens 2048`, `temperature 0.0`, `type1.{candidate_multiplier 5, min_candidates 50}`, `reflect_error_chars 300`|`agents/_limits.py` (validate)|
|`agent/llm.yaml`|`provider`, `model` (ghi tháº³ng), `base_url: ${LLM_BASE_URL:-}`, `api_key: ${LLM_API_KEY:-}`, `timeout_seconds`|`build_llm_provider`|
|`agent/agent_eval.yaml`|`agents [baseline,type1,planner,planner_memory]`, `k 10`, `per_segment 20`, `n_ambiguous 6`, `language vi`, `price_slack 1.25`, `price_round_to 5`, `min_metadata_coverage 0.5`, `trajectory_error_chars 300`, `max_consecutive_llm_errors 5`, `experiments_subdir agent_eval`, `trajectory_file`|`run_agent_eval` (vÃ  `ranking_eval` cho `min_metadata_coverage`)|
|`agent/inference.yaml`|`mode` (`llm` \| `template`), `max_items 10`, `max_tokens 2048`, `temperature 0.0`, `llm_retries 1`, `check_numbers true`, `price_tolerance 0.5` (USD), `title_chars 120`, `reason_chars 300`|`inference/_limits.py` (validate)|
|`agent/demo.yaml`|`max_error_length 300`, `max_items_display 10`, `sample_users_per_segment 3`, `default_language vi`, `max_recent_items_display 5`, `max_turn_history_rows 50`|`demo/_limits.py` (validate)|
|`agent/ablation.yaml`|`bootstrap_resamples 10000`, `confidence 0.95`, `min_n_warn 20`, `seed 42`, `metrics` (11 má»¥c, gá»“m `answer_fallback`, `inference_latency_seconds`, `inference_completion_tokens`), `groups` (**nay khai bÃ¡o tháº­t**: `reflect_0: [exp_012]`, `reflect_1: [exp_013]`, `infer_template: [exp_011]`), `contrasts` (6 contrast), `output_subdir agent_eval/ablation`|`evaluation/ablation/_limits.py`, `scripts/experiments/compare_experiments.py`|
|`agent/demo_profiles.yaml`|`demo_profiles.pinned` (danh sÃ¡ch profile ghim cho demo UI; hiá»‡n `[]`)|`demo/_profile_builder.py` (`build_profiles`, `load_config("agent/demo_profiles")`)|
|`eval/judge.yaml`|`api_key: ${OPENROUTER_API_KEY:-}`, `model jev-latest`, `base_url https://api.typesafe.ai`, `timeout_seconds 30`, `enable_long_context false`, `evaluation.faithfulness.{claim_extraction rule, support_threshold 0.7}`, `evaluation.communication.criteria.{relevance, clarity, language, honesty_about_gaps}` + rubric 5 má»©c|`evaluation/judge/jev_client.py`, `evaluation/jev_product_evaluator.py` (Ä‘á»c tháº³ng file báº±ng `yaml.safe_load`, máº·c Ä‘á»‹nh `configs/eval/judge.yaml`, **khÃ´ng** qua `load_config`)|

`tools.yaml`, `agent.yaml`, `inference.yaml`, `demo.yaml`, `ablation.yaml` Ä‘Æ°á»£c validate (trong `_limits.py` cá»§a tá»«ng package); cÃ¡c file cÃ²n láº¡i script Ä‘á»c tháº³ng (`eval/judge.yaml` Ä‘á»c báº±ng `yaml.safe_load`). **Biáº¿n mÃ´i trÆ°á»ng:** `LLM_API_KEY`, `LLM_BASE_URL` (cáº£ hai máº·c Ä‘á»‹nh rá»—ng â†’ `build_llm_provider` bÃ¡o thiáº¿u `base_url`), `OPENROUTER_API_KEY` (cho `eval/judge.yaml`). `scripts/README.md` **khÃ´ng nháº¯c** biáº¿n mÃ´i trÆ°á»ng nÃ o. Tá»« 29/10 **khÃ´ng cÃ²n comment hay docstring nÃ o trá» tá»›i file `docs/*` khÃ´ng tá»“n táº¡i** (Ä‘Ã£ bá» tham chiáº¿u `decisions.md` á»Ÿ `llm.yaml`/`domains.yaml` vÃ  `inference_contract.md` á»Ÿ `inference.yaml` + `classify_outcome.py`; má»¥c 16).

## 21.2. `package/config/`

|File|Viá»‡c|
|---|---|
|`__init__.py`|export `load_config`, `DataPaths`, `get_data_paths`, `get_domains`|
|`load_config.py`|`load_config("<thÆ°_má»¥c>/<tÃªn>")` Ä‘á»c `configs/<thÆ°_má»¥c>/<tÃªn>.yaml`, thay `${VAR}` / `${VAR:-default}` báº±ng biáº¿n mÃ´i trÆ°á»ng (káº¿t quáº£ luÃ´n lÃ  **chuá»—i**)|
|`_helper.py`|`_interpolate_env`: ngá»¯ nghÄ©a shell `:-` (biáº¿n chÆ°a Ä‘áº·t **hoáº·c rá»—ng** thÃ¬ dÃ¹ng default); `${VAR}` khÃ´ng default mÃ  thiáº¿u â†’ `ConfigError`|
|`get_data_paths.py`|`get_data_paths(tag)` â†’ `DataPaths`. **KhÃ´ng Ä‘á»c biáº¿n mÃ´i trÆ°á»ng `TAG`** (script Python dÃ¹ng `--tag`)|
|`_dataclass.py`|`DataPaths` (frozen) + `corpus_path`, `item_knn_path` (cache theo `tag` vÃ  `eval_on`) vÃ  cÃ¡c hÃ m `review_path` (**nay thá»­ `<domain>/<domain>.jsonl[.gz]` trÆ°á»›c**, rá»“i file pháº³ng á»Ÿ `raw_dir`), `meta_path`, `cleaned_path`, `filtered_path`, `split_path`; tÃªn file `interactions.parquet`; `log_dir` = `experiments/logs/<tag>`|
|`get_domains.py`|danh sÃ¡ch tÃªn domain tá»« `path/domains.yaml`|
|`__main__.py`|CLI Ä‘á»ƒ shell Ä‘á»c config/Ä‘Æ°á»ng dáº«n (khÃ´ng script nÃ o trong repo cÃ²n gá»i, vÃ¬ `scripts/sh/` Ä‘Ã£ bá»): `python -m package.config path/domains.domains` hoáº·c `path:raw_dir`, `path:cleaned_path:Video_Games`. CÃ³ báº£ng `folder_map` hard-code cho tÃªn cÅ© khÃ´ng cÃ³ thÆ° má»¥c (`domains.domains` váº«n cháº¡y).|
|`_constants.py`|`PROJECT_ROOT`, `CONFIG_DIR`, regex `${VAR}`|
|`_error.py`|`ConfigError`|

---

# 22. Data pipeline

**Vai trÃ²:** biáº¿n review thÃ´ Amazon thÃ nh 3 split theo thá»i gian Ä‘Ã£ map sang chá»‰ sá»‘ nguyÃªn, Ä‘á»§ Ä‘á»ƒ fit mÃ´ hÃ¬nh, Ä‘á»“ng thá»i cÃ³ kiá»ƒm tra leakage.

```mermaid
flowchart LR
    RAW["resource/raw<br/>reviews + meta (.jsonl.gz)"]
    S1["stage 1<br/>clean tá»«ng domain"]
    S2["stage 2<br/>gá»™p domain + k-core"]
    S3["stage 3<br/>ID mapping + temporal split<br/>+ leakage check"]
    OUT1["cleaned/&lt;Domain&gt;/interactions.parquet"]
    OUT2["filtered/&lt;tag&gt;/interactions.parquet"]
    OUT3["mapped/&lt;tag&gt;/{user2id,item2id}.json<br/>splits/&lt;tag&gt;/{train,validation,test}.parquet"]
    META["meta_&lt;Domain&gt;.jsonl.gz"]
    CORPUS["ItemCorpus"]
    MODELS["Recommenders"]

    RAW --> S1 --> OUT1 --> S2 --> OUT2 --> S3 --> OUT3
    RAW --> META --> CORPUS
    OUT3 --> MODELS
```

## 22.1. Ba stage (scripts)

|Stage|Script|Viá»‡c chÃ­nh|
|---|---|---|
|1|`data_pipeline/stage1_clean_domain.py`|Äá»c review theo chunk (`chunk_size`), `clean_interactions` tá»«ng chunk, **dedupe xuyÃªn chunk báº±ng báº£ng SQLite táº¡m** (khoÃ¡ `(user_id, parent_asin, timestamp)`), ghi parquet theo chunk. Output Ä‘á»c ra theo thá»© tá»± khoÃ¡ chÃ­nh (Ä‘Ã£ sort theo `user_id`). KhÃ´ng cÃ³ `--force` thÃ¬ bÃ¡o lá»—i náº¿u output Ä‘Ã£ tá»“n táº¡i|
|2|`data_pipeline/stage2_merge_filter.py`|`tag_domain` tá»«ng domain â†’ `merge_domains` â†’ `clean_interactions` láº§n ná»¯a â†’ `k_core_filter` **trÃªn dá»¯ liá»‡u Ä‘Ã£ gá»™p** (Ä‘áº¿m xuyÃªn domain) â†’ `optimize_interaction_dtypes` â†’ parquet. `--cold-start-report` so sá»‘ user warm khi lá»c riÃªng tá»«ng domain vá»›i khi gá»™p|
|3|`data_pipeline/stage3_map_split.py`|`build_id_mappings` + `apply_id_mapping` trÃªn **toÃ n bá»™** dá»¯ liá»‡u (ká»ƒ cáº£ val/test) â†’ `compute_temporal_cutoffs` + `temporal_split` â†’ 3 leakage check â†’ `save_splits`|
|EDA|`eda_diagnostic/run_eda.py`|EDA interaction trÃªn review thÃ´, streaming. Chá»‰ in thá»‘ng kÃª interaction; **`compute_metadata_stats` khÃ´ng Ä‘Æ°á»£c script nÃ o gá»i** (chá»‰ cÃ³ test)|
|Cháº©n Ä‘oÃ¡n|`eda_diagnostic/diagnose_splits.py`|`--tag <tag> [--out file.json]`: Ä‘á»c splits + mapping Ä‘Ã£ sinh, in bÃ¡o cÃ¡o vÃ  (tuá»³ chá»n) ghi JSON (`SplitDiagnosis`): sá»‘ dÃ²ng / user / item vÃ  khoáº£ng thá»i gian tá»«ng split; tá»‰ lá»‡ domain; **% item cá»§a val/test Ä‘Ã£ cÃ³ trong train** (theo item vÃ  theo dÃ²ng); **% user val/test cÃ³ lá»‹ch sá»­ train** (+ min / median / p90 Ä‘á»™ dÃ i lá»‹ch sá»­); **% cáº·p (user, item) láº·p** Ä‘Ã£ náº±m trong history; **% dÃ²ng `reachable`** (item cÃ³ trong train **vÃ ** cáº·p chÆ°a náº±m trong history); % user Ä‘a-domain. Má»¥c Ä‘Ã­ch: tráº£ lá»i "vÃ¬ sao recall@10 â‰ˆ 0" (Â§19.6, Â§21.7). **ChÆ°a tháº¥y káº¿t quáº£ cháº¡y trÃªn dá»¯ liá»‡u tháº­t trong zip**|

**Item id** dáº¡ng `{domain}::{parent_asin}`. Sau `tag_domain`, cá»™t váº«n tÃªn `parent_asin` nhÆ°ng giÃ¡ trá»‹ Ä‘Ã£ namespace; `original_item_id` giá»¯ asin gá»‘c. **`user_id` khÃ´ng namespace** (id toÃ n cá»¥c cá»§a Amazon â†’ giÃºp cross-domain). Domain lÆ°u thÃ nh cá»™t vÃ  tra láº¡i, **khÃ´ng parse tá»« id**. **Split** luÃ´n lÃ  temporal toÃ n cá»¥c (khÃ´ng random, khÃ´ng leave-one-out).

## 22.2. `package/data/` â€” tá»«ng file

| Folder     | File                                     | Viá»‡c                                                                                                                                                                                                                                   |
| ---------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (gá»‘c)      | `__init__.py`                            | export cÃ¡c subpackage vÃ  `domain.*`                                                                                                                                                                                                    |
|            | `_schema.py`                             | `REQUIRED_COLUMNS` (user_id, parent_asin, rating, timestamp), `OPTIONAL_COLUMNS`, `ITEM_ID_SEPARATOR = "::"`                                                                                                                           |
| `clean/`   | `clean_interactions.py`                  | bá» dÃ²ng thiáº¿u field báº¯t buá»™c + dedupe `(user, item, timestamp)`; tráº£ `(df, report)` cÃ³ sá»‘ lÆ°á»£ng loáº¡i á»Ÿ má»—i bÆ°á»›c                                                                                                                        |
|            | `iter_reviews_dataframes.py`             | Ä‘á»c `.jsonl.gz` theo chunk (`pd.read_json(chunksize=â€¦)`)                                                                                                                                                                               |
|            | `load_reviews_dataframe.py`              | Ä‘á»c cáº£ file vÃ o má»™t DataFrame (cho file nhá»/test)                                                                                                                                                                                      |
| `domain/`  | `tag_domain.py`                          | thÃªm cá»™t `domain`, `original_item_id`; ghi Ä‘Ã¨ `parent_asin` thÃ nh id cÃ³ namespace                                                                                                                                                      |
|            | `namespaced_item_id.py`                  | `"{domain}::{asin}"`                                                                                                                                                                                                                   |
|            | `merge_domains.py`                       | `pd.concat` cÃ¡c DataFrame Ä‘Ã£ tag (bÃ¡o lá»—i náº¿u chÆ°a tag)                                                                                                                                                                                |
|            | `domain_breakdown.py`                    | thá»‘ng kÃª interaction/user/item theo domain                                                                                                                                                                                             |
| `filter/`  | `k_core_filter.py`                       | láº·p tá»‘i Ä‘a 20 vÃ²ng loáº¡i user/item dÆ°á»›i ngÆ°á»¡ng (**Ä‘áº¿m theo sá»‘ dÃ²ng**); háº¿t 20 vÃ²ng chÆ°a há»™i tá»¥ thÃ¬ **cáº£nh bÃ¡o** (`warnings`) nhÆ°ng váº«n tráº£ káº¿t quáº£ chÆ°a há»™i tá»¥                                                                          |
| `loader/`  | `iter_jsonl_gz.py`                       | generator Ä‘á»c `.jsonl.gz` theo dÃ²ng                                                                                                                                                                                                    |
|            | `load_item_metadata.py`                  | Ä‘á»c `meta_<Domain>.jsonl.gz`, chá»‰ giá»¯ item `keep(domain, asin)`; cá»™t theo `META_FIELDS` + `domain`                                                                                                                                     |
|            | `optimize_interaction_dtypes.py`         | `user_id/parent_asin/domain/original_item_id` â†’ `category`, `rating` â†’ float32 (giá»¯ `timestamp` int64)                                                                                                                                 |
|            | `estimate_memory_usage_mb.py`            | Ä‘o RAM (`deep=True`) Ä‘á»ƒ log                                                                                                                                                                                                            |
|            | `_schema.py`                             | `META_FIELDS`                                                                                                                                                                                                                          |
| `mapping/` | `build_id_mappings.py`                   | gÃ¡n index theo thá»© tá»± xuáº¥t hiá»‡n Ä‘áº§u tiÃªn (khÃ´ng dá»±a timestamp)                                                                                                                                                                         |
|            | `apply_id_mapping.py`                    | thÃªm `user_idx`, `item_idx`; id láº¡ â†’ `ValueError` (khÃ´ng Ã¢m tháº§m bá»)                                                                                                                                                                   |
|            | `save_mappings.py` / `load_mappings.py`  | ghi/Ä‘á»c `user2id.json`, `item2id.json`                                                                                                                                                                                                 |
|            | `_schema.py`                             | tÃªn 2 file trÃªn                                                                                                                                                                                                                        |
| `split/`   | `compute_temporal_cutoffs.py`            | 2 má»‘c timestamp theo phÃ¢n vá»‹ toÃ n cá»¥c                                                                                                                                                                                                  |
|            | `temporal_split.py`                      | cáº¯t thÃ nh train / validation / test theo 2 má»‘c                                                                                                                                                                                         |
|            | `save_splits.py` / `load_splits.py`      | ghi/Ä‘á»c 3 parquet; `load_splits` chá»‰ láº¥y cá»™t cÃ³ trong file; `infer_matrix_shape` (Ä‘á»‹nh nghÄ©a á»Ÿ `infer_matrix_shape.py`) Ä‘Æ°á»£c `load_splits.py` import láº¡i vÃ  re-export                                                                  |
|            | `split_path.py`                          | nÆ¡i duy nháº¥t quyáº¿t Ä‘á»‹nh `<splits_dir>/<name>.parquet`                                                                                                                                                                                  |
|            | `infer_matrix_shape.py`                  | `infer_matrix_shape(*frames)` â€” kÃ­ch thÆ°á»›c ma tráº­n suy tá»« chá»‰ sá»‘ lá»›n nháº¥t. Sau refactor Ä‘Ã£ háº¿t trÃ¹ng (khÃ´ng cÃ²n báº£n thá»© hai trong `load_splits.py`); `load_splits.py` import láº¡i nÃªn pyflakes bÃ¡o import thá»«a                          |
|            | `_schema.py`                             | `SPLIT_NAMES = (train, validation, test)`                                                                                                                                                                                              |
| `leakage/` | `check_split_temporal_order.py`          | `max(train) â‰¤ min(val)` vÃ  `max(val) â‰¤ min(test)`                                                                                                                                                                                      |
|            | `check_no_duplicate_across_splits.py`    | khÃ´ng dÃ²ng nÃ o xuáº¥t hiá»‡n á»Ÿ 2 split                                                                                                                                                                                                     |
|            | `check_profile_snapshot.py`              | khÃ´ng interaction nÃ o cÃ³ `timestamp > as_of` (dÃ¹ng cho `MemoryTool`, `run_agent_eval`, stage 3)                                                                                                                                        |
|            | `_error.py`                              | `LeakageError`                                                                                                                                                                                                                         |
| `eda/`     | `compute_interaction_stats.py`           | thá»‘ng kÃª trÃªn DataFrame (chá»‰ dÃ¹ng trong test)                                                                                                                                                                                          |
|            | `compute_interaction_stats_streaming.py` | thá»‘ng kÃª streaming trÃªn review thÃ´ (dÃ¹ng bá»Ÿi `run_eda`)                                                                                                                                                                                |
|            | `print_streaming_stats_report.py`        | in bÃ¡o cÃ¡o                                                                                                                                                                                                                             |
|            | `diagnose_splits.py`                     | `diagnose_splits(...)` â†’ `SplitDiagnosis` (cÃ¡c chá»‰ sá»‘ á»Ÿ má»¥c 4.1: item/user Ä‘Ã£ tháº¥y trong train, cáº·p láº·p, `reachable`, Ä‘á»™ dÃ i history, tá»‰ lá»‡ domain, % user Ä‘a-domain); chá»‰ gá»i bá»Ÿi `scripts/eda_diagnostic/diagnose_splits.py` vÃ  test |
|            | `compute_metadata_stats.py`              | thá»‘ng kÃª completeness metadata (chá»‰ dÃ¹ng trong test)                                                                                                                                                                                   |
|            | `segment_users.py`                       | phÃ¢n nhÃ³m kiá»ƒu cÅ© (`new`/`sparse_history`/`warm`, ngÆ°á»¡ng 3, cá»™t `evolving_interest` luÃ´n `False`); **chá»‰ dÃ¹ng trong test**. PhÃ¢n Ä‘oáº¡n tháº­t lÃ  `tools/evaluation/_helper.assign_segments` (`cold`/`sparse`/`warm`, `sparse_max=4`)      |
|            | `_dataclass.py`                          | `InteractionStats`, `StreamingInteractionStats`, `MetadataStats`, `SplitDiagnosis` (nay thÃªm `protocol`, `fit_diagnostics`, `domain_diagnostics`; cÃ¡c `*_reachable_pct` Ä‘Æ°á»£c chÃº thÃ­ch láº¡i lÃ  **unique-pair catalog eligibility**, khÃ´ng pháº£i tráº§n macro Recall@K)                                                                                                                                                     |

LÆ°u Ã½ Ä‘á»c code: nhiá»u file trong `clean/`, `domain/`, `mapping/`, `leakage/`, `filter/k_core_filter.py`, `eda/segment_users.py` **dÃ¹ng chung má»™t docstring Ä‘áº§u module copy tá»« file khÃ¡c** â€” Ä‘á»«ng tin docstring Ä‘áº§u file, hÃ£y tin tÃªn hÃ m.

---

# 23. Item corpus â€” kiáº¿n thá»©c vá» item

**Vai trÃ²:** kho item chá»‰ Ä‘á»c mÃ  `SQLTool`, `SemanticSearchTool`, `QueryTool`, `MemoryTool`, `ItemCFTool`, `RecoModelTool` cÃ¹ng dÃ¹ng (hai tool cuá»‘i chá»‰ Ä‘á»ƒ gáº¯n `domain`).

|File|Viá»‡c|
|---|---|
|`tools/corpus/item_corpus.py`|`ItemCorpus`: dá»±ng tá»« metadata DataFrame (`from_dataframe`, `from_parquet`) thÃ nh SQLite in-memory; khoÃ¡ láº¡i báº±ng `PRAGMA query_only` + authorizer chá»‰ cho `SELECT` (`PRAGMA`, ká»ƒ cáº£ `pragma_table_info()`, bá»‹ cháº·n). API: `select(sql, params, max_rows)` (tráº£ `(rows, truncated)`), `count`, `domains`, `item_domains`; **cáº£ `select` vÃ  `count` cÃ³ timeout `sql_time_budget_seconds`** (nÃ©m `SQLTimeOutError`). `from_dataframe` tá»« chá»‘i `domain=` mÃ¢u thuáº«n vá»›i cá»™t `domain` vÃ  `original_item_id` khÃ´ng khá»›p `parent_asin` (`ValueError`)|
|`tools/corpus/_helper.py`|`read_only_authorizer` (Ä‘Æ°á»£c `item_corpus.py` dÃ¹ng), `_clean_row` (NaNâ†’None, numpyâ†’Python), `normalize_categories`, `numeric_column`|
|`tools/corpus/_sql.py`|DDL cá»§a `item_categories` vÃ  `items_fts`, cÃ¡c index (`idx_items_id` UNIQUE, `idx_items_domain`, `idx_items_price`, `idx_cat_item`, `idx_cat_cat`, **`idx_cat_item_cat (item_id, category)` â€” má»›i, hÆ°á»›ng xá»­ lÃ½ timeout `categories_any`**), cÃ¢u SQL náº¡p FTS. CÃ³ háº±ng `ITEMS_TABLE_SCHEMA`: **khÃ´ng** dÃ¹ng Ä‘á»ƒ táº¡o báº£ng (báº£ng do `DataFrame.to_sql` táº¡o trong `from_dataframe`) nhÆ°ng **cÃ³** dÃ¹ng Ä‘á»ƒ tÃ­nh `_CORPUS_SCHEMA_FINGERPRINT` (`_sql.py:79`; má»¥c 16 báº£n 29/10)|
|`tools/corpus/_schema.py`, `_error.py`|háº±ng sá»‘ (`COVERAGE_SAMPLE`, `QUERY_CHUNK_SIZE`â€¦); `SQLTimeOutError` (lá»›p con cá»§a `ToolInputError`)|
|`tools/corpus/apply_metadata_policy.py`|`apply_metadata_policy(corpus, policy, *, as_of_timestamp)`: chá»‘t policy metadata **má»™t láº§n** cho corpus (`historical_static_catalog` â†’ mask `price`/`average_rating`/`rating_number`; `snapshot` â†’ khÃ´ng mask); mask báº±ng TEMP VIEW `items` + authorizer `SQLITE_DENY` trÃªn cÃ¡c cá»™t bá»‹ mask; Ä‘á»•i policy/cutoff sau Ä‘Ã³ â†’ `ValueError` (pháº£i reload corpus)|
|ðŸ”´`tools/corpus/build_corpus.py`|ðŸ”´dá»±ng corpus tá»« `meta_<Domain>.jsonl.gz`, chá»‰ giá»¯ item cÃ³ trong mapping, nÃ©m `ValueError` náº¿u Ä‘á»™ phá»§ dÆ°á»›i `min_coverage`|
|`tools/_schema.py`|há»£p Ä‘á»“ng: `ITEM_COLUMNS`, `SCHEMA_HINT` (Ä‘Æ°a vÃ o thÃ´ng bÃ¡o lá»—i SQL Ä‘á»ƒ LLM sá»­a), `FILTER_KEYS`, `ORDER_COLUMNS`|
|`tools/_limits.py`|giá»›i háº¡n tá»« `agent/tools.yaml` (`MAX_CANDIDATES`, `MAX_QUERY_ROWS`, `SQL_TIME_BUDGET_SECONDS`, `SEMANTIC_*`, cÃ¡c default), **Ä‘á»c má»™t láº§n lÃºc import**|

**Báº£ng trong corpus:** `items(item_id, domain, original_item_id, title, store, price NULL, average_rating, rating_number, main_category)` (**`item_id` khÃ´ng pháº£i PRIMARY KEY**, tÃ­nh duy nháº¥t do `UNIQUE INDEX idx_items_id`; kiá»ƒu cá»™t theo dá»¯ liá»‡u, vd `rating_number` lÃ  INTEGER náº¿u má»i giÃ¡ trá»‹ nguyÃªn, REAL náº¿u cÃ³ thiáº¿u), `item_categories(item_id, category)` (multi-label), `items_fts` (FTS5 trÃªn title/store/main_category/categories, tokenizer `porter unicode61`). `price` Ä‘Æ°á»£c lÃ m sáº¡ch (bá» `$`, `,`; khoáº£ng giÃ¡ dáº¡ng `"10 - 20"` hoáº·c null â†’ NULL). Ráº¥t nhiá»u item thiáº¿u giÃ¡ (~55% á»Ÿ Video_Games) â†’ má»i filter giÃ¡ máº·c Ä‘á»‹nh loáº¡i item NULL trá»« khi `include_missing_price=true`. `rating_number`, `average_rating` lÃ  sá»‘ tá»•ng há»£p **Ä‘áº¿n cuá»‘i dataset** (khÃ´ng pháº£i táº¡i thá»i Ä‘iá»ƒm split) â€” xem Â§16.3.

---

# 24. Tools

**Vai trÃ²:** cÃ¡c thao tÃ¡c cÃ³ kiá»ƒm soÃ¡t mÃ  agent Ä‘Æ°á»£c phÃ©p gá»i. LLM chá»‰ tháº¥y `name`, `description`, `input_schema` vÃ  `output_schema` (khÃ´ng tháº¥y code).

## 24.1. Há»£p Ä‘á»“ng chung â€” `tools/base/`

|File|Viá»‡c|
|---|---|
|`tool.py`|`Tool` (ABC): `name`, `description`, `input_schema`, `output_schema`, `execute()` trá»«u tÆ°á»£ng. `__init_subclass__` **báº¯t buá»™c** subclass khai bÃ¡o cáº£ bá»‘n thuá»™c tÃ­nh vÃ  cáº¥m tÃªn tham sá»‘ `agent`/`action` (`TypeError` lÃºc Ä‘á»‹nh nghÄ©a class). `__call__` bá»c `execute()` báº±ng log (`ToolCallLogger`) vÃ  báº¯t `ToolInputError` thÃ nh `ToolResult(ok=False, error=â€¦)`; exception khÃ¡c Ä‘Æ°á»£c log (`ok=False`) rá»“i **nÃ©m láº¡i**|
|`_dataclass.py`|`ToolResult(ok, data, error)`|
|`_error.py`|`ToolInputError` (input sai: filter láº¡, SQL khÃ´ng an toÃ n, domain láº¡â€¦)|
|`tool_call_logger.py`|ghi call vÃ o bá»™ nhá»› (`input` rÃºt gá»n + tÃ³m táº¯t output, khÃ´ng lÆ°u toÃ n bá»™ output), tuá»³ chá»n thÃªm JSONL|
|`_helper.py`|`_hash_input` (hash kwargs), `_simplify_args` (rÃºt gá»n args trÆ°á»›c khi log)|
|`_validation.py`|`validate_list_like`, `validate_int`â€¦ (kiá»ƒm kiá»ƒu Ä‘áº§u vÃ o, nÃ©m `ToolInputError` rÃµ rÃ ng; dÃ¹ng chung cho tool); `validate_int` cÃ³ `allow_numpy` (nháº­n `numpy.integer`, váº«n tá»« chá»‘i `bool` / `np.bool_`)|
|`candidate_ids.py`|nháº­n `list[str]` hoáº·c `list[{item_id: â€¦}]` (tá»©c output tool khÃ¡c) â†’ list id Ä‘Ã£ dedupe; **tá»« chá»‘i** Ä‘áº§u vÃ o khÃ´ng pháº£i list/tuple (chuá»—i khÃ´ng cÃ²n bá»‹ tÃ¡ch tá»«ng kÃ½ tá»±). `candidate_results.py` (file riÃªng sau refactor): giá»¯ nguyÃªn dict (ká»ƒ cáº£ `score`/`similarity`), bá» trÃ¹ng theo `item_id` â€” **chÆ°a tool nÃ o dÃ¹ng**, chá»‰ cÃ³ test|
|`check_top_k.py`|kiá»ƒm `1 â‰¤ giÃ¡ trá»‹ â‰¤ upper` (máº·c Ä‘á»‹nh `MAX_CANDIDATES`); tá»« chá»‘i bool/float; thÃ´ng bÃ¡o dÃ¹ng Ä‘Ãºng tÃªn tham sá»‘ (`name=`); nay gá»i `validate_int(â€¦, allow_numpy=True)` thay vÃ¬ tá»± kiá»ƒm|

## 24.2. Báº£ng tá»•ng quan 6 tool

|Tool|NhÃ³m|VÃ o|Ra (top-level keys = Ä‘Æ°á»ng dáº«n `$N.path` há»£p lá»‡)|Dá»±a vÃ o|Planner cÃ³?|
|---|---|---|---|---|---|
|`SemanticSearchTool`|retrieval|`query` (tá»« khoÃ¡ tiáº¿ng Anh), `filters`, `limit`|`candidates` (kÃ¨m `score`), `total_matches` (`int`, **`None` náº¿u truy váº¥n Ä‘áº¿m háº¿t giá»**), `query_tokens`, `truncated`, `applied_filters`|corpus (FTS5 + BM25)|cÃ³|
|`SQLTool`|retrieval|`filters`, `order_by`, `descending`, `limit`|`candidates`, `total_matches`, `truncated`, `applied_filters`|corpus|**chÆ°a**|
|`ItemCFTool`|retrieval|`items` (seed), `top_k`, `domain`, `exclude_input`|`candidates` (`item_id`, `similarity`, `domain`), `unknown_items`|ma tráº­n similarity cá»§a ItemKNN|cÃ³|
|`RecoModelTool`|ranking|`user_id`, `candidates`, `top_k`, `exclude_seen`|`ranked`, `model`, `cold_start`, `excluded_seen`, `unscored_item_ids`|`CandidateScorer`|cÃ³|
|`QueryTool`|hydration|Ä‘Ãºng má»™t trong `item_ids` / `query` (SELECT) , `max_rows`|`items`, `missing_item_ids` (chá»‰ vá»›i `item_ids`), `truncated`|corpus|cÃ³|
|`MemoryTool`|memory|`user_id`, `top_n_categories`|`user_id`, `known`, `n_interactions`, `top_categories`, `price_range`|interactions + corpus|chá»‰ á»Ÿ `planner_memory`|

**Retrieval vs Ranking vs Hydration:** retrieval tráº£ "item nÃ o cÃ³ thá»ƒ liÃªn quan" (luÃ´n cÃ³ `item_id` nÃªn Ä‘Æ°a tháº³ng Ä‘Æ°á»£c vÃ o `RecoModelTool`); ranking tráº£ "trong cÃ¡c candidate nÃ y cÃ¡i nÃ o Ä‘á»©ng trÃªn"; hydration tráº£ metadata cho id Ä‘Ã£ biáº¿t.

## 24.3. Chi tiáº¿t tá»«ng tool

|File|Ghi chÃº Ä‘Ã¡ng biáº¿t|
|---|---|
|`sql_query/sql_tool.py` â€” `SQLTool`|Filter compile thÃ nh SQL **cÃ³ tham sá»‘**, key láº¡ bá»‹ tá»« chá»‘i â†’ LLM khÃ´ng thá»ƒ SQL-injection. Key há»£p lá»‡: `domain, price_min, price_max, include_missing_price, min_rating, min_rating_number, categories_any, categories_all, store, title_contains, exclude_item_ids`. **KhÃ´ng nháº­n danh sÃ¡ch candidate Ä‘á»ƒ lá»c** â€” tá»± truy váº¥n corpus. Sáº¯p xáº¿p NULL cuá»‘i, rá»“i `item_id` Ä‘á»ƒ deterministic; `filters` pháº£i lÃ  dict, `descending` pháº£i lÃ  bool (chuá»—i `"false"` khÃ´ng cÃ²n Ã¢m tháº§m sort DESC)|
|`sql_query/query_tool.py` â€” `QueryTool`|`item_ids` (tá»‘i Ä‘a `max_query_rows` id) hoáº·c má»™t `SELECT` tá»± do; tráº§n `max_query_rows` vÃ¬ káº¿t quáº£ Ä‘i tháº³ng vÃ o prompt; `item_ids` qua `validate_list_like`, pháº§n tá»­ pháº£i lÃ  chuá»—i khÃ¡c rá»—ng; `query` pháº£i lÃ  chuá»—i|
|`sql_query/compile_filters.py`|`compile_filters` (filter â†’ `WHERE` cÃ³ tham sá»‘, dÃ¹ng chung `SQLTool` + `SemanticSearchTool`; kiá»ƒm kiá»ƒu báº±ng `_as_list` / `_as_float` / `_as_int`, `store` so khá»›p khÃ´ng phÃ¢n biá»‡t hoa/thÆ°á»ng); tráº£ `(where, params, normalized_filters)` â€” `applied_filters` cá»§a `SQLTool` / `SemanticSearchTool` lÃ  báº£n **Ä‘Ã£ chuáº©n hoÃ¡**, khÃ´ng cÃ²n lÃ  filter thÃ´ LLM gá»­i|
|`retrieval/semantic_search_tool.py` â€” `SemanticSearchTool`|**Thá»±c táº¿ lÃ  lexical** (SQLite FTS5 + BM25), chÆ°a pháº£i embedding. Token `\w+`, bá» stopword, Ä‘áº·t trong nhÃ¡y kÃ©p, ná»‘i `OR` â†’ text ngÆ°á»i dÃ¹ng khÃ´ng inject Ä‘Æ°á»£c cÃº phÃ¡p FTS. Sáº¯p xáº¿p `score DESC, rating_number DESC, item_id`. `total_matches` Ä‘áº¿m báº±ng truy váº¥n MATCH thá»© hai; náº¿u **chá»‰** truy váº¥n Ä‘áº¿m háº¿t giá» thÃ¬ `total_matches = None` vÃ  váº«n tráº£ `candidates` (truy váº¥n chÃ­nh háº¿t giá» váº«n lÃ  `ok=False`). `input_schema` cá»§a _instance_ liá»‡t kÃª **tÃªn domain tháº­t** cá»§a corpus Ä‘á»ƒ planner khÃ´ng bá»‹a. Tá»“n táº¡i vÃ¬ ~72% user chá»‰ cÃ³ 1 interaction â†’ vá»›i há» chá»‰ cÃ³ "Ä‘iá»u há» nÃ³i"|
|`retrieval/_helper.py`, `retrieval/_schema.py`|`_tokenize` (helper) + `STOPWORDS` (schema; bá» `want`, `need`, `cheap`, `best`â€¦ â€” giÃ¡ Ä‘á»ƒ cho filter)|
|`ranking/item_cf_tool.py` â€” `ItemCFTool`|Cá»™ng cÃ¡c hÃ ng similarity cá»§a seed (khÃ´ng densify), tráº£ `unknown_items`. Cross-domain máº·c Ä‘á»‹nh; `domain` filter cÃ³ thá»ƒ tráº£ **Ã­t hÆ¡n** `top_k` vÃ¬ ItemKNN chá»‰ giá»¯ top-k lÃ¡ng giá»ng; `domain` láº¡ â†’ lá»—i `unknown domain â€¦; available: [â€¦]`, `domain=""` = khÃ´ng lá»c; tá»« chá»‘i `item2id` cÃ³ chá»‰ sá»‘ trÃ¹ng; `items` pháº£i lÃ  list chuá»—i khÃ¡c rá»—ng|
|`ranking/reco_model_tool.py` â€” `RecoModelTool`|Xáº¿p háº¡ng candidate báº±ng model (**khÃ´ng pháº£i LLM**). BÃ¡o `cold_start`, `excluded_seen`, `unscored_item_ids` thay vÃ¬ giáº¥u. KhÃ´ng cÃ³ timestamp: "as-of" Ä‘Æ°á»£c quyáº¿t Ä‘á»‹nh bá»Ÿi dá»¯ liá»‡u mÃ  model Ä‘Ã£ fit; kiá»ƒm kiá»ƒu `user_id` (chuá»—i khÃ¡c rá»—ng) vÃ  `exclude_seen` (bool); scorer tráº£ sai sá»‘ lÆ°á»£ng Ä‘iá»ƒm hoáº·c NaN/inf â†’ `ToolInputError`|
|`memory/memory_tool.py` â€” `MemoryTool`|**Chá»‰ Ä‘á»c** (khÃ´ng write/update/forget) vÃ¬ Amazon Reviews khÃ´ng cÃ³ há»™i thoáº¡i Ä‘á»ƒ trÃ­ch preference. Tá»•ng há»£p category hay mua + khoáº£ng giÃ¡ tá»« history. `as_of_timestamp` â†’ `check_profile_snapshot` cháº·n leakage. Output dÃ¹ng Ä‘Æ°á»£c qua ref, vd `"$1.top_categories"` â†’ `filters.categories_any`. Tá»•ng há»£p **báº±ng SQL** (`MIN/MAX` giÃ¡, `GROUP BY category`) nÃªn khÃ´ng bá»‹ giá»›i háº¡n 100 dÃ²ng cá»§a `corpus.select`. User láº¡ hoáº·c 0 tÆ°Æ¡ng tÃ¡c â†’ `known=False`, `top_categories=[]`, `price_range=None`, **khÃ´ng** nÃ©m lá»—i (nháº¥t quÃ¡n vá»›i cold-start cá»§a `RecoModelTool`). **Import public**: dÃ¹ng `package.memory.limits.get_memory_limits()` vÃ  `package.data.leakage.check_profile_snapshot()` thay vÃ¬ cross-folder private imports|

## 24.4. Scorer â€” `tools/score/`

|File|Viá»‡c|
|---|---|
|`candidate_scorer.py`|`CandidateScorer` (Protocol): `name`, `is_known_user`, `seen_items`, `score(user_idx, item_idxs)` â€” chá»— cáº¯m cho SASRec/BPR sau nÃ y|
|`baseline_scorer.py`|`BaselineScorer`: bá»c model há» DataFrame-based. Äiá»ƒm ItemKNN = tá»•ng similarity lÃ¡ng giá»ng vá»›i history + má»™t sá»‘ háº¡ng popularity ráº¥t nhá» (`1e-6`) Ä‘á»ƒ phÃ¡ hoÃ ; user khÃ´ng history â†’ chá»‰ popularity; `__init__` gá»i `_validate_model` (Ä‘á»™ dÃ i `popularity`, shape `user_items` / `similarity`, giÃ¡ trá»‹ há»¯u háº¡n)|

---

# 25. Recommendation models

**Vai trÃ²:** tÃ­n hiá»‡u gá»£i Ã½. Trong `package/tools/recommenders/` cÃ³ **hai há» class song song, trÃ¹ng tÃªn** â€” Ä‘Ã¢y lÃ  chá»— dá»… nháº§m nháº¥t cá»§a repo.

|Há»|File|API|DÃ¹ng á»Ÿ Ä‘Ã¢u|
|---|---|---|---|
|**DataFrame-based** (cho agent)|`baseline_popularity_recommender.py` (`BaselinePopularityRecommender`), `baseline_item_knn_recommender.py` (`BaselineItemKNNRecommender`); tÃªn cÅ© giá»¯ qua hai **lá»›p con rá»—ng** `popularity_recommender.py` (`PopularityRecommender`), `item_knn_recommender.py` (`ItemKNNRecommender`)|`fit(interactions_df)`, `.recommend(user_idx, k)`, cÃ³ `.scores`, `.user_items`, `.similarity`|`ItemCFTool`, `BaselineScorer` â†’ `RecoModelTool`, `Type1Agent`, `run_tools`, `run_agent_eval`. LÃ  `package.tools.recommenders.ItemKNNRecommender` / `PopularityRecommender`|
|**Matrix-based** (offline eval)|`recommender.py` (`Recommender` ABC), `popularity_matrix_recommender.py` (`PopularityMatrixRecommender`), `item_knn_matrix_recommender.py` (`ItemKNNMatrixRecommender`), `bpr_mf_recommender.py`, `random_recommender.py`, `fallback_recommender.py`, `build_model.py`|`fit(csr_matrix)`, `.score_batch()`, `.recommend(user_idxs, k, exclude)`|`run_baselines`, `tune_baselines`, `candidate_recall`, `tools/evaluation/`. TÃªn cÅ© cÃ²n lÃ  **alias** (khÃ´ng pháº£i ABC dÃ¹ cÃ³ háº­u tá»‘): `ItemKNNRecommenderABC = ItemKNNMatrixRecommender`, `PopularityRecommenderABC = PopularityMatrixRecommender`|

| File                                                   | Viá»‡c                                                                                                                                                                                                                                     |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `baseline_popularity_recommender.py`                   | Ä‘áº¿m táº§n suáº¥t item trong táº­p fit; cÃ³ `user_items` (CSR nhá»‹ phÃ¢n); kiá»ƒm cá»™t `user_idx` / `item_idx`, dá»¯ liá»‡u rá»—ng, `top_k` nguyÃªn dÆ°Æ¡ng                                                                                                    |
| `baseline_item_knn_recommender.py`                     | káº¿ thá»«a Popularity; cosine itemâ€“item tá»« co-occurrence, giá»¯ `neighbors` (máº·c Ä‘á»‹nh 20) lÃ¡ng giá»ng má»—i item; user khÃ´ng history â†’ popularity                                                                                                |
| `popularity_recommender.py`, `item_knn_recommender.py` | lá»›p con **rá»—ng** cá»§a hai lá»›p trÃªn, giá»¯ tÃªn cÅ© cho code hiá»‡n cÃ³; tá»“n táº¡i Ä‘á»ƒ thoáº£ luáº­t "tÃªn cÃ´ng khai duy nháº¥t" khi lá»›p ma tráº­n Ä‘á»•i tÃªn                                                                                                    |
| `recommender.py`                                       | `Recommender` ABC: `fit`, `_fit`, `score_batch`, `history_sizes`, `recommend` (loáº¡i item trong `exclude`); `_prepare_train_matrix` chuáº©n hoÃ¡ ma tráº­n train; `recommend` tráº£ `int64` vá»›i `-1` **chá»‰ lÃ  padding**; Ä‘iá»ƒm NaN â†’ `ValueError` |
| `popularity_matrix_recommender.py`                     | popularity dáº¡ng ma tráº­n                                                                                                                                                                                                                  |
| `item_knn_matrix_recommender.py`                       | ItemKNN dáº¡ng ma tráº­n, tÃ­nh theo block (`block_elements`) Ä‘á»ƒ khÃ´ng ná»• RAM; máº·c Ä‘á»‹nh `k=50`                                                                                                                                                |
| `bpr_mf_recommender.py`                                | BPR-MF tá»± cÃ i báº±ng numpy (negative sampling, SGD theo batch); máº·c Ä‘á»‹nh `learning_rate=0.05`; kiá»ƒm tham sá»‘; `_sample_negatives` láº¥y Ä‘Ãºng item chÆ°a tÆ°Æ¡ng tÃ¡c (tá»‘i Ä‘a 10 vÃ²ng rejection, rá»“i láº¥y chÃ­nh xÃ¡c tá»« pháº§n bÃ¹ cá»§a user)            |
| `random_recommender.py`                                | baseline ngáº«u nhiÃªn cÃ³ seed                                                                                                                                                                                                              |
| `fallback_recommender.py`                              | `FallbackRecommender(primary, fallback)`: user khÃ´ng history dÃ¹ng Ä‘iá»ƒm cá»§a fallback (popularity)                                                                                                                                         |
| `build_model.py`                                       | `ALL_MODELS = [random, popularity, item_knn, bpr_mf]`, `build_model(name, cfg)`; bá»c `FallbackRecommender` náº¿u `popularity_fallback: true`; seed riÃªng cá»§a model (`bpr_mf.seed`) ghi Ä‘Ã¨ seed toÃ n cá»¥c                                    |
| `build_interaction_matrix.py`                          | DataFrame â†’ CSR nhá»‹ phÃ¢n vá»›i shape cho trÆ°á»›c                                                                                                                                                                                             |
| `_helper.py`                                           | `_append_popular_unseen`, `_user_item_matrix` (gáº§n trÃ¹ng `build_interaction_matrix` nhÆ°ng tá»± suy shape), `_keep_top_neighbors`                                                                                                           |
| `file_hash.py`                                         | `file_hash(path)` â€” hash ná»™i dung file, dÃ¹ng cho provenance cá»§a artifact (`.npz` ItemKNN, `.sqlite` corpus)                                                                                                                              |
| `mapping_hash.py`                                      | `mapping_hash(mapping)` â€” hash cáº£ tÃªn láº«n chá»‰ sá»‘ cá»§a `user2id` / `item2id`, khÃ´ng phá»¥ thuá»™c thá»© tá»± dict                                                                                                                                  |
| `fit_split_names.py`                                   | `fit_split_names(eval_on)` â†’ `["train"]` (validation) hoáº·c `["train", "validation"]` (test); `eval_on` khÃ¡c hai giÃ¡ trá»‹ nÃ y â†’ `ValueError`                                                                                               |
| `fit_provenance.py`                                    | `fit_provenance(fit_pairs, *, user2id, item2id, eval_on, tag)` â†’ dict provenance (`scope`, hash 2 mapping, `eval_on`, `fit_splits`, `tag`); thiáº¿u má»™t trong hai mapping, hoáº·c chá»‰ sá»‘ fit vÆ°á»£t chiá»u mapping â†’ `ValueError`             |
| Há»‡ quáº£:                                                |                                                                                                                                                                                                                                          |

- **`BPRMFRecommender` hiá»‡n chá»‰ dÃ¹ng trong Ä‘Ã¡nh giÃ¡ baseline offline.** `BaselineScorer` Ä‘Ã²i model cÃ³ `.scores`, `.user_items`, `.num_items` â€” chá»‰ há» DataFrame-based cÃ³. Muá»‘n BPR/SASRec lÃ m ranker cho agent thÃ¬ viáº¿t thÃªm má»™t class thoáº£ `CandidateScorer`.
- CÃ¹ng key `eval/baselines.yaml â†’ item_knn.k` Ä‘iá»u khiá»ƒn **cáº£ hai há»**; `block_elements` chá»‰ há» matrix Ä‘á»c. Máº·c Ä‘á»‹nh trong class lá»‡ch YAML (ItemKNN matrix `k=50`, DataFrame `neighbors=20`, BPR `learning_rate` 0.05 so vá»›i 0.001).
- `tune_baselines` chá»‰ cho phÃ©p `popularity`, `item_knn`, `bpr_mf` (khÃ´ng tune `random`).
- **Hai ItemKNN khÃ´ng cho cÃ¹ng thá»© háº¡ng khi bá»‹ cáº¯t top-k:** `ItemKNNRecommender` (DataFrame) vÃ  `ItemKNNMatrixRecommender` cháº¥m Ä‘iá»ƒm theo hai hÆ°á»›ng ngÆ°á»£c nhau (`history @ S` so vá»›i `history @ S.T`) nÃªn chá»‰ khá»›p khi khÃ´ng cáº¯t lÃ¡ng giá»ng (chÃº thÃ­ch trong `recommenders/__init__.py`, test `tests/tools/recommenders/test_contract_recommenders.py`).

**Hardening á»Ÿ snapshot 17/10** (theo diff so vá»›i snapshot 11/10 vÃ  docstring má»›i; chÆ°a tÃ¡i hiá»‡n láº¡i tá»«ng má»¥c): `Recommender` chuáº©n hoÃ¡ ma tráº­n train (`_prepare_train_matrix`: gá»™p trÃ¹ng, bá» sá»‘ 0, tá»« chá»‘i NaN / Ã¢m / khÃ´ng pháº£i ma tráº­n thÆ°a); `recommend` tráº£ `-1` chá»‰ khi Ã­t hÆ¡n k item khuyáº¿n nghá»‹ Ä‘Æ°á»£c; toÃ n Ä‘iá»ƒm há»£p lá»‡ báº±ng 0 thÃ¬ dÃ¹ng popularity lÃ m Ä‘iá»ƒm; `BPRMFRecommender` kiá»ƒm tham sá»‘ vÃ  láº¥y máº«u item Ã¢m Ä‘Ãºng; factory khÃ´ng cÃ²n lá»—i `multiple values for keyword 'seed'`; `PopularityRecommender` (há» DataFrame) kiá»ƒm Ä‘áº§u vÃ o. Váº«n Ä‘Ãºng: `BPRMFRecommender` chÆ°a cÃ³ scorer cho agent.

---

# 26. API layer â€” `package/api/` (trÆ°á»›c lÃ  `package/llm/`)

**Vai trÃ²:** giao diá»‡n thá»‘ng nháº¥t tá»›i LLM; pháº§n cÃ²n láº¡i cá»§a repo chá»‰ biáº¿t `LLMProvider`. Tá»« snapshot 17/10 thÆ° má»¥c Ä‘á»•i tÃªn tá»« `package/llm/` thÃ nh `package/api/` vÃ  khÃ´ng cÃ²n thÆ° má»¥c con `providers/` (khÃ´ng cÃ²n tham chiáº¿u `package.llm` nÃ o trong code). TÃªn `api/` dá»… hiá»ƒu nháº§m lÃ  API serving; thá»±c táº¿ Ä‘Ã¢y lÃ  táº§ng gá»i LLM. Sau refactor má»—i file giá»¯ má»™t public symbol (má»¥c 2.6); docstring cÃ²n trÃ­ch "spec má»¥c XXI" (má»¥c 16.2).

|File|Viá»‡c|
|---|---|
|`llm_provider.py`|`LLMProvider` (ABC): `complete(messages, *, temperature, max_tokens, response_format_json)`, `health_check()`|
|`openai_compatible_provider.py`|`OpenAICompatibleProvider` â€” OpenAI / vLLM / Ollama / LM Studio qua `urllib` (khÃ´ng SDK). `response_format_json=True` â†’ `{"type": "json_object"}`. Lá»—i máº¡ng/timeout/JSON há»ng â†’ `LLMProviderError`. `health_check` gá»­i má»™t request `ping` tháº­t. Docstring cÃ²n ghi chÃº `BLOCKED` (cáº§n endpoint tháº­t) vÃ  nháº¯c `scripts/tools/check_llm_provider.py` Ä‘á»ƒ xÃ¡c nháº­n|
|`build_llm_provider.py`|`build_llm_provider(config)` Ä‘á»c `agent/llm.yaml`; thiáº¿u `base_url` hoáº·c `model` â†’ `ValueError`; provider láº¡ â†’ `ValueError`|
|`_dataclass.py`|`LLMMessage(role, content)`, `LLMResponse(text, raw, prompt_tokens, completion_tokens, latency_seconds, provider_name, model_name, metadata)`|
|`_error.py`|`LLMProviderError`|
|`__init__.py`|export `LLMMessage`, `LLMProviderError`, `LLMProvider`, `build_llm_provider`, `OpenAICompatibleProvider` (`LLMResponse` khÃ´ng Ä‘Æ°á»£c export á»Ÿ cáº¥p `package.api`, import tá»« `package.api._dataclass`)|

KhÃ´ng cÃ³ `MockLLMProvider`; test dÃ¹ng `ScriptedLLM` Ä‘á»‹nh nghÄ©a trong `tests/agents/test_plan_executor.py`. `inference` (má»¥c 9.4) vÃ  `demo` (má»¥c 13.1) cÅ©ng import tá»« `package.api`.

---

# 27. Agent layer â€” `package/agents/`

**Vai trÃ²:** ghÃ©p LLM vÃ  tool. Hiá»‡n cÃ³ hai agent: `PlanExecutor` (LLM viáº¿t toÃ n bá»™ plan má»™t láº§n rá»“i cháº¡y; náº¿u lá»—i thÃ¬ sá»­a plan thÃªm `reflect_rounds` láº§n vá»›i quality gate) vÃ  `Type1Agent` (plan cá»‘ Ä‘á»‹nh, khÃ´ng LLM). **Há»— trá»£ multi-turn conversation qua `Session`**. Káº¿t quáº£ cá»§a agent Ä‘Æ°á»£c `package/inference` (má»¥c 9.4) biáº¿n thÃ nh cÃ¢u tráº£ lá»i cuá»‘i.

## 27.1. CÃ¡ch `PlanExecutor` hoáº¡t Ä‘á»™ng

1. `build_tool_prompt()` biáº¿n má»—i tool thÃ nh `- <name>: <description>` + `input_schema` + `returns` (= `output_schema`); LLM chá»‰ tháº¥y **mÃ´ táº£ vÃ  schema vÃ o/ra**, khÃ´ng tháº¥y code.
2. LLM tráº£ JSON `{"steps": [{"tool": ..., "args": {...}}], "ask_user": null}` (JSON mode). Reply sai Ä‘á»‹nh dáº¡ng â†’ retry tá»‘i Ä‘a `plan_retries` láº§n kÃ¨m thÃ´ng bÃ¡o lá»—i (chá»‰ cho JSON sai, **khÃ´ng** cho lá»—i provider). HÃ ng rÃ o ` ```json ` Ä‘Æ°á»£c tá»± bÃ³c.
3. Plan dÃ i hÆ¡n `max_steps` bá»‹ cáº¯t (`last_truncated = True`).
4. Má»—i step cháº¡y tuáº§n tá»±. Arg tham chiáº¿u output step trÆ°á»›c báº±ng `"$N.path"`, vd `"$1.candidates"`, `"$2.ranked.*.item_id"` (`*` = láº¥y field tá»« má»i pháº§n tá»­ list). **Multi-turn:** cÃ³ thá»ƒ tham chiáº¿u session state báº±ng `"$S.field"` (vd `$S.shown_items`, `$S.candidates`, `$S.ranked`, `$S.constraints`, `$S.shown_items.1` cho item thá»© 2). Chuá»—i tham chiáº¿u pháº£i lÃ  **toÃ n bá»™** giÃ¡ trá»‹ arg.
5. Chá»‘t an toÃ n (tool **khÃ´ng Ä‘Æ°á»£c gá»i** náº¿u vi pháº¡m):
    - tÃªn tool láº¡ â†’ `unknown tool`;
    - `user_id` / `items` / `item_ids` literal **khÃ´ng xuáº¥t hiá»‡n trong cÃ¢u request hoáº·c session** â†’ coi lÃ  bá»‹a id (`invented_ids`);
    - **arg khÃ´ng cÃ³ trong `input_schema`** â†’ lá»—i cÃ³ gá»£i Ã½ (vd `'price_max' belongs inside 'filters'`); tool khÃ´ng khai bÃ¡o schema thÃ¬ khÃ´ng bá»‹ kiá»ƒm tra;
    - ref há»ng hoáº·c arg sai kiá»ƒu â†’ chá»‰ step Ä‘Ã³ lá»—i (`skipped, step N failed`), cÃ¡c step cÃ²n láº¡i váº«n cháº¡y;
    - thiáº¿u thÃ´ng tin â†’ LLM tráº£ `steps: []` kÃ¨m `ask_user` Ä‘á»ƒ há»i láº¡i thay vÃ¬ Ä‘oÃ¡n.
6. Sau `plan()`/`run()`, cÃ¡c thuá»™c tÃ­nh `last_plan`, `last_question`, `last_response`, `last_usage` (token, latency, sá»‘ láº§n thá»­; cá»™ng dá»“n má»i láº§n gá»i LLM, reflect gá»“m cáº£), `last_truncated` mÃ´ táº£ request gáº§n nháº¥t.
7. **Plan-reflect** (`reflect_rounds`, máº·c Ä‘á»‹nh 1; 0 = táº¯t): náº¿u plan cháº¡y xong nhÆ°ng cÃ³ step lá»—i, hoáº·c khÃ´ng ra item nÃ o (vÃ  khÃ´ng pháº£i `ask_user`), `run()` gá»­i cho LLM bÃ¡o cÃ¡o tá»«ng step (`_step_report`, lá»—i cáº¯t `reflect_error_chars` kÃ½ tá»±, máº·c Ä‘á»‹nh 300) rá»“i cháº¡y plan Ä‘Ã£ sá»­a, tá»‘i Ä‘a `reflect_rounds` láº§n. **KhÃ´ng reflect** khi cÃ³ step dÃ¹ng id bá»‹a hoáº·c cháº¡m time budget SQL (plan má»›i khÃ´ng giÃºp Ã­ch: `_blocks_reflect`). **Quality gate:** reflection chá»‰ Ä‘Æ°á»£c cháº¥p nháº­n náº¿u cáº£i thiá»‡n quality (fewer failed steps, more items, fewer error kinds). Reply reflect khÃ´ng dÃ¹ng Ä‘Æ°á»£c (hoáº·c lá»—i provider lÃºc reflect) thÃ¬ bá»‹ bá» vÃ  giá»¯ káº¿t quáº£ trÆ°á»›c. Thuá»™c tÃ­nh thÃªm: `last_reflections` (sá»‘ lÆ°á»£t Ä‘Ã£ dÃ¹ng, reply há»ng cÅ©ng tÃ­nh), `last_first_attempt_ok`, `last_attempt_plans`.
8. **Session update:** sau má»—i turn thÃ nh cÃ´ng, PlanExecutor cáº­p nháº­t Session vá»›i turns, shown_items, candidates, ranked (method `_update_session`).

`output_schema` cá»§a má»—i tool Ä‘Æ°á»£c render vÃ o prompt (dÃ²ng `returns:`) Ä‘á»ƒ LLM biáº¿t tÃªn field há»£p lá»‡ cho `$N.path`; nÃ³ **chÆ°a** Ä‘Æ°á»£c dÃ¹ng Ä‘á»ƒ kiá»ƒm tra ref lÃºc cháº¡y (`_resolve_path` duyá»‡t káº¿t quáº£ tháº­t).

## 27.2. `Type1Agent`

KhÃ´ng LLM, chuá»—i cá»‘ Ä‘á»‹nh: `ItemCFTool` (láº¥y `max(top_k Ã— candidate_multiplier, min_candidates)` candidate quanh seed; máº·c Ä‘á»‹nh 5 vÃ  50 trong `agent.yaml â†’ type1`) â†’ `RecoModelTool` (xáº¿p háº¡ng cho `user_id`) â†’ `QueryTool` (gáº¯n metadata). BÆ°á»›c nÃ o lá»—i tráº£ `{"ok": False, "stage": "retrieve"|"rank"|"fetch", "error": â€¦}`. Chá»‰ Ã¡p dá»¥ng cho request kiá»ƒu `similar` (cáº§n seed item).

## 27.3. Tá»«ng file

|File|Viá»‡c|
|---|---|
||`planner/plan_executor.py`|`PlanExecutor` (má»¥c 9.1). Giá»›i háº¡n máº·c Ä‘á»‹nh tá»« `agent/agent.yaml`, ghi Ä‘Ã¨ Ä‘Æ°á»£c qua tham sá»‘. Má»—i entry step nay cÃ³ thÃªm `error_kind` (`unknown_tool` / `invented_id` / `unknown_args` / `tool_error` / `bad_reference` / `exception`). CÃ³ method `_update_session()` Ä‘á»ƒ cáº­p nháº­t session sau má»—i turn|
||`session.py`|`Session`: quáº£n lÃ½ state multi-turn conversation (turns, shown_items, candidates, ranked, constraints, feedback). _Turn (internal dataclass): 1 lÆ°á»£t há»™i thoáº¡i. Limits (max_turns, max_shown_items, max_candidates, max_turn_chars). Methods: `add_turn`, `add_shown_items`, `set_candidates`, `update_constraints`, `add_exclusions`, `add_feedback`, `get_valid_ids`, `reset`, `to_dict`|
|`planner/_prompt.py`|`SYSTEM_PROMPT` cá»§a planner: luáº­t (chá»‰ dÃ¹ng tool/arg cÃ³ sáºµn, khÃ´ng bá»‹a id, cÃ¡ch viáº¿t ref, luÃ´n rank báº±ng `RecoModelTool` rá»“i fetch báº±ng `QueryTool`, thiáº¿u thÃ´ng tin thÃ¬ `ask_user`) + má»™t vÃ­ dá»¥. Chá»‰ nháº¯c `ItemCFTool`, `SemanticSearchTool`, `RecoModelTool`, `QueryTool`|
|`planner/_schema.py`|ngá»¯ phÃ¡p tham chiáº¿u `_REF` vÃ  `ID_ARG_KEYS = (user_id, items, item_ids)`|
|`planner/_helper.py`|`_extract_plan`, `_resolve_refs`/`_resolve_path`, `_invented_ids`, `_unknown_args`; cho plan-reflect: `_is_time_budget`, `_is_bad_reference`, `_blocks_reflect`, `_reflect_problem`, `_step_report`; hÃ m cÃ´ng khai `check_time_budget_error` (dÃ¹ng chung vá»›i `layer5_deployment`)|
|`type1/type1_agent.py`|`Type1Agent` (má»¥c 9.2)|
|`toolkit/agent_tools.py`|`AgentTools`: **nÆ¡i duy nháº¥t liá»‡t kÃª tool cho agent**; `for_planner()` (5 tool: item_cf, reco, query, search, sql), `for_planner_memory()` (+ `MemoryTool`)|
|`toolkit/build_tools.py`|`build_tools(knn, scorer, user2id, item2id, interactions, corpus, â€¦)` â†’ `AgentTools`|
|`toolkit/build_tool_prompt.py`|tool â†’ text cho system prompt (render `input_schema` vÃ  `returns` = `output_schema`)|
|`results/extract_recommendations.py`|"ngÆ°á»i dÃ¹ng thá»±c sá»± tháº¥y gÃ¬": Æ°u tiÃªn `ranked` cá»§a `RecoModelTool` > retrieval > `QueryTool`. Chuyá»ƒn tá»« `agents/evaluation/` sang Ä‘Ã¢y Ä‘á»ƒ `inference`, `evaluation` dÃ¹ng chung mÃ  khÃ´ng vi pháº¡m hÆ°á»›ng phá»¥ thuá»™c|
|`_schema.py`|`TEMPLATES`: cÃ¢u request máº«u theo ngÃ´n ngá»¯ (`vi` / `en`) vÃ  kind â€” dÃ¹ng bá»Ÿi `evaluation/agent/build_requests.py` vÃ  `demo/samples/sample_requests.py`|
|`_limits.py`|`AgentLimits` tá»« `agent/agent.yaml` (validate; gá»“m `reflect_rounds â‰¥ 0`, `reflect_error_chars`, `type1_candidate_multiplier`, `type1_min_candidates`)|
|`__init__.py`|export `PlanExecutor`, `Type1Agent`, `AgentTools`, `build_tools`, `build_tool_prompt`, `extract_recommendations`, `get_agent_limits`, `TEMPLATES`|

(`package/evaluation/agent/` á»Ÿ má»¥c 10.3, `package/evaluation/ablation/` á»Ÿ má»¥c 10.4, `package/inference/` á»Ÿ má»¥c 9.4. ThÆ° má»¥c `agents/ablation/` vÃ  `agents/evaluation/` cÃ²n sÃ³t láº¡i trong zip nhÆ°ng **rá»—ng** â€” chá»‰ cÃ³ `__pycache__`.)

## 27.4. Inference â€” cÃ¢u tráº£ lá»i cuá»‘i (`package/inference/`)

**Vai trÃ²:** bÆ°á»›c _trÃ¬nh bÃ y_. Nháº­n káº¿t quáº£ agent Ä‘Ã£ chá»n vÃ  viáº¿t cÃ¢u tráº£ lá»i cho ngÆ°á»i dÃ¹ng; **khÃ´ng chá»n láº¡i, khÃ´ng thÃªm / bá»›t / Ä‘á»•i thá»© tá»± item**. KhÃ´ng pháº£i vÃ²ng láº·p "quan sÃ¡t káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿" (má»¥c 15). Config: `agent/inference.yaml`.

Luá»“ng: káº¿t quáº£ agent â†’ `outcome_from_*` â†’ `AgentOutcome` â†’ `classify_outcome` (status) â†’ `compose_answer` â†’ `Answer`.

|File|Viá»‡c|
|---|---|
|`_dataclass.py`|`AgentOutcome(request_text, items, question, errors, invented_ids, cold_start, n_steps)` â€” agent Ä‘Ã£ lÃ m gÃ¬; `Answer(status, text, items, grounded, composer, fallback_reason, usage, reason)` â€” ngÆ°á»i dÃ¹ng tháº¥y gÃ¬|
|`outcome/outcome_from_plan_results.py`|káº¿t quáº£ `PlanExecutor.run()` â†’ `AgentOutcome`: item = `extract_recommendations(...)` (tá»« `agents/results/`; cÃ¹ng id, cÃ¹ng thá»© tá»± vá»›i `trajectory["recommended"]`), bá» trÃ¹ng, cáº¯t `max_items`; metadata láº¥y tá»« output tool (`QueryTool` trÆ°á»›c, rá»“i dÃ²ng cá»§a search / ranker), khÃ´ng bá»‹a; lá»—i tool vÃ  lá»—i planner vÃ o `errors`|
|`outcome/outcome_from_type1.py`|output `Type1Agent.recommend()` â†’ `AgentOutcome`|
|`outcome/classify_outcome.py`|status theo luáº­t, khá»›p Ä‘áº§u tiÃªn tháº¯ng: `ask_user` (cÃ³ cÃ¢u há»i vÃ  0 step) â†’ `tool_error` (id bá»‹a; lá»—i planner) â†’ `ok` (cÃ³ item; náº¿u cÃ³ tool lá»—i thÃ¬ ghi `partial: â€¦ failed`) â†’ `tool_error` (cÃ³ lá»—i mÃ  khÃ´ng cÃ³ item) â†’ `no_result`|
|`compose/compose_template.py`|cÃ¢u tráº£ lá»i **táº¥t Ä‘á»‹nh, khÃ´ng LLM**: vÄƒn báº£n cá»‘ Ä‘á»‹nh (tiáº¿ng Viá»‡t) cho `no_result` / `tool_error`, cÃ¢u há»i cá»§a planner cho `ask_user`, danh sÃ¡ch Ä‘Ã¡nh sá»‘ cho `ok` (giÃ¡, rating, store náº¿u cÃ³)|
|`compose/compose_llm.py`|LLM viáº¿t (JSON `{answer, mentioned_item_ids}`), kiá»ƒm grounding, retry `llm_retries` láº§n kÃ¨m lÃ½ do; háº¿t lÆ°á»£t hoáº·c lá»—i provider thÃ¬ lÃ¹i vá» template (`fallback_reason`). **KhÃ´ng nÃ©m lá»—i**. Chá»‰ status `ok` má»›i gá»i LLM|
|`compose/compose_answer.py`|Ä‘iá»ƒm vÃ o `compose_answer(outcome, llm=None, mode=â€¦)`: mode `template`, status khÃ¡c `ok` hoáº·c `llm=None` â‡’ khÃ´ng gá»i LLM (`fallback_reason="no_llm"`)|
|`compose/item_view.py`, `compose/cut_title.py`|`item_view`: item nhÆ° LLM nhÃ¬n tháº¥y; `cut_title`: cáº¯t tiÃªu Ä‘á» cÃ²n `title_chars` (máº·c Ä‘á»‹nh 120) kÃ½ tá»±, thÃªm `â€¦`|
|`compose/_prompt.py`|system prompt + cÃ¡c cÃ¢u cá»‘ Ä‘á»‹nh (tiáº¿ng Viá»‡t)|
|`grounding/check_grounding.py`, `grounding/parse_llm_reply.py`, `grounding/_helper.py`|`parse_llm_reply`; `check_grounding` (JSON há»£p lá»‡, id cÃ³ trong dá»¯ liá»‡u, Ä‘á»§ item vÃ  Ä‘Ãºng thá»© tá»±; náº¿u `check_numbers` thÃ¬ giÃ¡ / rating trong cÃ¢u khÃ´ng lá»‡ch quÃ¡ `price_tolerance`); `ids_in_text` vÃ  trÃ­ch giÃ¡ / rating (ná»™i bá»™)|
|`cut.py`, `empty_usage.py`|`cut`: cáº¯t lÃ½ do / lá»—i cÃ²n `reason_chars` (máº·c Ä‘á»‹nh 300) kÃ½ tá»±; `empty_usage`: dict usage rá»—ng|
|`_schema.py`, `_limits.py`|`ITEM_FIELDS`, `STATUSES = (ok, ask_user, no_result, tool_error)`, `MODES = (llm, template)`; `InferenceLimits` tá»« `agent/inference.yaml` (validate)|
|`__init__.py`|export `compose_answer`, `compose_llm`, `compose_template`, `classify_outcome`, `outcome_from_plan_results`, `outcome_from_type1`, `empty_usage`, `AgentOutcome`, `Answer`, `MODES`, `get_inference_limits`|
|**Trong Ä‘Ã¡nh giÃ¡:** `run_agent_eval.py --inference-mode llm|template`gáº¯n cÃ¢u tráº£ lá»i vÃ o trajectory cá»§a`type1`,` planner`,` planner_memory `(`INFERENCE_AGENTS`; baseline khÃ´ng cÃ³). VÃ¬ chá»‰ trÃ¬nh bÃ y nÃªn` recommended`,` task_success`, recallâ€¦ **khÃ´ng Ä‘á»•i**; cÃ¢u tráº£ lá»i Ä‘Æ°á»£c cháº¥m báº±ng cá»™t riÃªng (má»¥c 10.3).` --resume` khÃ´ng trá»™n cÃ¢u tráº£ lá»i LLM vÃ  template trong má»™t thÃ­ nghiá»‡m.|

**Äiá»u cáº§n biáº¿t:** `docs/inference_contract.md` mÃ  báº£n cÅ© trÃ­ch **khÃ´ng tá»“n táº¡i** (má»¥c 16); luá»“ng vÃ  báº£ng Ã¡nh xáº¡ status náº±m ngay trong code â€” `outcome/classify_outcome.py` vÃ  `_schema.STATUSES`. `demo` **Ä‘Ã£** gá»i `compose_answer` (má»¥c 13.1).

---

# 28. Evaluation

CÃ³ **bá»‘n** loáº¡i Ä‘Ã¡nh giÃ¡: ba loáº¡i Ä‘áº§u tráº£ lá»i ba cÃ¢u há»i vá» mÃ´ hÃ¬nh / agent, loáº¡i thá»© tÆ° so sÃ¡nh cÃ¡c láº§n cháº¡y.

|Loáº¡i|CÃ¢u há»i|Script|Cáº§n LLM?|
|---|---|---|---|
|Offline recommender|Model nÃ o gá»£i Ã½ tá»‘t hÆ¡n trÃªn split?|`run_baselines`, `tune_baselines`|khÃ´ng|
|Candidate recall|Retrieval cÃ³ Ä‘Æ°a item held-out vÃ o tay reranker khÃ´ng?|`candidate_recall`|khÃ´ng|
|Agent eval|Táº§ng agent cÃ³ thÃªm giÃ¡ trá»‹ so vá»›i recommender thuáº§n khÃ´ng, vÃ  á»Ÿ Ä‘Ã¢u?|`run_agent_eval`|cÃ³ (trá»« `baseline`, `type1`)|
|So sÃ¡nh cÃ¡c láº§n cháº¡y (ablation)|Cáº¥u hÃ¬nh A cÃ³ hÆ¡n B khÃ´ng, cÃ³ Ã½ nghÄ©a thá»‘ng kÃª khÃ´ng?|`compare_experiments`|khÃ´ng (chá»‰ Ä‘á»c `exp_NNN`)|

## 28.1. Offline recommender â€” `package/tools/evaluation/`

(Náº±m trong `tools/` nhÆ°ng **khÃ´ng pháº£i Tool** â€” chá»‰ lÃ  bá»™ Ä‘Ã¡nh giÃ¡ offline.)

|File|Viá»‡c|
|---|---|
|`evaluate_recommender.py`|`evaluate_recommender(model, exclude, target, ks, sparse_max)` â†’ `EvaluationResult`: metric tá»•ng + theo segment cold/sparse/warm, `catalog_coverage@k`, `target_item_seen_ratio` (Ä‘Æ°á»ng chÃ­nh, há» matrix-based)|
|`metrics/`|`ranking_metrics_at_k(hits, num_relevant, k)`: precision/recall/hit-rate/NDCG/MRR/MAP@k vectorised, má»—i metric má»™t file (`recall_at_k.py`, `precision_at_k.py`, `hit_rate_at_k.py`, `ndcg_at_k.py`, `mrr_at_k.py`, `average_precision_at_k.py`, gá»™p bá»Ÿi `ranking_metrics_at_k.py`; cÅ©ng Ä‘Æ°á»£c `score_trajectory` cá»§a agent eval dÃ¹ng)|
|`evaluate_ranking.py`|`evaluate_ranking(model, interactions_df, ks)`: cÃ¹ng cÃ¡c metric nhÆ°ng vÃ²ng láº·p tá»«ng user, cho há» DataFrame-based; **chá»‰ dÃ¹ng trong test**|
|`_dataclass.py`|`EvaluationResult`|
|`_helper.py`|`assign_segments` (cold = 0 history, sparse â‰¤ `sparse_max`, warm), `_git_commit`|
|`segment_users_by_history.py`|`segment_users_by_history(users, history_sizes, sparse_max)` â†’ `{user_idx: segment}` theo sá»‘ interaction trong dá»¯ liá»‡u fit|
|`select_fit_target.py`|giao thá»©c fit/target dÃ¹ng chung: `validation` â†’ fit = train; `test` â†’ fit = train + validation|
|`save_experiment.py`|ghi `exp_NNN/{config.yaml, metrics.json, README.md}` (kÃ¨m git commit, pháº§n cá»©ng, seed, thá»i gian cháº¡y)|
|`next_experiment_dir.py`|tÃªn thÆ° má»¥c `exp_NNN` káº¿ tiáº¿p|
|`parameter_grid.py` / `merge_model_params.py`|khai triá»ƒn lÆ°á»›i tham sá»‘ / ghi Ä‘Ã¨ tham sá»‘ cá»§a má»™t model trong config baseline|
|`hardware_info.py`|platform, python, sá»‘ CPU|
|`evaluation_protocol.py`|`evaluation_protocol(..., eval_on, tag, fit_df, target_df, user2id, item2id, segments, sampled, metadata_policy, evaluation_kind)`: báº¯t fit **hoÃ n toÃ n trÆ°á»›c** target theo timestamp, cutoff metadata pháº£i báº±ng `target.min`, rá»“i tráº£ dict mÃ´ táº£ protocol (provenance ItemKNN, chÃ­nh sÃ¡ch label / cohort / history, cá»¡ máº«u theo segment)|
|`normalize_query_text.py`|`normalize_query_text(query, mode)`: `raw` (nguyÃªn vÄƒn) hoáº·c `ascii_fold` (bá» dáº¥u, kÃ½ tá»± > ASCII â†’ space); mode khÃ¡c â†’ `ValueError`|
|`ranking_run_store.py`|`RankingRunStore`: checkpoint SQLite + lock file cho ranking eval; `append` theo stream pháº£i lÃ  **tiá»n tá»‘ liá»n máº¡ch** (trÃ¹ng / lá»— há»•ng â†’ fail atomic), `rows` Ä‘á»c theo keyset, cÃ³ `export`, `timing`, `close`|
|`ranking_stream_summary.py`|`RankingStreamSummary`: cá»™ng dá»“n candidate + scored row thÃ nh metric retrieval / ranking, p50 / p95 latency theo segment, Ä‘áº¿m health vÃ  error|
|`stage_progress.py`|`StageProgress`: in tiáº¿n Ä‘á»™ `committed/total`, rate vÃ  ETA cho cÃ¡c vÃ²ng cháº¡y dÃ i|

## 28.2. Candidate recall â€” `scripts/evaluation/candidate_recall.py`

Vá»›i má»—i user máº«u, má»—i nguá»“n candidate (`popularity`, `item_cf`, `semantic`, `union`) tráº£ N item; loáº¡i item user Ä‘Ã£ cÃ³; Ä‘áº¿m bao nhiÃªu item held-out xuáº¥t hiá»‡n. CÃ¢u query cá»§a `semantic` Ä‘Æ°á»£c mÃ´ phá»ng báº±ng `history` (title item gáº§n nháº¥t â€” trung thá»±c nhÆ°ng rá»—ng vá»›i cold user) hoáº·c `category_oracle` (category cá»§a item held-out â€” **cáº­n trÃªn, khÃ´ng bÃ¡o cÃ¡o nhÆ° káº¿t quáº£ tháº­t**).

## 28.3. Agent eval â€” `package/evaluation/` (+ `requests/`)

Dá»±ng request giáº£ láº­p tá»« dá»¯ liá»‡u held-out (offline khÃ´ng cÃ³ query log tháº­t), gá»­i **cÃ¹ng táº­p request** cho tá»«ng agent, cháº¥m Ä‘iá»ƒm.

|File|Viá»‡c|
|---|---|
|`_schema.py`|`AGENTS`, `PLANNER_AGENTS`, `KIND_SEGMENTS`, `KINDS`, `ORACLE_KINDS`, `REFERENCE_PLANS` (nhÃ³m tool má»™t plan tá»‘t Ä‘i qua theo tá»«ng kind), `INFERENCE_AGENTS` (agent cÃ³ cÃ¢u tráº£ lá»i: type1, planner, planner_memory), `ANSWER_STATUSES` (láº·p láº¡i cá»§a `inference._schema.STATUSES`, cÃ³ test giá»¯ báº±ng nhau); `TEMPLATES` (cÃ¢u request) Ä‘Ã£ chuyá»ƒn sang `agents/_schema.py`; sau refactor `evaluation` Ä‘Æ°á»£c phÃ©p import `inference` nÃªn báº£n láº·p `ANSWER_STATUSES` cÃ³ thá»ƒ bá»|
|`requests/_dataclass.py`|`AgentRequest` (kind, segment, text, user, seed, targets, price_max, category, `oracle`); cÃ³ `to_dict()`|
|`requests/build_requests.py`|sinh request theo seed cá»§a `rng`; `constrained` láº¥y giÃ¡/category tá»« item held-out; `requests/filter_requests_by_scope.py` chá»n `realistic` hay `oracle` theo scope|
|`requests/reference_groups.py`|`reference_groups(kind, available_tools)`: cÃ¡c nhÃ³m tool cá»§a plan tham chiáº¿u (`REFERENCE_PLANS`) cÃ²n láº¡i sau khi lá»c theo tool agent cÃ³; dÃ¹ng trong `score_trajectory` cho `tool_selection_ok`|
|`agents/results/extract_recommendations.py`|"ngÆ°á»i dÃ¹ng thá»±c sá»± tháº¥y gÃ¬": Æ°u tiÃªn `ranked` cá»§a `RecoModelTool` > retrieval > `QueryTool`|
|`score_trajectory.py` (nay á»Ÿ gá»‘c `package/evaluation/`, ghÃ©p 5 lá»›p `score_layer1â€¦5`)|cháº¥m má»™t trajectory: metric xáº¿p háº¡ng, `tool_selection_ok`, `constraint_satisfaction`, `invented_ids`, `asked_clarification`, `task_success`, token/latency. Lá»—i tÃ­nh lÃ  0 chá»© khÃ´ng bá» máº«u; thÃªm cá»™t cÃ¢u tráº£ lá»i `answer_status_<status>`, `answer_grounded`, `answer_fallback`, `inference_{attempts,prompt_tokens,completion_tokens,latency_seconds}` (None khi trajectory khÃ´ng cÃ³ answer: baseline hoáº·c báº£n ghi cÅ©)|
|`summarize.py` (nay á»Ÿ gá»‘c `package/evaluation/`)|gá»™p theo agent â†’ kind â†’ segment (`all` = má»i segment)|
|`requests/_helper.py`|tra corpus: giÃ¡, category sÃ¢u nháº¥t, `items_satisfying`, `items_without_price`|

**5 lá»›p scoring (`layer1_outcome/` â€¦ `layer5_deployment/`)** â€” `score_trajectory` gá»i tá»«ng lá»›p rá»“i ghÃ©p thÃ nh má»™t hÃ ng pháº³ng:

|File|Viá»‡c|
|---|---|
|`layer1_outcome/layer1_outcome.py`|`score_layer1_outcome(request, trajectory, *, item2id, k, seen_item_ids)` â€” metric xáº¿p háº¡ng trÃªn `recommended` so vá»›i `targets`|
|`layer2_interaction/layer2_interaction.py`|`score_layer2_interaction(request, trajectory, *, corpus)` â€” `task_success` (v2: `plan_valid` âˆ§ `steps_ok` âˆ§ cÃ³ item âˆ§ thoáº£ rÃ ng buá»™c; `ambiguous` = há»i láº¡i), `constraint_satisfaction`|
|`layer3_grounding/layer3_grounding.py`|`score_layer3_grounding(trajectory)` â€” `answer_status_*`, `answer_grounded`, `answer_fallback` (None khi trajectory khÃ´ng cÃ³ answer)|
|`layer4_process/layer4_process.py`|`score_layer4_process(request, trajectory)` â€” `plan_valid`, `plan_attempts`, `plan_truncated`, `n_steps`, `steps_ok_rate`, `invented_ids`, `reflections`, `tool_selection_ok` (qua `_helper.check_tool_selection`)|
|`layer5_deployment/layer5_deployment.py`|`score_layer5_deployment(trajectory)` â€” token, `llm_latency_seconds`, `tool_latency_seconds`, `wall_seconds`, `inference_*`|
|`layer*/_schema.py`|háº±ng tÃªn cá»™t cá»§a tá»«ng lá»›p|

**Component benchmark â€” `package/evaluation/component/`** (Ä‘o tá»«ng component tÃ¡ch rá»i, khÃ´ng cáº§n LLM tháº­t / dá»¯ liá»‡u tháº­t):

|File|Viá»‡c|
|---|---|
|`_evaluator.py`|`ComponentEvaluator`: subclass cÃ i `run_component` / `score_component`; `run_case`, `run_benchmark(cases, runs, component_name, git_sha)`|
|`_schema.py`|`BenchmarkCase`, `BenchmarkResult`, `BenchmarkSummary`, `RegressionReport` (+ `to_dict` / `from_dict`)|
|`_loader.py`|`load_cases`, `save_cases`, `filter_cases_by_tag`, `filter_cases_by_metadata` (JSON / JSONL)|
|`_regression.py`|`compare_benchmarks` (ngÆ°á»¡ng 5% metric / 10% latency), `format_regression_report`|
|`run.py`, `run_all.py`|CLI cháº¡y má»™t benchmark / cháº¡y táº¥t cáº£ rá»“i gá»™p `unified_report` (`.json` + `.md`)|
|`link_e2e.py`|`link_component_to_e2e`, `create_traceback_tool` â€” ná»‘i Ä‘iá»ƒm component vá»›i lá»—i trajectory end-to-end|
|`benchmarks/planner_benchmark.py`, `planner_mock_llm.py`, `planner_mock_tools.py`|`PlannerBenchmark` trÃªn LLM + tool giáº£: chá»n tool, arg, schema, ref `$N.path`, rÃ ng buá»™c|
|`benchmarks/executor_benchmark.py`, `executor_mock_tools.py`|`ExecutorBenchmark` (executor + reflection) trÃªn tool giáº£ Ä‘iá»u khiá»ƒn Ä‘Æ°á»£c (fail / timeout / rá»—ng / sai schema)|
|`benchmarks/grounding_benchmark.py`|`GroundingBenchmark` â€” cháº¥m claim-level báº±ng Jev (`jev_product_evaluator`)|
|`benchmarks/integration_benchmark.py`|`IntegrationBenchmark` â€” kiá»ƒm ranh giá»›i giá»¯a cÃ¡c component|
|`benchmarks/memory_correctness_evaluator.py`, `memory_oracle.py`, `memory_correctness_setup.py`, `build_memory_correctness_dataset.py`|`MemoryCorrectnessEvaluator` cháº¥m theo **oracle Ä‘á»™c láº­p** (`compute_memory_oracle`, `leakage_probe`; oracle **khÃ´ng** import `MemoryTool`/`ItemCorpus`); script sinh dataset vÃ  `--check` phÃ¡t hiá»‡n lá»‡ch|
|`benchmarks/memory_utility.py`|phÃ¢n tÃ­ch **utility** ghÃ©p cáº·p nhiá»u run `planner` vs `planner_memory` (khÃ´ng gá»i LLM; nhÃ³m chá»‰ 1 run â†’ khÃ´ng káº¿t luáº­n)|
|`benchmarks/*.jsonl`|dataset: `planner`, `executor`, `grounding`, `integration`, `memory_correctness` (+ `dummy_memory_dataset.jsonl`)|
|`README.md`, `benchmarks/planner_README.md`|cÃ¡ch cháº¡y benchmark component|

**Cháº©n Ä‘oÃ¡n & judge:**

|File|Viá»‡c|
|---|---|
|`diagnostics/failure_rates.py`|`failure_rates(rows)` â€” tá»‰ lá»‡ lá»—i theo agent Ã— kind (gá»“m `answer_status_tool_error_rate`)|
|`diagnostics/error_taxonomy.py`|`error_taxonomy(trajectories)` â€” phÃ¢n loáº¡i lá»—i step / plan theo agent Ã— kind|
|`diagnostics/reflection_diagnostics.py`|`reflection_diagnostics(rows)` â€” hÃ nh vi reflection (láº§n Ä‘áº§u lá»—i, sá»‘ lÆ°á»£t, â€¦)|
|`judge/jev_client.py`|`JevClient` (TypeSafe AI): `evaluate`, `evaluate_noul`, `evaluate_choice`, `evaluate_score`|
|`jev_product_evaluator.py`|`evaluate_product_reply_with_jev(...)` â€” faithfulness (claim â†’ Noul) + communication (Score theo rubric); Ä‘á»c `configs/eval/judge.yaml`|
|`product_reply_evaluator.py`|`evaluate_product_reply(...)` â€” báº£n khÃ´ng cáº§n Jev|
|`build_run_provenance.py`|`build_run_provenance(planner_tools, memory_tools)` â€” hash prompt / tool schema / git state / limits cá»§a má»™t láº§n cháº¡y|

|Kind|Dá»±ng tá»«|Ghi chÃº|
|---|---|---|
|`similar`|item gáº§n nháº¥t trong history|trung thá»±c|
|`personalized`|chá»‰ history|trung thá»±c; cÃ´ láº­p tÃ¡c dá»¥ng cá»§a `MemoryTool`|
|`constrained`|category + giÃ¡ cá»§a item held-out|**ORACLE** (cáº­n trÃªn)|
|`cold_text`|category cá»§a item held-out|**ORACLE**|
|`ambiguous`|cÃ¢u mÆ¡ há»“ ("CÃ³ gÃ¬ má»›i khÃ´ng?")|thÃ nh cÃ´ng = agent **há»i láº¡i** thay vÃ¬ bá»‹a id|
||`exclusion`|exclude categories + items|trung thá»±c; kiá»ƒm tra kháº£ nÄƒng lá»c|
||`unanswerable`|query báº¥t kháº£ thi|trung thá»±c; kiá»ƒm tra xá»­ lÃ½ trÆ°á»ng há»£p null|

Bá»‘n agent so sÃ¡nh: `baseline` (ItemKNN, khÃ´ng LLM), `type1` (plan cá»‘ Ä‘á»‹nh, chá»‰ cho `similar`), `planner` (LLM + 4 tool), `planner_memory` (planner + `MemoryTool`).

**Plan-reflect trong eval:** trajectory cá»§a planner cÃ³ thÃªm `reflections` (sá»‘ lÆ°á»£t reflect), `first_attempt_ok` (láº§n cháº¡y Ä‘áº§u khÃ´ng lá»—i step vÃ  ra item hoáº·c há»i láº¡i) vÃ  `reflect_rounds` (giÃ¡ trá»‹ lÃºc cháº¡y; `--resume` chá»‰ dÃ¹ng láº¡i trajectory cÃ¹ng `reflect_rounds`). `steps` trong trajectory lÃ  cá»§a láº§n cháº¡y **cuá»‘i**, vÃ  `task_success` cháº¥m trÃªn káº¿t quáº£ cuá»‘i. Cá» `--reflect-rounds` ghi Ä‘Ã¨ `agent.reflect_rounds`. Script phÃ¢n tÃ­ch lá»—i theo tool `analyze_agent_failures.py` cÃ³ á»Ÿ báº£n 12/10 nhÆ°ng **khÃ´ng cÃ³ trong zip 17/10** (má»¥c 11.1).

**CÃ¢u tráº£ lá»i (Inference) trong eval:** `--inference-mode` (máº·c Ä‘á»‹nh láº¥y tá»« `inference.mode`) quyáº¿t Ä‘á»‹nh `llm` (LLM viáº¿t, kiá»ƒm grounding, lá»—i thÃ¬ dÃ¹ng template; tá»‘i Ä‘a `1 + llm_retries` láº§n gá»i thÃªm cho má»—i request Ä‘Æ°á»£c tráº£ lá»i) hay `template` (táº¥t Ä‘á»‹nh, khÃ´ng gá»i LLM). Trajectory cÃ³ thÃªm `answer`, `answer_status`, `answer_grounded`, `answer_composer`, `answer_fallback`, `answer_reason`, `inference_usage`, `inference_mode`; `inference_usage` tÃ¡ch riÃªng vá»›i `usage` cá»§a planner. Báº£n ghi cÅ© khÃ´ng cÃ³ cÃ¡c trÆ°á»ng nÃ y váº«n Ä‘Æ°á»£c dÃ¹ng láº¡i khi `--resume` (cá»™t answer Ä‘á»ƒ trá»‘ng).

## 28.4. So sÃ¡nh nhiá»u láº§n cháº¡y (ablation) â€” `package/evaluation/ablation/`

**Vai trÃ²:** so sÃ¡nh cÃ¡c thÃ­ nghiá»‡m `agent_eval` (`exp_NNN`) theo "nhÃ³m cáº¥u hÃ¬nh" (vÃ­ dá»¥ `reflect_rounds` 0 vÃ  1, má»—i nhÃ³m nhiá»u láº§n láº·p): Ä‘á»c `scored.jsonl` vÃ  `config.yaml` cá»§a tá»«ng exp, ghÃ©p cáº·p theo `request_id`, kiá»ƒm tÆ°Æ¡ng thÃ­ch config, trung bÃ¬nh qua cÃ¡c láº§n láº·p trong nhÃ³m, rá»“i bÃ¡o chÃªnh lá»‡ch theo kind Ã— segment Ã— metric kÃ¨m khoáº£ng tin cáº­y; metric nhá»‹ phÃ¢n cÃ³ thÃªm McNemar. Config: `agent/ablation.yaml` (nay **Ä‘Ã£ khai bÃ¡o** `groups` tháº­t: `reflect_0: [exp_012]`, `reflect_1: [exp_013]`, `infer_template: [exp_011]`; 6 `contrasts`; `output_subdir: agent_eval/ablation`). Script: `scripts/experiments/compare_experiments.py`. `docs/ablation_protocol.md` **khÃ´ng tá»“n táº¡i** trong repo vÃ  khÃ´ng cÃ²n chá»— nÃ o trÃ­ch tá»›i (má»¥c 16).

|File|Viá»‡c|
|---|---|
|`_limits.py`|`AblationLimits` tá»« `agent/ablation.yaml`|
|`_loader.py`|`load_scored_data`, `load_config_data`, `load_group_data`, `validate_contrast_config`, `check_compatibility`|
|`_compare.py`|`pair_by_request_id`, `average_across_runs`, `compute_metric_diff`, `compute_binary_disagreement`, `compare_two_groups`, `find_disagreements`|
|`_statistics.py`|`bootstrap_ci` (khoáº£ng tin cáº­y cho trung bÃ¬nh), `mcnemar_test` (xáº¥p xá»‰ chi-bÃ¬nh-phÆ°Æ¡ng; tráº£ `None` náº¿u sá»‘ cáº·p báº¥t nháº¥t `b + c < 10`; p-value **thÃ´**, chá»‰ láº¥y má»™t trong 4 má»©c 1.0 / 0.05 / 0.01 / 0.001)|
|`_report.py`|`render_markdown_report`, `write_csv`, `write_json`, `write_disagreements` (â†’ `disagreements.jsonl`)|

`compare_experiments.py` nay import Ä‘Ãºng `package.evaluation.ablation` (lá»—i import trÆ°á»›c refactor Ä‘Ã£ háº¿t; `test_import_resolution.py` cháº·n lá»—i loáº¡i nÃ y). `_compare.py` Ä‘Ã£ dÃ¹ng `kind_key` á»Ÿ nhÃ¡nh ghi káº¿t quáº£ McNemar; lá»—i `king_key` cá»§a báº£n 17/10 Ä‘Ã£ háº¿t (xÃ¡c nháº­n trong snapshot 20/10).

---

# 29. Scripts â€” `scripts/`

Script cháº¡y trá»±c tiáº¿p tá»« gá»‘c `src/`: `PYTHONPATH=. python scripts/<thÆ° má»¥c>/<tÃªn>.py [tham sá»‘]`. Chi tiáº¿t lá»‡nh: `--help` cá»§a tá»«ng script vÃ  `scripts/README.md` (mÃ´ táº£ bá»‘ cá»¥c 7 thÆ° má»¥c; khÃ´ng nháº¯c biáº¿n mÃ´i trÆ°á»ng `LLM_API_KEY` / `LLM_BASE_URL`).

## 29.1. Tá»«ng thÆ° má»¥c

| ThÆ° má»¥c           | File                          | Viá»‡c                                                                                                                                                                                                                                                                                                             | DÃ¹ng chÃ­nh                                                                                           |
| ----------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `data_pipeline/`  | `stage1_clean_domain.py`      | stage 1                                                                                                                                                                                                                                                                                                          | `data.clean`, SQLite dedupe, pyarrow                                                                 |
|                   | `stage2_merge_filter.py`      | stage 2                                                                                                                                                                                                                                                                                                          | `data.domain`, `data.filter`                                                                         |
|                   | `stage3_map_split.py`         | stage 3                                                                                                                                                                                                                                                                                                          | `data.mapping`, `data.split`, `data.leakage`                                                         |
| `eda_diagnostic/` | `run_eda.py`                  | EDA streaming trÃªn review thÃ´                                                                                                                                                                                                                                                                                    | `data.eda`                                                                                           |
|                   | `diagnose_splits.py`          | cháº©n Ä‘oÃ¡n split (má»¥c 4.1): `--tag`, `--out`; báº£n 29/10 in **riÃªng** máº«u sá»‘ theo event / pair / user (`print_diagnosis_report`) vÃ  khÃ´ng cÃ²n coi `*_reachable_pct` lÃ  tráº§n macro Recall@K                                                                                                                             | `data.eda.diagnose_splits`, `data.split`, `data.mapping`                                             |
| `evaluation/`     | `run_baselines.py`            | cháº¡y random/popularity/item_knn/bpr_mf, ghi `exp_NNN` trá»±c tiáº¿p trong `experiments/`                                                                                                                                                                                                                             | há» matrix-based + `tools/evaluation`                                                                 |
|                   | `tune_baselines.py`           | tune chá»‰ báº±ng validation; `--run-final-test` refit train+val vÃ  Ä‘o test má»™t láº§n                                                                                                                                                                                                                                  | há» matrix-based                                                                                      |
|                   | `candidate_recall.py`         | má»¥c 10.2; ghi vÃ o `<experiments_dir>/<candidate_recall.experiments_subdir>`                                                                                                                                                                                                                                      | `ItemCFTool`, `SemanticSearchTool`, `ItemCorpus`                                                     |
|                   | `run_agent_eval.py`           | má»¥c 10.3: so sÃ¡nh baseline / type1 / planner / planner_memory; `--resume` (trajectory ghi dáº§n), `--reflect-rounds` (ghi Ä‘Ã¨ `agent.reflect_rounds`), `--inference-mode` (llm hoáº·c template; ghi Ä‘Ã¨ `inference.mode`), `--eval-on test` má»›i Ä‘á»¥ng test; ghi vÃ o `<experiments_dir>/<agent_eval.experiments_subdir>` | `evaluation` (5 layer + `requests/`), `inference`                                                                      |
|                   | `benchmark_categories_any.py` | Ä‘o `SemanticSearchTool` + `categories_any` **cÃ³ / khÃ´ng cÃ³** index `idx_cat_item_cat` (dá»±ng corpus tá»« `meta_*.jsonl.gz`, in `EXPLAIN QUERY PLAN` vÃ  thá»i gian); `--tag`, `--queries-file` (JSONL), `--iterations`, `--limit`                                                                                     | corpus + `SemanticSearchTool`                                                                        |
|                   | `analyze_ranking_bottlenecks.py` | Ä‘á»c candidate / score Ä‘Ã£ lÆ°u: máº¥t mÃ¡t do retrieval, headroom cá»§a ranking, fusion nguá»“n; **khÃ´ng** fit model, **khÃ´ng** load corpus, **khÃ´ng** gá»i LLM (dÃ¹ng target chá»‰ Ä‘á»ƒ cháº©n Ä‘oÃ¡n)                                                                                                                            | `tools/evaluation` (metric), artifact ranking                                                                 |
|                   | `evaluate_product_reply.py`   | cháº¥m cÃ¢u tráº£ lá»i cuá»‘i theo 2 trá»¥c faithfulness + communication (`product_reply_evaluator`); `--input-file` JSONL hoáº·c `--request` + `--items-file` + `--answer`                                                                                                                                                    | `evaluation/product_reply_evaluator`                                                                 |
|                   | `evaluate_with_jev.py`        | nhÆ° trÃªn nhÆ°ng dÃ¹ng Jev (TypeSafe AI) lÃ m judge (`jev_product_evaluator`, `configs/eval/judge.yaml`)                                                                                                                                                                                                              | `evaluation/judge`, `evaluation/jev_product_evaluator`                                                |
| `experiments/`    | `compare_experiments.py`      | so sÃ¡nh cÃ¡c `exp_NNN` theo `agent/ablation.yaml` (`--config`) â†’ bÃ¡o cÃ¡o markdown / CSV / JSON (má»¥c 10.4; `docs/ablation_protocol.md`). Import Ä‘Ã£ Ä‘Ãºng sau refactor                                                                                                                                               | `evaluation/ablation`                                                                                |
| `tools/`          | `run_tools.py`                | cháº¡y má»i tool trÃªn dá»¯ liá»‡u tháº­t (`--model` knn hoáº·c popularity, `--neighbors`, `--eval-users`, `--negatives`); ghi `<log_dir>/run_tools.log` (log kiá»ƒm tool, khÃ´ng pháº£i káº¿t quáº£ thÃ­ nghiá»‡m)                                                                                                                      | corpus + há» DataFrame-based + `BaselineScorer`; **lÃ  nÆ¡i duy nháº¥t cháº¡y `SQLTool` trÃªn dá»¯ liá»‡u tháº­t** |
|                   | `check_llm_provider.py`       | gá»i thá»­ LLM tháº­t (`health_check` + má»™t request JSON)                                                                                                                                                                                                                                                             | `api/`                                                                                               |
| `llm_agent/`      | `smoke_real_llm.py`           | `PlanExecutor` + 5 tool trÃªn fixture synthetic, LLM tháº­t                                                                                                                                                                                                                                                         | `api/`, `agents/`                                                                                    |
| `demo/`           | `run_demo.py`                 | Gradio UI: `--mock` (khÃ´ng cáº§n dá»¯ liá»‡u / LLM / máº¡ng) hoáº·c backend tháº­t vá»›i `--tag`, `--domain`, `--eval-on`, `--host`, `--port`; cáº§n `pip install gradio`                                                                                                                                                        | `package/demo`                                                                                       |
|                   | `demo_full_agent.py`          | `build_tools()` / `build_executor()` **báº£n cÅ©** (5 tool, khÃ´ng cÃ³ `SQLTool`, khÃ´ng qua `AgentTools`); agent tháº­t dÃ¹ng `package/agents/toolkit/build_tools.py`. KhÃ´ng cháº¡y trá»±c tiáº¿p; chÆ°a quyáº¿t Ä‘á»‹nh xoÃ¡                                                                                                         | â€”                                                                                                    |

`analyze_agent_failures.py` (cÃ³ á»Ÿ báº£n 12/10) **khÃ´ng cÃ³ trong snapshot 17/10**: hiá»‡n chÆ°a cÃ³ script phÃ¢n tÃ­ch lá»—i step theo tool.

## 29.2. Thá»© tá»± cháº¡y

KhÃ´ng cÃ²n `sh/`: nhá»¯ng viá»‡c `_common.sh` tá»«ng lÃ m (Ä‘á»c `TAG`, láº·p qua domain, bá» qua stage Ä‘Ã£ cÃ³ output) **khÃ´ng tá»± Ä‘á»™ng**; dÃ¹ng tham sá»‘ cá»§a tá»«ng script: `data_pipeline/stage1_clean_domain.py` (`--domain`, `--review-path`, `--output-dir`, `--chunk-size`, `--force`) â†’ `stage2_merge_filter.py` (`--domain`, `--tag`, `--force`, `--cold-start-report`) â†’ `stage3_map_split.py` (`--tag`, `--force`) â†’ (tuá»³ chá»n) `eda_diagnostic/diagnose_splits.py --tag <tag>`. `evaluation/run_baselines.py`, `evaluation/candidate_recall.py`, `tools/run_tools.py` nháº­n `--tag`; `eda_diagnostic/run_eda.py` nháº­n `--domain` / `--path`. Script táº£i review/meta (`download_review_data.sh`) vÃ  `download.yaml` khÃ´ng cÃ²n trong repo: dá»¯ liá»‡u thÃ´ pháº£i Ä‘Æ°á»£c Ä‘áº·t sáºµn vÃ o `resource/raw/`.

---

# 30. Tests â€” `tests/`

Cháº¡y: `PYTHONPATH=. pytest tests -q`, hoáº·c `tests/run_all_tests.sh` (cÅ©ng cÃ³ `.bat`); má»—i thÆ° má»¥c con (`agents/`, `config/`, `data/`, `tools/`â€¦) cÃ³ `run_tests.sh` / `.bat` riÃªng; `tests/README.md` mÃ´ táº£ bá»‘ cá»¥c. **Snapshot 17/10 sau refactor (`src_e44a83.zip`), `pytest tests`: 952 pass, 1 Ä‘á», 1 skip** (trÆ°á»›c refactor, `src_1.zip`: 925 pass / 15 Ä‘á»). Sá»‘ test thu tháº­p theo thÆ° má»¥c: agents 115, config 37, data 62, demo 17, evaluation 72, tools 649, cá»™ng `test_package_import.py`. **1 test Ä‘á»:** `tests/demo/test_live_backend.py::test_live_backend_get_sample_users` cáº§n dá»¯ liá»‡u tháº­t `resource/splits/multi_domain/train.parquet` (Ä‘á» khi khÃ´ng cÃ³ dá»¯ liá»‡u, khÃ´ng pháº£i lá»—i code). **Log test:** `tests/README.md` ghi `experiments/test_logs/`, nhÆ°ng `run_all_tests.sh` vÃ  `results_report.py` (`DEFAULT_RESULTS_DIR`) váº«n ghi `tests/logs/`; zip Ä‘Ã£ chuyá»ƒn tay cÃ¡c file cÅ© sang `experiments/test_logs/`; `test_data_paths.py` kháº³ng Ä‘á»‹nh `tests/logs` **khÃ´ng** náº±m trong cáº¥u hÃ¬nh Ä‘Æ°á»ng dáº«n. (Báº£n 12/10: 796 test / 792 pass / 4 Ä‘á» trÃªn má»™t zip khÃ¡c.)

**31/10/2026 â€” Ä‘Ã£ cháº¡y láº¡i `pytest tests -q`** (sau khi sá»­a `package/__init__.py`, má»¥c 16, vÃ  sá»­a import `memory_tool.py`): **1212 test thu tháº­p Ä‘Æ°á»£c â†’ 1198 passed, 10 failed, 2 skipped, 2 xfailed.** Cháº¡y chia lÃ´ theo thÆ° má»¥c vÃ¬ giá»›i háº¡n thá»i gian cá»§a shell; `pytest tests --collect-only -q` xÃ¡c nháº­n tá»•ng 1212. 10 test Ä‘á» (**chÆ°a Ä‘iá»u tra nguyÃªn nhÃ¢n**): `config/test_data_paths.py::test_data_paths_layout_is_under_resource`, `config/test_data_paths.py::test_config_cli_resolves_paths_from_datapaths_for_shell_scripts`, `config/test_package_layout.py::test_every_public_module_has_one_public_symbol_named_after_the_file`, `config/test_package_layout.py::test_public_names_are_unique_across_the_package`, `config/test_path_hygiene.py::test_no_hardcoded_project_dirs_in_code`, `evaluation/ablation/test_loader.py::test_comparison_rejects_policy_and_protocol_mixing`, `evaluation/agent/test_behavior_snapshot.py::test_behavior_snapshot_matches_existing`, `evaluation/agent/test_eval_integration.py::{test_run_planner_adds_the_answer_without_touching_the_recommendation_or_planner_usage, test_end_to_end_scenario[llm]}`. **Test privacy `test_no_module_imports_a_private_module_of_another_folder` giá» pass** (memory_tool.py khÃ´ng cÃ²n import cross-folder private). `tests/demo` 46 passed â€” khÃ´ng cÃ³ test nÃ o Ä‘á» vÃ¬ thiáº¿u `resource/` trong láº§n cháº¡y nÃ y. Sá»‘ **file** test hiá»‡n táº¡i (Ä‘áº¿m `tests/**/test_*.py`): `agents/` 17, `config/` 8, `data/` 16, `demo/` 5, `evaluation/` 13, `tools/` 34, vÃ  1 file á»Ÿ gá»‘c `tests/` (`test_package_import.py`).

|File|Kiá»ƒm gÃ¬|
|---|---|
|`conftest.py`, `tools_helpers.py`, `results_report.py`|fixture dÃ¹ng chung: `corpus` (5 item máº«u), `cf_setup` (interactions + mapping); plugin ghi káº¿t quáº£ tá»«ng test|
|`test_package_import.py`|import `package.*` pháº£i nháº¹ (CLI `python -m package.config` cháº¡y tá»« shell)|
|**`config/`**||
|`test_config_loader.py`|thay biáº¿n mÃ´i trÆ°á»ng, `${VAR:-default}`, thiáº¿u file/biáº¿n, `llm.yaml` khÃ´ng chá»©a credential, CLI `python -m package.config`|
|`test_data_paths.py`|má»i key `data_paths` â†” field `DataPaths`, cÃ¡c thÆ° má»¥c phÃ¢n biá»‡t vÃ  náº±m trong project, `tag` chá»‰ Ä‘á»•i thÆ° má»¥c theo run|
|`test_domain_registry.py`|`namespaced_item_id`, `tag_domain`, `merge_domains` (khÃ´ng Ä‘á»¥ng id, giá»¯ `user_id`), `domain_breakdown`|
|`test_path_hygiene.py`|AST cáº¥m hard-code `resource/â€¦`, `experiments/â€¦`; **code trong `package/` vÃ  `scripts/` khÃ´ng tá»± Ä‘á»c má»¥c `paths` thÃ´ cá»§a `data_paths.yaml`** (pháº£i qua `DataPaths`); khÃ´ng cÃ²n `_config.py`; khÃ´ng cÃ³ secret trong config|
|`test_package_layout.py`|**má»™t file, má»™t symbol**; tÃªn cÃ´ng khai duy nháº¥t toÃ n package; module `_xxx` riÃªng theo thÆ° má»¥c (má»¥c 2.6). **Test privacy giá» pass** cho `memory_tool.py` (Ä‘Ã£ xoÃ¡ khá»i `EXEMPT_FILES`, import dÃ¹ng public API). CÃ²n 1 vi pháº¡m á»Ÿ `layer5_deployment.py` (Ä‘Ã£ exempt).|
|`test_dependency_direction.py`|hÆ°á»›ng phá»¥ thuá»™c giá»¯a `tools`, `agents`, `inference`, `evaluation`, `demo` (má»¥c 2.5); danh sÃ¡ch ngoáº¡i lá»‡ pháº£i cÃ²n Ä‘Æ°á»£c dÃ¹ng|
|`test_import_resolution.py`|má»i `package.*` import trong `package/`, `scripts/`, `tests/` trá» tá»›i file tá»“n táº¡i|
|`test_tool_limits.py`|giá»›i háº¡n láº¥y tá»« `tools.yaml`, `check_top_k`, giÃ¡ trá»‹ sai bá»‹ tá»« chá»‘i|
|**`data/`**||
|`test_clean.py`, `test_mapping.py`, `test_temporal_split.py`, `test_load_splits.py`, `test_split_paths.py`, `test_load_item_metadata.py`|cÃ¡c hÃ m tÆ°Æ¡ng á»©ng trong `package/data`|
|`test_leakage_check.py`|**cáº£ hai chiá»u**: pass khi há»£p lá»‡, raise khi vi pháº¡m|
|`test_eda.py`, `test_streaming_eda.py`, `test_metadata_eda.py`|cÃ¡c hÃ m EDA (ká»ƒ cáº£ `segment_users`, `compute_metadata_stats`)|
|`test_eval_helpers.py`|`select_fit_target`, `segment_users_by_history`, `build_corpus` (Ä‘á»™ phá»§ quÃ¡ tháº¥p â†’ lá»—i), `parameter_grid`|
|`test_diagnose_splits.py`|`diagnose_splits` / `SplitDiagnosis` (cÃ¡c chá»‰ sá»‘ item Ä‘Ã£ tháº¥y, cáº·p láº·p, `reachable`, tá»‰ lá»‡ domain â€¦)|
|**`agents/`**||
|`test_plan_executor.py`|retry JSON sai, cáº¯t `max_steps`, id bá»‹a khÃ´ng cháº¡y tool, ref `$N`, `ask_user`, arg sai chá»— cÃ³ gá»£i Ã½, má»i tool tá»± mÃ´ táº£|
|`test_plan_reflect.py`|plan-reflect: sá»­a plan khi step lá»—i / khÃ´ng ra item, giá»›i háº¡n `reflect_rounds`, khÃ´ng reflect khi id bá»‹a hoáº·c timeout SQL, reply reflect há»ng bá»‹ bá», `last_reflections` / `last_first_attempt_ok`|
|`test_memory_tool.py`|`MemoryTool`: user 300 interaction, user láº¡, 0 interaction, giÃ¡ toÃ n NULL, dÃ¹ng lÃ m ref trong plan|
|`test_llm_provider.py`|factory + provider (HTTP bá»‹ fake)|
|`test_phase1_smoke.py`|config â†’ factory â†’ provider end-to-end (fake `urlopen`) vÃ  náº¡p config dá»¯ liá»‡u|
|`test_baselines.py`, `test_item_knn_equivalence.py`|popularity loáº¡i item Ä‘Ã£ tháº¥y, ItemKNN, metric macro-average, top_k; hai há» ItemKNN cho cÃ¹ng ma tráº­n similarity|
|`inference/`: `test_limits.py`, `test_adapters.py`, `test_compose.py`|`package/inference`: validate `inference.yaml`, `outcome_from_*`, `classify_outcome`, template / LLM (grounding, retry, fallback)|
|`fakes/` (thÆ° viá»‡n, khÃ´ng pháº£i test): `fake_tools.py`, `sample_data.py`, `scripted_llm.py`|tool giáº£ khá»›p schema tool tháº­t, builder dá»¯ liá»‡u máº«u, `ScriptedLLM` táº¥t Ä‘á»‹nh (khÃ´ng gá»i API)|
|`test_executor_guards.py`, `test_plan_building.py`, `test_reflection_behavior.py`, `test_classify_outcome.py`, `test_inference_behavior.py`, `test_end_to_end.py`, `test_fake_contracts.py`|guard cá»§a `_execute` (tool láº¡, id bá»‹a, arg sai chá»—, ref há»ng, cáº¯t `max_steps`), retry plan JSON, plan-reflect, báº£ng status cá»§a `classify_outcome`, grounding / fallback cá»§a inference, pipeline planner â†’ executor â†’ outcome â†’ compose, há»£p Ä‘á»“ng fake tool â†” tool tháº­t|
|**`demo/`**||
|`test_demo_config.py`, `test_demo_backend.py`, `test_inference_adapter.py`, `test_live_backend.py`, `test_gradio_ui.py`|`demo.yaml`, `MockBackend`, adapter (`adapt_from_inference` â€¦), `LiveBackend`, giao diá»‡n Gradio. `test_live_backend_get_sample_users` cáº§n dá»¯ liá»‡u tháº­t|
|**`evaluation/`**||
|`agent/`: `test_agent_eval.py`, `test_eval_integration.py`|`build_requests`, `extract_recommendations`, `score_trajectory`, `summarize`, cá»™t reflect trong trajectory/summary, `--resume` theo `reflect_rounds`. náº¡p `scripts/evaluation/run_agent_eval.py` (Ä‘Æ°á»ng dáº«n Ä‘Ã£ sá»­a sau refactor) `test_eval_integration.py`: tÃ­ch há»£p `run_agent_eval` vá»›i `inference` (`--inference-mode`, cá»™t answer, `--resume`; dÃ¹ng chung loader `_load_run_agent_eval` cá»§a `test_agent_eval.py`)|
|`ablation/`: `test_limits.py`, `test_loader.py`, `test_compare.py`, `test_statistics.py`, `test_report.py`, `test_integration.py`|`package/evaluation/ablation`: validate config, náº¡p `scored.jsonl` / `config.yaml`, ghÃ©p cáº·p theo `request_id`, bootstrap CI, McNemar, bÃ¡o cÃ¡o, so sÃ¡nh hai nhÃ³m. (NhÃ¡nh `king_key` á»Ÿ `_compare.py:256` chÆ°a cÃ³ test cháº¡m tá»›i)|
|`component/`: `test_loader.py`, `test_regression.py`, `test_memory_correctness.py`, `test_memory_utility.py`|loader dataset cá»§a component benchmark, so sÃ¡nh hai láº§n cháº¡y (regression), `MemoryCorrectnessEvaluator` Ä‘á»‘i chiáº¿u oracle Ä‘á»™c láº­p + phÃ¡t hiá»‡n leakage cÃ i vÃ o, phÃ¢n tÃ­ch memory utility ghÃ©p cáº·p nhiá»u run|
|`agent/` (má»›i 29/10): `test_behavior_snapshot.py` (+ `behavior_snapshot.json`)|khoÃ¡ hÃ nh vi cháº¥m Ä‘iá»ƒm trÆ°á»›c / sau refactor 5 lá»›p: so `score_trajectory` vá»›i snapshot Ä‘Ã£ lÆ°u|
|**`tools/`** (má»—i module má»™t thÆ° má»¥c con; fixture "tiny world" trong `tools/conftest.py`, giÃ¡ trá»‹ mong Ä‘á»£i tÃ­nh tay)||
|`base/`: `test_tool_call_logger.py`, `test_validation.py`|há»£p Ä‘á»“ng log cá»§a má»i tool (field, `input_hash` á»•n Ä‘á»‹nh, JSONL); `validate_list_like` / `validate_int`â€¦|
|`corpus/`: `test_contract_corpus.py`, `test_corpus_regressions.py`|`ItemCorpus`: namespace id, giÃ¡/NULL, id trÃ¹ng, báº¯t buá»™c domain, categories, cá»™t sá»‘, chá»‰ Ä‘á»c (authorizer cháº·n ghi), `item_domains` chia chunk, `from_parquet`; **`SCHEMA_HINT` chá»‰ nÃªu báº£ng/cá»™t cÃ³ tháº­t** (so vá»›i `SELECT â€¦ LIMIT 0` vÃ  `sqlite_master`, vÃ¬ `PRAGMA` bá»‹ cháº·n; khÃ´ng so kiá»ƒu cá»™t)|
|`sql_query/`: `test_contract_sql_query.py`, `test_sql_filter_semantics.py`, `test_sql_filter_validation.py`, `test_query_tool_regressions.py`, `test_sql_hardening.py`|`SQLTool` / `QueryTool` / `compile_filters`: filter giÃ¡, categories any/all, domain, key láº¡ bá»‹ tá»« chá»‘i, wildcard `LIKE` lÃ  literal, kiá»ƒu sai bá»‹ tá»« chá»‘i rÃµ rÃ ng, `total_matches`/`truncated`, tráº§n `max_rows`, timeout, SQL nhiá»u cÃ¢u / ghi bá»‹ cháº·n|
|`retrieval/`: `test_contract_retrieval.py`, `test_semantic_search_regressions.py`|`SemanticSearchTool` (lexical FTS5/BM25): tokenizer (giá»¯ `usb-c`), match tá»‘t nháº¥t trÆ°á»›c, filter, output Ä‘Æ°a Ä‘Æ°á»£c sang tool khÃ¡c, khÃ´ng match â†’ rá»—ng, khÃ´ng inject FTS, limit, **truy váº¥n Ä‘áº¿m háº¿t giá» â†’ `total_matches=None` váº«n cÃ³ candidates; truy váº¥n chÃ­nh háº¿t giá» â†’ `ok=False`**|
|`ranking/`: `test_item_cf_tool.py`, `test_reco_model_tool.py`, `test_ranking_hardening.py`, `test_contract_ranking_extras.py`|`ItemCFTool` (cá»™ng nhiá»u seed, `unknown_items`, validate), `RecoModelTool` (loáº¡i/giá»¯ item Ä‘Ã£ tháº¥y, nháº­n output tool khÃ¡c, `unscored_item_ids`, `has_personal_signal`, cold start, note khi má»i á»©ng viÃªn Ä‘Ã£ xem) vÃ  há»£p Ä‘á»“ng scorer|
|`score/`: `test_contract_baseline_scorer.py`, `test_baseline_scorer_validation.py`|`BaselineScorer`: cÃ´ng thá»©c, tie-break, user láº¡, validate|
|`recommenders/`: `test_base_recommender.py`, `test_contract_recommenders.py`|`Recommender` base, cáº£ hai há» API, factory, fallback, negative sampling cá»§a BPR|
|`evaluation/`: `test_contract_evaluation.py`, `test_evaluator.py`|metric, `evaluate_recommender`, `EvaluationResult`, phÃ¢n Ä‘oáº¡n user|
|`utilities/`: `test_contract_utilities.py`|`merge_model_params`, `hardware_info`, `select_fit_target`, `parameter_grid`, lÆ°u experiment|
|`integration/`: `test_tools_integration.py`|cÃ¡c module khá»›p nhau á»Ÿ ranh giá»›i (tiny world)|
|`corpus/` (má»›i 29/10): `test_metadata_policy.py`|policy metadata Ã©p **á»Ÿ táº§ng SQL**: mask `price` / `average_rating` / `rating_number`, khÃ´ng cÃ³ Ä‘Æ°á»ng vÃ²ng SQL, policy chá»‘t má»™t láº§n (má»¥c 5)|
|`evaluation/` (má»›i 29/10): `test_protocol.py`, `test_query_normalization.py`, `test_ranking_bottlenecks.py`, `test_ranking_checkpoint.py`, `test_ranking_streaming.py`|`evaluation_protocol` (máº«u sá»‘, cutoff), `ascii_fold`, replay bottleneck, checkpoint / resume / export cá»§a ranking eval â€” cháº¡y end-to-end vá»›i tool tháº­t, khÃ´ng cáº§n LLM|

KhÃ´ng cÃ³ file test riÃªng cho `agents/_limits.py` (chá»‰ Ä‘Æ°á»£c dÃ¹ng giÃ¡n tiáº¿p qua `reflect_rounds`).

---

# 31. Pháº§n cÃ²n láº¡i

|NÆ¡i|Tráº¡ng thÃ¡i|
|---|---|
|`demo/`|backend + view model cá»§a demo UI (má»¥c 13.1)|
|`utils/ensure_utf8_stdout.py`|`ensure_utf8_stdout()` (export qua `package.utils`) â€” trÃ¡nh `UnicodeEncodeError` trÃªn Windows khi in tiáº¿ng Viá»‡t|
|`memory/__init__.py`|export `MemoryTool`, `get_memory_limits`, `MemoryLimits` (code á»Ÿ `memory/memory_tool.py`, `memory/limits.py`; má»¥c 6.3)|
|`tools/embeddings/`|**placeholder** (`__init__.py` 3 dÃ²ng, chÆ°a cÃ³ code). Dá»± kiáº¿n: embedding retrieval|

CÃ¡c package `embeddings/`, `features/`, `sequential/` á»Ÿ cáº¥p `package/` Ä‘Ã£ bá»; `api/` (má»¥c 8) vÃ  `inference/` (má»¥c 9.4) Ä‘Ã£ cÃ³ code.

## 31.1. `package/demo/` â€” backend cá»§a demo UI

**Vai trÃ²:** tÃ¡ch "nhá»¯ng gÃ¬ UI hiá»ƒn thá»‹" khá»i agent. `scripts/demo/run_demo.py` dá»±ng giao diá»‡n Gradio trÃªn cÃ¡c lá»›p nÃ y. Config: `agent/demo.yaml`. CÃ¡ch cháº¡y: `--help` cá»§a `scripts/demo/run_demo.py` (`docs/demo.md` mÃ  báº£n cÅ© trÃ­ch **khÃ´ng tá»“n táº¡i**).

|File|Viá»‡c|
|---|---|
|`view/_dataclass.py`|`DemoItem`, `DemoRequest` (cÃ³ `inference_mode`, `use_memory`), `DemoTrace` (plan, steps, `ask_user`, `reflections`, `first_attempt_ok`, `truncated`, `usage`, `inference`), `DemoResult` (`status`, `text`, `items`, `trace`), `DemoProfile`, `MemoryView`|
|`view/format_items.py`, `view/format_trace.py`, `view/status_badge.py`|Ä‘á»‹nh dáº¡ng danh sÃ¡ch item thÃ nh báº£ng, váº¿t thá»±c thi thÃ nh markdown, badge theo status|
|`adapter/adapt_from_plan_executor.py`|káº¿t quáº£ `PlanExecutor` â†’ `DemoResult`; `text` do hÃ m máº«u táº¥t Ä‘á»‹nh, **khÃ´ng pháº£i LLM**|
|`adapter/adapt_from_plan_executor_error.py`|khi `PlanExecutor` nÃ©m ngoáº¡i lá»‡|
|`adapter/adapt_from_inference.py`|`adapt_from_inference(answer, *, request, item_id_to_metadata, trace=None)`: `Answer` â†’ `DemoResult`; bá»• sung metadata cÃ²n thiáº¿u tá»« corpus, `error` chá»‰ khi status `tool_error`, gáº¯n `trace.inference` (composer / grounded / fallback_reason / reason / usage). **ÄÃ£ cÃ i Ä‘áº·t â€” khÃ´ng cÃ²n `raise NotImplementedError`**|
|`adapter/_helper.py`|vÄƒn báº£n tráº¡ng thÃ¡i dÃ¹ng chung cho cÃ¡c adapter|
|`backend/mock_backend.py`|`MockBackend`: tráº£ káº¿t quáº£ cÃ³ sáºµn (phÆ°Æ¡ng Ã¡n dá»± phÃ²ng khi demo lá»—i; khÃ´ng cáº§n dá»¯ liá»‡u / LLM / máº¡ng)|
|`backend/live_backend.py`|`LiveBackend`: táº£i dá»¯ liá»‡u **má»™t láº§n** (`initialize`), dá»±ng executor vÃ  `Type1Agent`, xá»­ lÃ½ request tuáº§n tá»± cÃ³ khoÃ¡ (`respond`); nay `respond` cháº¡y cáº£ `compose_answer(outcome, llm, mode=request.inference_mode)` â†’ `adapt_from_inference`, vÃ  chá»¥p memory trÆ°á»›c / sau báº±ng `take_memory_snapshot` khi `use_memory`; `get_sample_users`, `build_profiles`|
|`samples/sample_requests.py`, `samples/sample_users.py`|`sample_requests(language)` (tá»« `TEMPLATES` cá»§a `agents/_schema.py`), `sample_users(â€¦)` (chá»n user tháº­t theo segment cold / sparse / warm)|
|`samples/_identity_injection.py`|`identity_injection_vi` / `identity_injection_en`: cÃ¢u gáº¯n danh tÃ­nh user vÃ o request máº«u|
|`_profile_builder.py`|`build_profiles(...)` â€” Ä‘á»c `agent/demo_profiles.yaml` (`demo_profiles.pinned`) vÃ  dá»±ng profile `blank` / `pinned` / `auto` cho UI|
|`_consumed_by.py`|`detect_consumed_by(steps, memory_step_indices)`: step nÃ o Ä‘Ã£ dÃ¹ng output `MemoryTool` qua ref `$<n>`|
|`_memory_snapshot.py`|`take_memory_snapshot(memory_tool, user_id)`: chá»¥p profile trÆ°á»›c / sau má»™t request Ä‘á»ƒ UI so sÃ¡nh|
|`view/format_memory.py`|`format_memory(view, item_id_to_metadata=None)`: render `MemoryView` thÃ nh markdown|
|`_limits.py`|`DemoLimits` tá»« `agent/demo.yaml` (validate)|

**Äiá»u cáº§n biáº¿t:** demo **Ä‘Ã£ dÃ¹ng** `package/inference` â€” `live_backend.respond` gá»i `compose_answer(...)` rá»“i `adapt_from_inference(...)`, nÃªn `text` láº¥y tá»« `Answer` (háº¿t "hÃ m máº«u"). CÃ¡c import thá»«a cá»§a `LiveBackend` **chÆ°a Ä‘á»‘i chiáº¿u láº¡i** (`.venv` khÃ´ng cÃ³ `pyflakes`).

---

# 32. VÃ­ dá»¥ end-to-end

Dá»¯ liá»‡u trong vÃ­ dá»¥ lÃ  **minh hoáº¡**; luá»“ng, tÃªn tool, tÃªn trÆ°á»ng vÃ  status láº¥y tá»« code (`agents/planner/*`, `agents/results/extract_recommendations.py`, `inference/**`).

## 32.1. Má»™t dÃ²ng

```text
request â”€â–º PlanExecutor.plan()      1 LLM call; JSON há»ng thÃ¬ retry plan_retries láº§n
        â”€â–º _execute()               má»—i step: validate â†’ gá»i tool â†’ ghi entry
        â”€â–º (REFLECT náº¿u step lá»—i / khÃ´ng ra item, â‰¤ reflect_rounds) â”€â–º _execute láº¡i
        â”€â–º outcome_from_plan_results() â”€â–º AgentOutcome
        â”€â–º compose_answer(): classify_outcome â†’ status â†’ template | LLM (+grounding)
        â”€â–º Answer
```

Ba loáº¡i viá»‡c tÃ¡ch riÃªng, khÃ´ng tool nÃ o lÃ m hai viá»‡c:

|Tool|Viá»‡c|Tráº£ vá»|
|---|---|---|
|ItemCF / SemanticSearch / SQL|**tÃ¬m á»©ng viÃªn**|`candidates` (id + Ä‘iá»ƒm/metadata thÃ´)|
|RecoModel|**xáº¿p háº¡ng** á»©ng viÃªn cho má»™t user|`ranked` (id + score, **khÃ´ng** cÃ³ tÃªn/giÃ¡)|
|Query|**láº¥y metadata** theo id|`items` (title, store, price, ratingâ€¦)|
|Memory|**tÃ³m táº¯t lá»‹ch sá»­** user|`top_categories`, `price_range`, `recent_items`|

QueryTool á»Ÿ cuá»‘i lÃ  Ä‘á»ƒ Inference cÃ³ title/price mÃ  viáº¿t cÃ¢u tráº£ lá»i vÃ  kiá»ƒm grounding; nÃ³ **bá»• sung thÃ´ng tin hiá»ƒn thá»‹**, khÃ´ng Ä‘á»•i thá»© tá»±.

## 32.2. Ká»‹ch báº£n A â€” Ä‘Æ°á»ng thÃ nh cÃ´ng

**Request:** `TÃ´i lÃ  u1, vá»«a mua Video_Games::B00X1, gá»£i Ã½ game tÆ°Æ¡ng tá»±.`

```json
{"steps": [
  {"tool": "ItemCFTool",    "args": {"items": ["Video_Games::B00X1"], "top_k": 30}},
  {"tool": "RecoModelTool", "args": {"user_id": "u1", "candidates": "$1.candidates", "top_k": 5}},
  {"tool": "QueryTool",     "args": {"item_ids": "$2.ranked.*.item_id"}}
], "ask_user": null}
```

- Step 1 â†’ 30 dÃ²ng `candidates`; step 2 â†’ `ranked` 5 dÃ²ng (theo Ä‘iá»ƒm, `cold_start=false`); step 3 â†’ metadata 5 item.
- Má»—i step ghi `{tool, ok, data, error, invented_ids, args (Ä‘Ã£ resolve, cáº¯t gá»n), output_summary, latency_seconds, error_kind}`. KhÃ´ng step lá»—i + cÃ³ item â‡’ `first_attempt_ok=true` â‡’ khÃ´ng reflect.
- Inference: `extract_recommendations` láº¥y 5 id **theo `ranked`** â†’ `classify_outcome` â‡’ `ok` â†’ `compose_answer(mode="llm")`; `check_grounding` kiá»ƒm 4 Ä‘iá»u: id láº¡, `mentioned_item_ids` khá»›p text, Ä‘á»§ item + Ä‘Ãºng thá»© tá»±, giÃ¡ trong `price_tolerance`. TrÆ°á»£t â‡’ retry `llm_retries` láº§n â‡’ háº¿t lÆ°á»£t thÃ¬ lÃ¹i template (`fallback_reason`).

## 32.3. Ká»‹ch báº£n B â€” Ä‘Æ°á»ng lá»—i

|Lá»—i trong plan|Chá»‘t cháº·n|Káº¿t quáº£ step|
|---|---|---|
|tool khÃ´ng cÃ³ trong danh sÃ¡ch|`unknown tool`|`ok=false`, **khÃ´ng gá»i tool**|
|id khÃ´ng xuáº¥t hiá»‡n trong request|`_invented_ids`|`ok=false`, `invented_ids=[â€¦]`, **khÃ´ng gá»i**|
|arg khÃ´ng cÃ³ trong `input_schema` (vd `price_max` ngoÃ i `filters`)|`_unknown_args` (cÃ³ gá»£i Ã½)|`ok=false`, khÃ´ng gá»i|
|ref há»ng (`$5.x` khi má»›i 3 step, step Ä‘Æ°á»£c tham chiáº¿u Ä‘Ã£ lá»—i)|`_resolve_refs` nÃ©m `ValueError`|step Ä‘Ã³ lá»—i (`bad_reference`), step khÃ¡c váº«n cháº¡y|
|plan dÃ i hÆ¡n `max_steps`|cáº¯t bá»›t|`last_truncated=true`|
|LLM tráº£ rá»—ng / khÃ´ng pháº£i JSON|`_extract_plan` nÃ©m `ValueError`|retry `plan_retries`, háº¿t thÃ¬ `run()` nÃ©m lá»—i|

**Reflect** cháº¡y khi plan cháº¡y xong nhÆ°ng cÃ³ step lá»—i **hoáº·c** khÃ´ng ra item (vÃ  khÃ´ng pháº£i `ask_user`): gá»­i LLM `_step_report` (tÃªn khoÃ¡ + Ä‘á»™ dÃ i list, khÃ´ng gá»­i dá»¯ liá»‡u), cháº¡y plan Ä‘Ã£ sá»­a. **KhÃ´ng** reflect khi cÃ³ id bá»‹a, SQL háº¿t time budget, hoáº·c `reflect_rounds=0`; reply reflect há»ng â‡’ bá», giá»¯ káº¿t quáº£ cÅ©. **Cold start:** `RecoModelTool` khÃ´ng lá»—i â€” tráº£ `cold_start=true`, `has_personal_signal=false`.

|Äiá»u kiá»‡n (rule Ä‘áº§u tiÃªn khá»›p tháº¯ng)|Status|
|---|---|
|cÃ³ `question`, khÃ´ng step nÃ o cháº¡y|`ask_user`|
|cÃ³ `invented_ids`, hoáº·c lá»—i á»Ÿ planner|`tool_error`|
|cÃ³ item (dÃ¹ cÃ³ step lá»—i)|`ok` (reason `partial: <tool> failed`)|
|khÃ´ng item + cÃ³ lá»—i|`tool_error`|
|khÃ´ng item + khÃ´ng lá»—i|`no_result`|

`ask_user`, `no_result`, `tool_error` **khÃ´ng bao giá» gá»i LLM**.

## 32.4. Ká»‹ch báº£n C â€” cÃ¡ nhÃ¢n hoÃ¡ vá»›i `MemoryTool`

**Request:** `TÃ´i lÃ  u1, gá»£i Ã½ game cho tÃ´i.` â†’ plan: `MemoryTool` â†’ `SQLTool(filters.categories_any="$1.top_categories")` â†’ `RecoModelTool` â†’ `QueryTool`.

- `known=false` (user láº¡) â‡’ `top_categories=[]`, `price_range=None` â‡’ `$1.price_range.max` **lá»—i tham chiáº¿u** â‡’ step 2 lá»—i â‡’ reflect.
- CÃ¡ch khÃ¡c: dÃ¹ng `$1.recent_items` lÃ m seed cho `ItemCFTool`.

## 32.5. Chá»— vÃ­ dá»¥ cÅ© (PDF Â§14) lá»‡ch code

1. **"ThÃ­ch Elden Ring"** pháº£i lÃ  id namespaced (`Video_Games::B00X1`) **vÃ ** xuáº¥t hiá»‡n trong request, náº¿u khÃ´ng `_invented_ids` cháº·n; tÃªn â†’ id cáº§n má»™t bÆ°á»›c tra cá»©u (`SemanticSearchTool`) mÃ  prompt chÆ°a dáº¡y.
2. **"DÆ°á»›i $60" + "giá»‘ng item nÃ y" khÃ´ng Ä‘i cÃ¹ng má»™t plan:** `ItemCFTool` khÃ´ng cÃ³ tham sá»‘ giÃ¡; `price_max` chá»‰ cÃ³ trong `filters` cá»§a `SQLTool`/`SemanticSearchTool`; `SQLTool` khÃ´ng nháº­n `candidates`. VÃ¬ váº­y request `constrained` nÃªn cháº¥m theo "thoáº£ rÃ ng buá»™c giÃ¡", khÃ´ng Ä‘Ã²i giá»‘ng item gá»‘c.
3. `SQLTool` **Ä‘Ã£** náº±m trong `for_planner()` (báº£n PDF ghi lÃ  khÃ´ng).
4. Memory khÃ´ng cÃ³ trong vÃ­ dá»¥ cÅ© dÃ¹ `for_planner_memory` cÃ³ `MemoryTool`.

## 32.6. Äiá»ƒm nÃªn thÃ nh test

Má»—i hÃ ng cá»§a hai báº£ng á»Ÿ 14.3 = má»™t test vá»›i plan viáº¿t sáºµn, kiá»ƒm `entry.error` + viá»‡c tool **khÃ´ng** Ä‘Æ°á»£c gá»i; grounding: mutate cÃ¢u tráº£ lá»i (thÃªm id láº¡, Ä‘á»•i thá»© tá»±, Ä‘á»•i giÃ¡) vÃ  kiá»ƒm `check_grounding` báº¯t Ä‘Æ°á»£c.

---

# 33. Kiáº¿n trÃºc hiá»‡n táº¡i vs. Ä‘Ã­ch (báº£n nÃ©n)

**Hiá»‡n táº¡i:** `User â†’ LLM â†’ plan hoÃ n chá»‰nh â†’ PlanExecutor â†’ tools â†’ Inference` â€” má»™t lÆ°á»£t, khÃ´ng cÃ³ vÃ²ng láº·p cÃ³ state. **ÄÃ­ch:** `User â†’ LLM â†’ chá»n tool â†’ káº¿t quáº£ â†’ LLM â†’ â€¦` (tool-calling láº·p, multi-turn, memory ghi Ä‘Æ°á»£c).

ÄÃ£ cÃ³: planning, plan-reflect háº¹p (Â§9.1), memory read-only (Â§6.3), inference trÃ¬nh bÃ y (Â§9.4), bá»™ Ä‘Ã¡nh giÃ¡ nhiá»u táº§ng (Â§10). CÃ²n thiáº¿u: vÃ²ng láº·p "quan sÃ¡t káº¿t quáº£ â†’ quyáº¿t Ä‘á»‹nh bÆ°á»›c káº¿", conversation state, memory ghi/forget.

> Timeline 06/10 â†’ 20/10 cá»§a má»¥c 15 cÅ© vÃ  má»¥c 17 (káº¿ hoáº¡ch 17/10), 18 (snapshot 19/10) Ä‘Ã£ bá» khi tinh gá»n ngÃ y 30/10 â€” má»‘c thá»i gian xem Â§1.1, sá»‘ liá»‡u 20/10 xem Â§19, sá»‘ liá»‡u má»›i nháº¥t xem Â§21.

---

# 34. Issue tracker â€” phÃ¡t hiá»‡n theo snapshot vÃ  tráº¡ng thÃ¡i cáº§n xÃ¡c minh

> **LÆ°u Ã½ Ä‘á»“ng bá»™ theo tuáº§n:** má»¥c nÃ y lÃ  issue tracker tÃ­ch luá»¹ tá»« cÃ¡c snapshot 06/10, 12/10 vÃ  17/10, khÃ´ng pháº£i toÃ n bá»™ Ä‘á»u Ä‘Æ°á»£c xÃ¡c minh láº¡i á»Ÿ `src(8).zip` ngÃ y 20/10. NhÃ£n dÆ°á»›i Ä‘Ã¢y pháº£n Ã¡nh báº±ng chá»©ng táº¡i thá»i Ä‘iá»ƒm ghi chÃº; khÃ´ng tá»± Ä‘á»™ng pháº£n Ã¡nh tráº¡ng thÃ¡i hiá»‡n táº¡i. Khi má»™t má»¥c chÆ°a Ä‘Æ°á»£c Ä‘á»‘i chiáº¿u láº¡i vá»›i zip 20/10, hÃ£y xem lÃ  **historical / cáº§n re-check**, khÃ´ng pháº£i kháº³ng Ä‘á»‹nh Ä‘ang cÃ²n lá»—i.
>
> Quy Æ°á»›c nhÃ£n lá»‹ch sá»­: **[ÄÃ£ sá»­a]** Ä‘Ã£ xÃ¡c nháº­n trong snapshot ghi chÃº; **[CÃ²n]** cÃ²n tá»“n táº¡i á»Ÿ snapshot Ä‘Æ°á»£c nÃªu; **[ChÆ°a Ä‘á»‘i chiáº¿u láº¡i]** khÃ´ng cÃ³ xÃ¡c nháº­n má»›i; **[ChÆ°a Ä‘o]** lÃ  giáº£ thuyáº¿t chÆ°a kiá»ƒm trÃªn dá»¯ liá»‡u tháº­t. Snapshot 17/10 Ä‘Ã£ cháº¡y thá»­ `ItemCFTool(items=str)`, `candidate_ids(str)`, `k_core_filter` (chuá»—i 30 vÃ²ng), `mcnemar_test`, pyflakes vÃ  test suite theo ghi chÃº lÃºc Ä‘Ã³. ÄÃ¢y lÃ  káº¿t quáº£ cá»§a má»‘c 17/10, khÃ´ng nÃªn diá»…n Ä‘áº¡t nhÆ° vá»«a cháº¡y láº¡i ngÃ y 20/10.

**Äá»‘i chiáº¿u cÆ¡ há»c ngÃ y 29/10/2026 (commit `7c1144a`) â€” chá»‰ cÃ¡c má»¥c kiá»ƒm Ä‘Æ°á»£c báº±ng má»™t lá»‡nh:**

- **[ÄÃ£ sá»­a 29/10]** `package/__init__.py` â€” trÆ°á»›c lÃ  `from .judge import JevClient` trong khi `package/judge/` Ä‘Ã£ chuyá»ƒn sang `package/evaluation/judge/` (commit `7c1144a`), lÃ m má»i `import packageâ€¦` nÃ©m `ModuleNotFoundError: No module named 'package.judge'` vÃ  `pytest` dá»«ng ngay á»Ÿ `tests/conftest.py`. ÄÃ£ tráº£ file vá» **rá»—ng** (Ä‘Ãºng tráº¡ng thÃ¡i 20/10): `import package` khÃ´ng náº¡p subpackage nÃ o (thoáº£ `tests/test_package_import.py`), cÃ²n `from package.evaluation.judge import JevClient` váº«n dÃ¹ng Ä‘Æ°á»£c. Sau Ä‘Ã³ `pytest`: 1212 test â†’ 1198 passed / 10 failed / 2 skipped / 2 xfailed (má»¥c 12).
- **[CÃ²n â€” 10 test Ä‘á» khi cháº¡y láº¡i 29/10]** danh sÃ¡ch Ä‘áº§y Ä‘á»§ á»Ÿ má»¥c 12; **chÆ°a Ä‘iá»u tra nguyÃªn nhÃ¢n** nÃªn chÆ°a gáº¯n nhÃ£n lá»—i cá»¥ thá»ƒ.
- **[ÄÃ£ sá»­a 29/10]** `package/demo/adapter/adapt_from_inference.py` khÃ´ng cÃ²n `raise NotImplementedError` (grep = 0 káº¿t quáº£); `live_backend.respond` Ä‘Ã£ gá»i `compose_answer` + adapter nÃ y.
- **[ÄÃ£ sá»­a 29/10]** `tests/config/test_path_hygiene.py` khÃ´ng cÃ²n glob `scripts/sh/*.sh` (grep = 0 káº¿t quáº£).
- **[ÄÃ£ sá»­a 29/10]** tham chiáº¿u `docs/decisions.md` Ä‘Ã£ bá» (`configs/agent/llm.yaml:2` D-003b, `configs/path/domains.yaml:2` D-010); báº£n thÃ¢n `docs/decisions.md` váº«n khÃ´ng tá»“n táº¡i nhÆ°ng khÃ´ng cÃ²n ai trÃ­ch.
- **[ÄÃ£ sá»­a 29/10]** `docs/inference_contract.md`, `docs/ablation_protocol.md`, `docs/demo.md` **khÃ´ng tá»“n táº¡i á»Ÿ báº¥t ká»³ má»‘c nÃ o trong git** (`git ls-tree -r 40d31f2 -- docs` rá»—ng; `docs/` chá»‰ xuáº¥t hiá»‡n tá»« 26/10). Hai chá»— trÃ­ch trong code Ä‘Ã£ bá» (`configs/agent/inference.yaml:1`, `package/inference/outcome/classify_outcome.py:10`); má»¥c 9.4 / 10.4 / 13.1 nay ghi rÃµ file khÃ´ng tá»“n táº¡i.
- **[CÃ²n]** trong `docs/evaluation/` cÃ²n 2 chá»— trÃ­ch `PR_DESCRIPTION_PHASE0.md` (`component_evaluation_summary.md`, `FINAL_SUMMARY.md`) â€” file nÃ y khÃ´ng cÃ³ trong repo (chÆ°a sá»­a vÃ¬ lÃ  tÃ i liá»‡u phÃ¢n tÃ­ch cá»§a báº¡n).
- **[CÃ²n â€” cáº§n hiá»ƒu láº¡i]** `tools/corpus/_sql.py::ITEMS_TABLE_SCHEMA`: **khÃ´ng** dÃ¹ng Ä‘á»ƒ táº¡o báº£ng (báº£ng do `DataFrame.to_sql` táº¡o) nhÆ°ng **cÃ³** Ä‘Æ°á»£c dÃ¹ng Ä‘á»ƒ tÃ­nh `_CORPUS_SCHEMA_FINGERPRINT` (`_sql.py:79`). CÃ¢u "khÃ´ng Ä‘Æ°á»£c dÃ¹ng" á»Ÿ Â§5 vÃ  Â§16.2 vÃ¬ váº­y khÃ´ng cÃ²n Ä‘Ãºng theo nghÄ©a Ä‘en.
- **[CÃ²n]** `scripts/evaluation/analyze_agent_failures.py` váº«n khÃ´ng cÃ³ (Ä‘Ã£ cÃ³ script khÃ¡c: `analyze_ranking_bottlenecks.py`).
- **[CÃ²n]** `package/agents/{ablation,evaluation}/` váº«n tá»“n táº¡i vÃ  chá»‰ chá»©a `__pycache__`.
- **[CÃ²n]** `scripts/demo/demo_full_agent.py` váº«n cÃ²n báº£n `build_tools()` riÃªng (5 tool).
- **[CÃ²n]** `package/tools/__init__.py` váº«n import eager `evaluation` / `recommenders` vÃ  khÃ´ng export `Tool`, `ToolResult`, `ToolInputError`, `candidate_ids`, `MemoryTool`.
- **[CÃ²n]** `tools/base/candidate_results.py` váº«n chÆ°a tool nÃ o dÃ¹ng (chá»‰ `tools/base/__init__.py` export vÃ  test).
- **[ÄÃ£ sá»­a 29/10]** docstring lá»‡ch: `package/evaluation/jev_product_evaluator.py:37` ghi "default configs/agent/judge.yaml" trong khi dÃ²ng 51 Ä‘á»c `configs/eval/judge.yaml` â€” nay docstring ghi Ä‘Ãºng `configs/eval/judge.yaml`.
- **[ChÆ°a Ä‘á»‘i chiáº¿u láº¡i 29/10]** danh sÃ¡ch import thá»«a (pyflakes) á»Ÿ Â§16.2 â€” `.venv` khÃ´ng cÃ³ `pyflakes` nÃªn khÃ´ng cháº¡y láº¡i Ä‘Æ°á»£c.

## 34.1. ÄÃ£ sá»­a á»Ÿ cÃ¡c snapshot trÆ°á»›c (nÃ©n)

13 nhÃ³m lá»—i Ä‘Ã£ xÃ¡c nháº­n sá»­a trong giai Ä‘oáº¡n 17/10â€“20/10: kiá»ƒm kiá»ƒu Ä‘áº§u vÃ o (`ToolInputError` rÃµ rÃ ng), `MemoryTool` tÃ­nh báº±ng SQL (háº¿t cáº¯t 100 dÃ²ng), `RecoModelTool` bÃ¡o `unscored_item_ids`/`has_personal_signal`, `ItemCorpus` cÃ³ authorizer + time budget + `ValueError` khi domain/id mÃ¢u thuáº«n, `SQLTool` filter semantics (store khÃ´ng phÃ¢n biá»‡t hoa/thÆ°á»ng, `price_min > price_max` bÃ¡o lá»—i), `QueryTool` giá»¯ thá»© tá»± `item_ids`, `SemanticSearchTool` dÃ¹ng `compile_filters` cÃ´ng khai, `Tool.__init_subclass__` báº¯t buá»™c khai bÃ¡o schema, `compare_experiments` import Ä‘Ãºng, 14 test trá» `scripts/run_agent_eval.py` Ä‘Ã£ sá»­a, `infer_matrix_shape` háº¿t báº£n trÃ¹ng, vÃ  quy Æ°á»›c Â§2.6 Ä‘Æ°á»£c test Ã©p.

> Danh sÃ¡ch chi tiáº¿t tá»«ng má»¥c Ä‘Ã£ bá» khi tinh gá»n 30/10. Tráº¡ng thÃ¡i hiá»‡n táº¡i kiá»ƒm báº±ng test (Â§12) vÃ  báº±ng má»¥c 29/10 á»Ÿ trÃªn.

## 34.2. [CÃ²n táº¡i snapshot cÅ© / cáº§n re-check vá»›i `src(8).zip`] (cÃ¡c má»¥c ban Ä‘áº§u xÃ¡c nháº­n 12/10; má»™t pháº§n Ä‘á»‘i chiáº¿u 19/10)

- **`SCHEMA_HINT` lá»‡ch kiá»ƒu:** ghi `rating_number REAL`, nhÆ°ng báº£ng tháº­t lÃ  INTEGER khi má»i giÃ¡ trá»‹ nguyÃªn (REAL náº¿u cÃ³ thiáº¿u). Test chá»‰ so tÃªn báº£ng/cá»™t, khÃ´ng so kiá»ƒu. Äá»•i cÃ¡ch táº¡o báº£ng sáº½ Ä‘á»•i giÃ¡ trá»‹ tool tráº£ ra (`200` â†’ `200.0`) nÃªn chÆ°a lÃ m.
- **GiÃ¡ dáº¡ng khoáº£ng** `"10 - 20"` thÃ nh NULL, khÃ´ng phÃ¢n biá»‡t Ä‘Æ°á»£c vá»›i giÃ¡ vá»‘n trá»‘ng.
- **`SQLTool`:** `include_missing_price` Ä‘á»©ng má»™t mÃ¬nh váº«n khÃ´ng cÃ³ tÃ¡c dá»¥ng.
- **`ItemCFTool`:** lá»c domain **sau** khi cáº¯t top-k lÃ¡ng giá»ng nÃªn cÃ³ thá»ƒ ra Ã­t hÆ¡n `top_k` (Ä‘Ã£ ghi trong docstring).
- **Planner khÃ´ng cÃ³ `SQLTool`** (má»¥c 2.4); **plan-reflect khÃ´ng cá»©u Ä‘Æ°á»£c timeout SQL vÃ  id bá»‹a** (do thiáº¿t káº¿).
- **Test vÃ  script:** 1 test demo cáº§n dá»¯ liá»‡u tháº­t (má»¥c 12). `scripts/README.md` cÃ³ nhÆ°ng khÃ´ng nháº¯c biáº¿n mÃ´i trÆ°á»ng; `analyze_agent_failures.py` (cÃ³ á»Ÿ báº£n 12/10) **khÃ´ng cÃ³** trong zip. (14 test trá» Ä‘Æ°á»ng dáº«n cÅ© cá»§a script Ä‘Ã£ Ä‘Æ°á»£c sá»­a sau refactor.)
- **CÃ²n import thá»«a / lá»—i nhá» (pyflakes, zip sau refactor):** `tools/corpus/item_corpus.py` (`warnings`, `Iterable`, `numpy as np`), `tools/ranking/item_cf_tool.py` (`Sequence`), `tools/sql_query/compile_filters.py` (`FILTER_KEYS`; f-string thiáº¿u placeholder ~dÃ²ng 255), `tools/score/baseline_scorer.py` (`math`), `agents/toolkit/agent_tools.py` (`ItemCorpus`), `data/split/load_splits.py` (`infer_matrix_shape` import Ä‘á»ƒ re-export), `inference/grounding/_helper.py` (`Any`), `demo/` (`adapter/_helper.py`: f-string thiáº¿u placeholder; `backend/live_backend.py`: `ItemCorpus`, biáº¿n `k`, `as_of`; `backend/mock_backend.py`: `Any`), `evaluation/ablation/` (`_compare`: `json`, `Path`, `ORACLE_KINDS`, `load_group_data`, `get_ablation_limits`; `_loader`: `get_ablation_limits`; `_statistics`: `Any`), `scripts/` (`diagnose_splits`: `pd`; `compare_experiments`: `json`, `Path`, `Any`; `demo_full_agent`: `load_config`, `build_llm_provider`; `run_demo`: `Any`, `get_data_paths`, `get_domains`).
- **`tools/corpus/_sql.py::ITEMS_TABLE_SCHEMA` khÃ´ng Ä‘Æ°á»£c dÃ¹ng** (`from_dataframe` táº¡o báº£ng báº±ng `to_sql`; `item_id` chá»‰ cÃ³ `UNIQUE INDEX`, khÃ´ng pháº£i PRIMARY KEY nhÆ° DDL gá»£i Ã½). XoÃ¡ háº±ng sá»‘ hoáº·c dÃ¹ng tháº­t; dÃ¹ng tháº­t sáº½ Ä‘á»•i kiá»ƒu cá»™t (xem dÃ²ng `SCHEMA_HINT` á»Ÿ trÃªn).
- **`scripts/demo/demo_full_agent.py`** cÃ²n báº£n `build_tools()` riÃªng, cÅ©, trÃ¹ng vai trÃ² vá»›i `agents/toolkit/build_tools.py`.
- **[ÄÃ£ sá»­a sau refactor]** `data/split/infer_matrix_shape.py` khÃ´ng cÃ²n lÃ  báº£n trÃ¹ng cá»§a hÃ m trong `load_splits.py` (xem má»¥c 4.2).
- **`tools/__init__`** váº«n import eager `evaluation`/`recommenders` vÃ  khÃ´ng export `Tool`, `ToolResult`, `ToolInputError`, `candidate_ids`, `MemoryTool` (import tá»« `package.tools.base` / `package.memory`).
- **[Cáº­p nháº­t 17/10: Ä‘Ã£ thÃªm index `idx_cat_item_cat`, chÆ°a Ä‘o trÃªn dá»¯ liá»‡u tháº­t â€” xem 16.1]** **Timeout SQL = `SemanticSearchTool` + `categories_any` (Ä‘Ã£ Ä‘o trÃªn log tháº­t; cÆ¡ cháº¿ Ä‘Ã£ tÃ¡i hiá»‡n trÃªn corpus giáº£):**
    - _Log tháº­t_ (`exp_002`, `exp_003` trong zip, cÃ¡c step `SemanticSearchTool` cá»§a planner / planner_memory, Ä‘áº¿m theo `latency_seconds â‰¥ 4 s` vÃ¬ step phá»¥ thuá»™c cÅ©ng mang chuá»—i `interrupted` trong thÃ´ng bÃ¡o lá»—i): **11 step timeout, latency p50 â‰ˆ 5,01 s, max 5,04 s (Ä‘Ãºng budget `sql_time_budget_seconds = 5.0`)**. Cáº£ 11 Ä‘á»u cÃ³ `filters.categories_any`; trong 17 lá»i gá»i cÃ³ `categories_any` thÃ¬ 11 timeout, 6 cháº¡y xong; trong 19 lá»i gá»i khÃ´ng cÃ³ `categories_any` thÃ¬ **0** timeout. `QueryTool`, `RecoModelTool`, `ItemCFTool` khÃ´ng cÃ³ timeout riÃªng. Máº«u nhá» (n = 20 request/exp).
    - _CÆ¡ cháº¿:_ filter `categories_any` biÃªn dá»‹ch thÃ nh `EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id AND c.category IN (â€¦))`. `EXPLAIN QUERY PLAN` cho tháº¥y SQLite dÃ¹ng `idx_cat_cat (category=?)` (khÃ´ng dÃ¹ng `idx_cat_item`), tá»©c **vá»›i má»—i dÃ²ng FTS khá»›p nÃ³ duyá»‡t cáº£ danh má»¥c** rá»“i má»›i so `item_id`: chi phÃ­ â‰ˆ (sá»‘ dÃ²ng khá»›p) Ã— (kÃ­ch thÆ°á»›c danh má»¥c), ráº¥t cháº­m vá»›i danh má»¥c lá»›n nhÆ° `Cases`, `Earbud Headphones`. CÃ¹ng filter áº¥y dÃ¹ng trong `SQLTool`, vÃ  `categories_all` cÅ©ng cÃ³ dáº¡ng tÆ°Æ¡ng tá»±.
    - _TÃ¡i hiá»‡n (corpus GIáº¢ 300k item, 40% thuá»™c `Cases`, khÃ´ng pháº£i dá»¯ liá»‡u tháº­t):_ query `cases black` + `categories_any=["Cases"]` + `price_max=15` â†’ **5,01 s, `ok=False`, `query exceeded the time budget`**; thÃªm index `CREATE INDEX idx_cat_item_cat ON item_categories(item_id, category)` â†’ **0,22 s, `ok=True`**. CÃ¹ng query khÃ´ng cÃ³ `categories_any`: 0,4 s (trÆ°á»›c) / 0,28 s (sau).
    - **[ChÆ°a Ä‘o]** trÃªn corpus tháº­t (631k item) vÃ  chÆ°a sá»­a code: cáº§n táº¡o index nÃ y trÃªn `ItemCorpus` rá»“i cháº¡y láº¡i Ä‘Ãºng cÃ¡c query bá»‹ timeout trong log (xem Â§16.2 vÃ  Â§20.7). Giáº£ thuyáº¿t cÅ© "FTS5 OR trÃªn 631k item vÆ°á»£t budget" **khÃ´ng Ä‘Æ°á»£c á»§ng há»™**: query khÃ´ng cÃ³ `categories_any` cháº¡y < 1,4 s trong log tháº­t.

**Má»›i á»Ÿ báº£n 17/10:**

- **[ÄÃ£ sá»­a sau refactor]** `scripts/experiments/compare_experiments.py` trÆ°á»›c Ä‘Ã¢y import `package.agents.evaluation.ablation._compare` (khÃ´ng tá»“n táº¡i) nÃªn `--help` Ä‘Ã£ `ModuleNotFoundError`; nay import `package.evaluation.ablation`.
- **[ÄÃ£ sá»­a trong `src(7).zip`] `package/evaluation/ablation/_compare.py`:** nhÃ¡nh McNemar hiá»‡n ghi `results[kind_key]`, khÃ´ng cÃ²n `king_key`. Tuy nhiÃªn váº«n nÃªn giá»¯ test há»“i quy cháº¡m nhÃ¡nh McNemar (â‰¥ 10 cáº·p báº¥t nháº¥t), vÃ¬ test chá»‰ xÃ¡c nháº­n tÃªn biáº¿n Ä‘Ãºng chÆ°a chá»©ng minh bÃ¡o cÃ¡o end-to-end trÃªn experiment tháº­t.
- **`candidate_results`** (`tools/base/candidate_results.py`, giá»¯ `score` / `similarity`) **chÆ°a tool nÃ o dÃ¹ng**, chá»‰ cÃ³ test â€” liÃªn quan quyáº¿t Ä‘á»‹nh ranking vs retrieval score (16.3).
- **[ÄÃ£ sá»­a 29/10] `demo` Ä‘Ã£ ná»‘i `inference`:** `adapt_from_inference` Ä‘Ã£ cÃ i Ä‘áº·t, `live_backend.respond` gá»i `compose_answer`; (báº£n 20/10: cÃ²n `raise NotImplementedError`, `text` cá»§a demo lÃ  hÃ m máº«u).
- **Tham chiáº¿u tÃ i liá»‡u:** `docs/inference_contract.md`, `docs/ablation_protocol.md`, `docs/demo.md` nay cÃ³ trong zip; **`docs/decisions.md` váº«n khÃ´ng cÃ³** (`llm.yaml` D-003b, `domains.yaml` D-010). Nhiá»u docstring cÃ²n trÃ­ch sá»‘ má»¥c cá»§a spec cÅ© ("má»¥c XX", "spec má»¥c XXI" á»Ÿ `api/llm_provider.py`, `api/build_llm_provider.py`, `config/load_config.py`).
- **Bá»‘ cá»¥c `experiments/` vÃ  log test chÆ°a thá»‘ng nháº¥t:** zip cÃ³ `experiments/{baselines,agent_eval}/â€¦`, `experiments/README.md` (mÃ´ táº£ cáº£ `phase4_baselines/`) vÃ  `experiments/test_logs/` (chuyá»ƒn tay), nhÆ°ng `run_baselines` / `tune_baselines` váº«n ghi `exp_NNN` tháº³ng trong `experiments/`, `run_agent_eval` / `candidate_recall` ghi vÃ o subdir theo config, `run_all_tests.sh` / `results_report.py` váº«n ghi `tests/logs/` (README nÃ³i `experiments/test_logs/`); comment `data_paths.yaml` liá»‡t kÃª `experiments/{baselines,data_pipeline,smoke_tests,test_logs}/`.
- **`tests/config/test_path_hygiene.py`** cÃ²n glob `scripts/sh/*.sh` (thÆ° má»¥c khÃ´ng cÃ²n) nÃªn kiá»ƒm tra Ä‘Ã³ luÃ´n qua mÃ  khÃ´ng kiá»ƒm gÃ¬.

## 34.3. Quyáº¿t Ä‘á»‹nh cÃ²n treo (giá»¯ láº¡i tá»« báº£n 06/10, Ä‘Ã£ nÃ©n)

- **Ranking vs retrieval score:** `RecoModelTool` bá» `similarity` cá»§a retrieval rá»“i cháº¥m láº¡i tá»« lá»‹ch sá»­ user; ba hÆ°á»›ng (trá»™n hybrid / chá»‰ rank khi cáº§n / Ä‘á»•i model) chÆ°a chá»n. CÃ¢u há»i gá»‘c: agent tráº£ lá»i "giá»‘ng cÃ¡i nÃ y" hay "há»£p vá»›i tÃ´i"?
- **Hai há» ItemKNN:** `history @ S` vs `history @ S.T` cho thá»© háº¡ng khÃ¡c nhau khi cáº¯t top-k â†’ chÆ°a chá»‘t há» nÃ o lÃ  chuáº©n (test `test_contract_recommenders.py` chá»‰ kháº³ng Ä‘á»‹nh chÃºng khá»›p khi **khÃ´ng** cáº¯t lÃ¡ng giá»ng).
- **Default lá»‡ch YAML:** ItemKNN matrix `k=50` vs DataFrame `neighbors=20`; BPR `learning_rate` 0.05 vs 0.001; lÆ°á»›i tuning `[0.001, 0.005]` khÃ´ng thá»­ 0.05.
- **`Type1Agent`** khÃ´ng clamp `top_k` theo `max_candidates`: `top_k â‰¥ 201` (5 Ã— 201 > 1000) â‡’ lá»—i á»Ÿ bÆ°á»›c retrieve.

---

# 35. Snapshot 20/10 â€” `src(8).zip`

> Sá»‘ liá»‡u Ä‘á»c tá»« `experiments/agent_eval/*/metrics.json` vÃ  bÃ¡o cÃ¡o ablation, **khÃ´ng** cháº¡y láº¡i. Má»¥c 21 lÃ  snapshot má»›i hÆ¡n (27/10); chá»— nÃ o khÃ¡c nhau thÃ¬ Â§21 Ä‘Ãºng hÆ¡n.

## 35.1. Báº±ng chá»©ng cÃ³ trong zip

| NhÃ¡nh | Báº±ng chá»©ng | Káº¿t luáº­n Ä‘Æ°á»£c Ä‘áº¿n Ä‘Ã¢u |
|---|---|---|
| Offline recommender | `baselines/exp_001`â€“`exp_003`, `phase4_baselines/` | CÃ³ sá»‘ baseline cÅ©; chÆ°a chá»©ng minh káº¿t quáº£ má»›i hay nguyÃªn nhÃ¢n recall tháº¥p |
| Agent evaluation | `agent_eval/exp_002`â€“`exp_008` (requests / trajectories / scored / metrics) | PhÃ¢n tÃ­ch Ä‘Æ°á»£c theo kind Ã— segment; pháº£i ghi rÃµ config, n, loáº¡i request |
| Memory ablation | `ablation/memory_vs_no_memory/` | GhÃ©p cáº·p 146 request, nhÆ°ng **1 run/nhÃ³m** â‡’ chÆ°a cÃ³ phÆ°Æ¡ng sai |
| Reflection ablation | `ablation/planner_reflect0_vs_reflect1/`, `planner_memory_reflect0_vs_reflect1/` | NhÆ° trÃªn; thÃªm ná»¯a inference mode khÃ¡c nhau á»Ÿ 007/008 |
| Inference ablation | `planner_template_vs_llm/`, `planner_memory_template_vs_llm/`, `type1_template_vs_llm/` | LÃ  cháº¥t lÆ°á»£ng/chi phÃ­ **cÃ¢u tráº£ lá»i**, khÃ´ng pháº£i cháº¥t lÆ°á»£ng gá»£i Ã½ |
| Candidate retrieval | `candidate_recall/exp_001`â€“`exp_018` | 18 bá»™ artifact; pháº£i tá»•ng há»£p theo nguá»“n Ã— budget Ã— segment |
| Multi-turn | trajectory + request hiá»‡n cÃ³ | **KhÃ´ng Ä‘á»§** chá»©ng minh multi-turn |

## 35.2. Agent eval `exp_004`â€“`exp_008`

Dataset tag `multi_domain`, 2,76 triá»‡u user / 678.281 item, validation. `exp_004`â€“`006` khÃ¡c scope vá»›i `exp_007`â€“`008` nÃªn **khÃ´ng** gá»™p thÃ nh má»™t xu hÆ°á»›ng.

| Run | Cáº¥u hÃ¬nh | Request | Káº¿t quáº£ Ä‘Ã¡ng chÃº Ã½ | Giá»›i háº¡n |
|---|---|---:|---|---|
| `exp_004` | planner + planner_memory, realistic, template | 86 | `planner_memory` recall@10 0.1917 á»Ÿ `cold_text` (planner 0.0417); cáº£ hai 0.175 á»Ÿ `constrained`; 0 á»Ÿ `personalized`/`similar` | `cold_text`/`constrained` lÃ  ORACLE |
| `exp_005` | baseline + type1, realistic, template | 86 | `similar`: task success 1.0 nhÆ°ng recall@10 = 0 | task success khÃ´ng thay Ä‘Æ°á»£c relevance |
| `exp_006` | baseline + type1, cÃ¹ng scope | 86 | Láº·p láº¡i Ä‘Ãºng pattern cá»§a 005 | KhÃ´ng pháº£i láº·p Ä‘á»™c láº­p |
| `exp_007` | planner + planner_memory, `reflect_rounds=0`, inference LLM | 146 | `cold_text` recall 0.0667/0.0917; `constrained` 0.200/0.225; 0 á»Ÿ `personalized`/`similar` | ORACLE + 1 run |
| `exp_008` | 4 agent, `reflect_rounds=1`, inference template | 146 | `planner_memory` 0.0917 `cold_text`, 0.250 `constrained`; planner 0.0667 / 0.175 | KhÃ´ng pháº£i ablation cá»§a 007 (khÃ¡c inference mode + danh sÃ¡ch agent) |

**Äiá»ƒm cáº§n nháº¥n máº¡nh:** `task_success = 1.0` váº«n cÃ³ thá»ƒ Ä‘i cÃ¹ng `recall@10 = 0` â€” hai metric Ä‘o hai thá»© khÃ¡c nhau. `cold_text`/`constrained` láº¥y category/price tá»« item held-out â‡’ **ORACLE upper bound**, khÃ´ng bÃ¡o nhÆ° query tháº­t. `ambiguous` cÃ³ ground truth riÃªng: thÃ nh cÃ´ng = **há»i láº¡i**.

## 35.3. Reflection (20/10) â€” chÆ°a pháº£i so sÃ¡nh sáº¡ch

Hai cáº·p bÃ¡o cÃ¡o, 146 paired request, bootstrap 10.000, 95% â€” nhÆ°ng **1 run/nhÃ³m** (bÃ¡o cÃ¡o ghi "Only 1 run per group, cannot compute variance"). VÃ­ dá»¥ `planner_reflect0_vs_reflect1`, `cold_text` (n=20, ORACLE): task success 1.00 â†’ 0.85, recall@10 0.0667 â†’ 0.0417. KhÃ´ng Ä‘á»§ Ä‘á»ƒ nÃ³i reflection lÃ m tÄƒng **hay** giáº£m cháº¥t lÆ°á»£ng. Cáº·p so sÃ¡nh sáº¡ch Ä‘áº§u tiÃªn chá»‰ cÃ³ á»Ÿ **Â§21.3** (`exp_012` vs `exp_013`, cÃ¹ng inference mode).

## 35.4. Memory (20/10) â€” tÃ­n hiá»‡u cá»¥c bá»™

`memory_vs_no_memory` (146 paired request): `cold_text` recall@10 **+0.1500** (0.0417 â†’ 0.1917), NDCG@10 +0.0579; `constrained` khÃ´ng Ä‘á»•i (0.1750). ChÆ°a káº¿t luáº­n vÃ¬: ORACLE, `personalized`/`similar` váº«n recall 0, 1 run/nhÃ³m, chÆ°a kiá»ƒm cÃ¹ng request + snapshot. KhÃ´ng chá»n má»™t metric Ä‘áº¹p rá»“i suy rá»™ng.

## 35.5. Inference (20/10)

Ba bÃ¡o cÃ¡o `*_template_vs_llm` Ä‘Ã£ cÃ³. Inference **khÃ´ng chá»n item** â€” nÃ³ diá»…n Ä‘áº¡t láº¡i danh sÃ¡ch agent Ä‘Ã£ chá»n, nÃªn pháº£i bÃ¡o riÃªng 4 táº§ng: (1) recommendation quality (Recall/NDCG/candidate recall), (2) agent/tool behavior (plan valid, tool selection, first-attempt, reflections), (3) answer generation (grounding, fallback, latency, token), (4) task behavior (clarification, constraint). KhÃ´ng gá»™p thÃ nh má»™t Ä‘iá»ƒm "agent tá»‘t hÆ¡n".

## 35.6. Candidate recall â€” `candidate_recall/exp_018`

Run 1.000 user/segment, validation, 4.147 target interaction á»Ÿ segment cold. ÄÃ¢y lÃ  Recall cá»§a **candidate set trÆ°á»›c ranking**:

| Segment | Nguá»“n | Recall@50 | Recall@100 | Recall@200 |
|---|---|---:|---:|---:|
| cold | Popularity | 0.0153 | 0.0207 | 0.0345 |
| cold | ItemCF | 0.0000 | 0.0000 | 0.0000 |
| cold | Semantic | 0.0000 | 0.0000 | 0.0000 |
| cold | Union-RR / Union-all | 0.0153 | 0.0207 | 0.0345 |
| sparse | Popularity | 0.0166 | 0.0215 | 0.0355 |
| sparse | ItemCF | 0.0092 | 0.0102 | 0.0102 |
| sparse | Semantic | 0.0098 | 0.0116 | 0.0154 |
| sparse | Union-RR | 0.0155 | 0.0229 | 0.0324 |
| sparse | **Union-all** | **0.0286** | **0.0353** | **0.0520** |
| warm | Popularity | 0.0128 | 0.0179 | 0.0283 |
| warm | ItemCF | 0.0028 | 0.0090 | 0.0090 |
| warm | Semantic | 0.0053 | 0.0067 | 0.0106 |
| warm | Union-RR | 0.0105 | 0.0179 | 0.0235 |
| warm | **Union-all** | **0.0191** | **0.0292** | **0.0414** |

**Äá»c tháº­n trá»ng:** Union-all tá»‘t nháº¥t á»Ÿ sparse/warm (Recall@200 0.0520 vs 0.0355; 0.0414 vs 0.0283); á»Ÿ cold, ItemCF vÃ  Semantic tráº£ rá»—ng nÃªn union khÃ´ng cáº£i thiá»‡n Ä‘Æ°á»£c Popularity. Recall váº«n tháº¥p á»Ÿ cáº£ 3 segment â‡’ candidate generation cÃ³ thá»ƒ lÃ  nÃºt tháº¯t, **nhÆ°ng** pháº£i kiá»ƒm reachable target vÃ  evaluator trÆ°á»›c khi quy háº¿t lá»—i cho retrieval. ÄÃ¢y lÃ  1 run/seed.

## 35.7. Multi-turn â€” chÆ°a Ä‘á»§ báº±ng chá»©ng

`requests.jsonl` + `trajectories.jsonl` khÃ´ng tá»± chá»©ng minh multi-turn. Cáº§n: (a) request cÃ³ phá»¥ thuá»™c thÃ´ng tin lÆ°á»£t trÆ°á»›c, (b) agent nháº­n conversation state tháº­t, (c) scoring Ä‘o viá»‡c dÃ¹ng thÃ´ng tin qua lÆ°á»£t. Náº¿u má»—i request cháº¡y Ä‘á»™c láº­p thÃ¬ Ä‘Ã³ lÃ  **single-request evaluation**, dÃ¹ cÃ¢u chá»¯ lÃ  há»™i thoáº¡i.

## 35.8. Káº¿ hoáº¡ch experiment

ÄÃ£ thay báº±ng **Â§21.7** (Æ°u tiÃªn: láº·p `exp_012/013` Ä‘á»ƒ cÃ³ phÆ°Æ¡ng sai, cháº¡y láº¡i `memory_utility` trÃªn run cÃ¹ng cáº¥u hÃ¬nh, giáº£i thÃ­ch `recall@10 = 0` trÆ°á»›c khi tune planner).

---

# 36. Performance review (báº£n nÃ©n, 20/10)

> Static review Ä‘á»c tá»« code, **chÆ°a pháº£i benchmark runtime**. Ba loáº¡i "performance" pháº£i Ä‘o riÃªng: latency/runtime, recommendation quality, agent reliability â€” tá»‘i Æ°u latency **khÃ´ng** tá»± Ä‘á»™ng tÄƒng Recall@K.

## 36.1. Request cháº¡y qua Ä‘Ã¢u

```text
User request
  â”œâ”€ Type1Agent   ItemCFTool â†’ RecoModelTool â†’ QueryTool            (khÃ´ng LLM planning)
  â””â”€ PlanExecutor LLM plan â†’ validate tool/args â†’ resolve $N.path â†’ cháº¡y tool tuáº§n tá»±
                  â†’ reflect náº¿u lá»—i/rá»—ng â†’ AgentOutcome â†’ Inference (template | LLM + grounding)
Tools: Tool.__call__ (validation + logging + error contract) bá»c ItemCF / SemanticSearch /
       SQL / RecoModel / Query / Memory
Ná»n:   Recommender + ma tráº­n sparse | ItemCorpus (SQLite + FTS5) | user2id / item2id + interactions
```

## 36.2. Æ¯u tiÃªn phÃ¡t hiá»‡n tá»« code

| Æ¯u tiÃªn | Component | Quan sÃ¡t trá»±c tiáº¿p trong code | HÆ°á»›ng kiá»ƒm tra/tá»‘i Æ°u |
|---|---|---|---|
| **P0 â€” correctness** | `BaselineScorer.score` vs `ItemKNNMatrixRecommender.score_batch` | CÃ¡c implementation khÃ´ng thá»‘ng nháº¥t hÆ°á»›ng nhÃ¢n: `BaselineScorer.score` dÃ¹ng `history @ similarity`, cÅ©ng nhÆ° `BaselineItemKNNRecommender.recommend`; `ItemKNNMatrixRecommender.score_batch` láº¡i dÃ¹ng `history @ similarity.T`. VÃ¬ top-k truncation cÃ³ thá»ƒ lÃ m similarity báº¥t Ä‘á»‘i xá»©ng, káº¿t quáº£ ranking cÃ³ thá»ƒ khÃ¡c nhau khi Ä‘á»•i model implementation. | Viáº¿t test vá»›i ma tráº­n similarity báº¥t Ä‘á»‘i xá»©ng Ä‘á»ƒ khÃ³a contract cho tá»«ng recommender vÃ  báº£o Ä‘áº£m `RecoModelTool` Ä‘ang nháº­n Ä‘Ãºng loáº¡i scorer/model. KhÃ´ng tá»± Ã½ Ä‘á»•i transpose: `BaselineScorer` hiá»‡n cÃ³ váº» nháº¥t quÃ¡n vá»›i `BaselineItemKNNRecommender`, nhÆ°ng cáº§n xÃ¡c minh khi dÃ¹ng `ItemKNNMatrixRecommender` hoáº·c thay model family. |
| **P1 â€” hot path** | `Tool.__call__` / `ToolCallLogger` | Má»—i call hash toÃ n bá»™ kwargs báº±ng JSON; rá»“i táº¡o `len(str(result.data))`; logger giá»¯ má»i record trong list vÃ  cÃ³ thá»ƒ má»Ÿ file/append Ä‘á»“ng bá»™ á»Ÿ má»—i call. Vá»›i candidate list lá»›n, serialization/logging cÃ³ thá»ƒ tá»‘n thÃªm Ä‘Ã¡ng ká»ƒ. | Benchmark cÃ¹ng input vá»›i logger tá»‘i giáº£n/Ä‘áº§y Ä‘á»§; log `candidate_count`, `data_keys`, bytes Æ°á»›c lÆ°á»£ng thay vÃ¬ stringify toÃ n bá»™ output; cÃ¢n nháº¯c táº¯t retention in-memory hoáº·c batch file writes cho benchmark dÃ i. Giá»¯ hash náº¿u cáº§n traceability nhÆ°ng Ä‘o chi phÃ­. |
| **P1 â€” hot path** | `MemoryTool.execute` | Má»—i request lá»c toÃ n bá»™ `interactions` Ä‘á»ƒ tÃ¬m user; náº¿u cÃ³ timestamp láº¡i lá»c toÃ n frame trÆ°á»›c, sau Ä‘Ã³ lá»c user history thÃªm láº§n ná»¯a. ÄÃ¢y lÃ  O(N_interactions) scan láº·p láº¡i cho má»—i láº§n gá»i. | Tiá»n xá»­ lÃ½/index theo `user_idx` khi build tool, giá»¯ Ä‘Ãºng `as_of_timestamp`; Ä‘o memory tÄƒng thÃªm so vá»›i giáº£m latency. ThÃªm test leakage Ä‘á»ƒ chá»©ng minh history táº¡i cutoff khÃ´ng chá»©a tÆ°Æ¡ng tÃ¡c tÆ°Æ¡ng lai. |
| **P1 â€” hot path** | `BaselineScorer.score` + `has_personal_signal` | Scoring tÃ­nh `user_items.getrow(user_idx) @ similarity`; sau Ä‘Ã³ `RecoModelTool` gá»i `has_personal_signal`, phÃ©p nÃ y nhÃ¢n láº¡i cÃ¹ng user-history vá»›i similarity. | Sau khi xá»­ lÃ½ P0 vá» hÆ°á»›ng ma tráº­n, dÃ¹ng má»™t phÃ©p tÃ­nh per-user tÃ¡i sá»­ dá»¥ng trong cÃ¹ng request, hoáº·c tÃ­nh score trá»±c tiáº¿p cho candidates. TrÃ¡nh cache vÃ´ háº¡n náº¿u user cardinality lá»›n; benchmark cache theo request trÆ°á»›c. |
| **P1 â€” retrieval** | `SQLTool.execute` | Cháº¡y query láº¥y candidates rá»“i cháº¡y thÃªm `COUNT(*)` riÃªng qua `corpus.count`. CÃ¹ng Ä‘iá»u kiá»‡n lá»c cÃ³ thá»ƒ khiáº¿n SQLite quÃ©t/index lookup hai láº§n. | Äo riÃªng SELECT vÃ  COUNT theo filter. Náº¿u `total_matches` khÃ´ng cáº§n chÃ­nh xÃ¡c trong má»i request, thÃªm cháº¿ Ä‘á»™ khÃ´ng Ä‘áº¿m hoáº·c tráº£ total Ä‘Ã£ biáº¿t/truncated; Ä‘á»«ng Ã¢m tháº§m Ä‘á»•i contract vÃ¬ eval/UI Ä‘ang dÃ¹ng field nÃ y. |
| **P1 â€” retrieval** | `SemanticSearchTool.execute` | Cháº¡y FTS query Ä‘á»ƒ láº¥y candidates, sau Ä‘Ã³ cháº¡y thÃªm COUNT JOIN FTS/filters. `ORDER BY score DESC, rating_number DESC, item_id` cáº§n sort; BM25 vÃ  filter káº¿t há»£p quyáº¿t Ä‘á»‹nh chi phÃ­. | Äo query time vÃ  COUNT time riÃªng; thá»­ `EXPLAIN QUERY PLAN` trÃªn cÃ¡c query thá»±c táº¿; giá»¯ query an toÃ n báº±ng parameterized match/filter. So sÃ¡nh recall trÆ°á»›c khi Ä‘á»•i FTS query/filters. |
| **P1 â€” planner** | `PlanExecutor` | Má»™t request cÃ³ Ã­t nháº¥t má»™t LLM call; JSON lá»—i thÃ¬ retry; `reflect_rounds > 0` cÃ³ thá»ƒ thÃªm nhiá»u LLM call vÃ  cháº¡y láº¡i toÃ n bá»™ plan. `build_tool_prompt` serializes description + input/output schema cá»§a táº¥t cáº£ tools vÃ o system prompt má»—i plan. | Äo latency/tokens theo plan attempt, reflect, sá»‘ steps; giáº£m schema/prompt dÆ° thá»«a hoáº·c expose tools theo task náº¿u Ä‘Ã¡nh giÃ¡ chá»©ng minh khÃ´ng lÃ m giáº£m tool-selection accuracy. TrÆ°á»›c tiÃªn xem P95 vÃ  sá»‘ call thá»±c táº¿. |
| **P1 â€” candidate reach** | `ItemCFTool` / retrieval candidates | ItemCF chá»‰ cÃ³ top-k neighbors Ä‘Ã£ lÆ°u cho má»—i seed; lá»c domain sau khi tá»•ng há»£p, nÃªn cÃ³ thá»ƒ tráº£ Ã­t hÆ¡n `top_k`. `RecoModelTool` chá»‰ xáº¿p háº¡ng danh sÃ¡ch Ä‘áº§u vÃ o; khÃ´ng tá»± tÃ¬m item bá»‹ retriever bá» sÃ³t. | Candidate Recall@K theo tá»«ng retriever/segment lÃ  cá»•ng báº¯t buá»™c. TÄƒng `top_k` chá»‰ cÃ³ Ã­ch náº¿u candidate pool chá»©a target; theo dÃµi candidate count, duplicate rate, target reach. |
| **P2 â€” scoring** | `RecoModelTool.execute` | Táº¡o NumPy array candidate IDs, score toÃ n bá»™ candidate, rá»“i `argsort` toÃ n bá»™ danh sÃ¡ch Ä‘á»ƒ láº¥y `top_k`. | Náº¿u candidate pool thá»±c táº¿ lá»›n, dÃ¹ng partial top-k (`argpartition` + sort top-k) cÃ³ thá»ƒ giáº£m sorting; cáº§n tie-break á»•n Ä‘á»‹nh vÃ  test thá»© tá»±. Vá»›i giá»›i háº¡n candidates hiá»‡n táº¡i nhá», cÃ³ thá»ƒ chÆ°a Ä‘Ã¡ng lÃ m. |
| **P2 â€” model fit** | `ItemKNNMatrixRecommender._fit` | XÃ¢y similarity theo block nhÆ°ng má»—i block váº«n materialize ma tráº­n dense `(block_items, num_items)`; `block_elements` giá»›i háº¡n pháº§n tá»­, khÃ´ng pháº£i peak RSS toÃ n hÃ m. | Äo peak RAM vÃ  fit time theo catalog size; kiá»ƒm tra dtype trÆ°á»›c `toarray()`/`astype(float32)` Ä‘á»ƒ trÃ¡nh báº£n sao dÆ°; tÄƒng/giáº£m `block_elements` theo RAM thá»±c. KhÃ´ng Æ°u tiÃªn trÆ°á»›c correctness/latency request. |
| **P2 â€” eval** | `Recommender.recommend` / `evaluate_recommender` | Ranking full catalog cáº§n táº¡o score matrix cho batch user vÃ  sau Ä‘Ã³ chá»n top-k. Batch Ä‘Æ°á»£c giá»›i háº¡n qua `batch_elements`, nhÆ°ng cÃ³ thá»ƒ tá»‘n CPU/RAM. | Cháº¡y benchmark theo `num_users Ã— num_items`, theo dÃµi peak RAM; giáº£m batch khi OOM, tÄƒng batch chá»‰ khi throughput tÄƒng vÃ  RAM cÃ²n dÆ°. TÃ¡ch fit time khá»i eval time. |
| **P2 â€” final answer** | `compose_llm` | Khi mode LLM, answer generation lÃ  má»™t call ná»¯a; grounding/JSON lá»—i cÃ³ thá»ƒ kÃ­ch hoáº¡t retry, rá»“i template fallback. NÃ³ trÃ¬nh bÃ y items, khÃ´ng sá»­a ranking. | Náº¿u metric chÃ­nh lÃ  ranking, Ä‘Ã¡nh giÃ¡ `template` trÆ°á»›c Ä‘á»ƒ cÃ´ láº­p agent/retriever. Chá»‰ báº­t LLM inference khi Ä‘o answer quality, grounding, token cost vÃ  latency riÃªng. |

## 36.3. Tá»«ng tool: chi phÃ­, giá»›i háº¡n, hÆ°á»›ng tá»‘i Æ°u

|Tool|Chi phÃ­ chÃ­nh|Giá»›i háº¡n|Tá»‘i Æ°u há»£p lÃ½|
|---|---|---|---|
|`ItemCFTool`|tá»•ng non-zero similarity cá»§a cÃ¡c seed row + sort candidate há»£p nháº¥t|chá»‰ cÃ³ top-k neighbors Ä‘Ã£ lÆ°u; lá»c `domain` **sau** khi cáº¯t â‡’ cÃ³ thá»ƒ tráº£ Ã­t hÆ¡n `top_k`|Ä‘o candidate count/latency theo sá»‘ seed Ã— domain; khÃ´ng densify|
|`RecoModelTool`|O(C) map/filter + scorer + O(C log C) sort|chá»‰ xáº¿p háº¡ng candidate Ä‘áº§u vÃ o, khÃ´ng tÃ¬m item bá»‹ bá» sÃ³t; `unscored_item_ids` bá»‹ loáº¡i|partial top-k náº¿u C lá»›n; cache `seen_items` trong pháº¡m vi 1 request|
|`SemanticSearchTool`|FTS match + JOIN/filter + ORDER BY + **COUNT láº§n hai**|**lexical** (FTS5/BM25), khÃ´ng pháº£i embedding; query cáº§n tiáº¿ng Anh; category pháº£i exact|tÃ¡ch timing fetch/count; `EXPLAIN QUERY PLAN`; Ä‘o empty-result rate|
|`SQLTool`|2 query (SELECT + `COUNT(*)`)|`limit` khÃ´ng giáº£m chi phÃ­ sort/count|cháº¿ Ä‘á»™ `include_total=False` náº¿u caller khÃ´ng cáº§n; index theo query plan|
|`QueryTool`|1 query `IN (â€¦)` theo batch|tráº§n `MAX_QUERY_ROWS`; nhiá»u placeholder náº¿u list dÃ i|má»™t batch id list, khÃ´ng gá»i láº·p tá»«ng item|
|`MemoryTool`|scan/filter cáº£ DataFrame má»—i call + 2 query `IN (â€¦)`|category Ä‘áº¿m theo interaction (1 category láº·p nhiá»u láº§n)|index history theo user lÃºc build (giá»¯ cutoff); benchmark build-time vs per-call|
|`Tool.__call__`|hash kwargs báº±ng JSON + `len(str(data))` + logger giá»¯ má»i record + append file má»—i call|chi phÃ­ tÄƒng theo kÃ­ch thÆ°á»›c candidate list|summary cÃ³ cáº¥u trÃºc (`candidate_count`, `n_keys`); logger `off/basic/full`; batch writes|

## 36.4. Agent / framework

- **`PlanExecutor`**: â‰¥ 1 LLM call má»—i request; JSON lá»—i thÃ¬ retry; `reflect_rounds > 0` thÃªm call + cháº¡y láº¡i plan. Äo `first_attempt_ok`, `reflections`, `plan_attempts`, `n_steps`, latency/token theo tá»«ng attempt.
- **`build_tool_prompt`**: description + input/output schema cá»§a **má»i** tool vÃ o system prompt â‡’ context cost. Äo prompt tokens; náº¿u compact theo intent thÃ¬ pháº£i kiá»ƒm `tool_selection_ok` vÃ  Ä‘á»«ng xoÃ¡ field cáº§n cho ref `$N.path`.
- **`Type1Agent`**: deterministic, khÃ´ng tá»‘n LLM planning, dá»… benchmark â€” nhÆ°ng chá»‰ ItemCF + seed, cold/seed rá»—ng lÃ  fail sá»›m.
- **`extract_recommendations`**: Æ°u tiÃªn `ranked` > retrieval > `QueryTool` â‡’ Ä‘á»c `tool_selection_ok`/`n_steps`, khÃ´ng chá»‰ "list cÃ³ rá»—ng hay khÃ´ng".
- **Inference**: template Ä‘á»ƒ cÃ´ láº­p agent/retriever; chá»‰ báº­t LLM khi Ä‘o answer quality + grounding + token/latency.
- **Provider**: `urllib` Ä‘á»“ng bá»™, khÃ´ng batch/async; má»i so sÃ¡nh pháº£i ghi model, base_url, timeout, retries, tokens.

## 36.5. Model / data / evaluation

- **ItemKNN fit:** má»—i block váº«n materialize ma tráº­n dense `(block_items, num_items)` â€” `block_elements` khÃ´ng pháº£i peak RSS. Äo fit time + peak RAM + nnz.
- **Offline eval:** `Recommender.recommend` cháº¥m toÃ n catalog theo batch, khÃ¡c `RecoModelTool` (rank subset) â‡’ **khÃ´ng** dÃ¹ng timing offline lÃ m latency online.
- **Cháº©n Ä‘oÃ¡n theo báº­c:** candidate recall tháº¥p â†’ retriever/query/seed; candidate recall tá»‘t mÃ  Recall@10 tháº¥p â†’ scorer/seen/mapping/split; ranking tá»‘t mÃ  task success tháº¥p â†’ constraint/tool lá»—i; task success cao mÃ  Recall@10 = 0 â†’ metric success khÃ´ng Ä‘áº¡i diá»‡n relevance.

## 36.6. Protocol benchmark (trÆ°á»›c khi sá»­a code)

Ghi Ä‘á»§: commit/hash + config snapshot + fingerprint dataset/split; model/scorer, seed, `top_k`, segment, request IDs cá»‘ Ä‘á»‹nh; warm-up + sá»‘ láº§n láº·p + median/P95 (khÃ´ng chá»‰ mean) + peak RAM; per-request `wall_seconds`, per-step tool name/ok/latency, LLM calls/tokens, reflection/retry counts; candidate count trÆ°á»›c/sau filter, `unscored_item_ids`, target-in-candidates; **cÃ¹ng má»™t táº­p request** cho before/after (khÃ´ng trá»™n Ä‘á»•i prompt + model + split + tool trong má»™t ablation).

## 36.7. Bá»‘n Ä‘á»£t tá»‘i Æ°u

1. **Äá»£t 0 â€” baseline, khÃ´ng Ä‘á»•i behavior:** cháº¡y táº­p request cá»‘ Ä‘á»‹nh, lÆ°u trajectory + tool log; bÃ¡o median/P95 theo agent Ã— kind Ã— segment; ghi cáº£ candidate reach + ranking metrics.
2. **Äá»£t 1 â€” correctness trÆ°á»›c tá»‘c Ä‘á»™:** test ma tráº­n báº¥t Ä‘á»‘i xá»©ng Ä‘á»ƒ khoÃ¡ convention `BaselineScorer` / `BaselineItemKNNRecommender` / `ItemKNNMatrixRecommender`; kiá»ƒm mapping id, exclude-seen, unknown, cold start; xá»­ lÃ½ segment cÃ³ Recall@K = 0 trÆ°á»›c khi tune.
3. **Äá»£t 2 â€” hot path cÃ³ báº±ng chá»©ng:** logger on/off/basic; index `MemoryTool` theo user; bá» phÃ©p nhÃ¢n sparse láº·p giá»¯a `score` vÃ  `has_personal_signal`; tuá»³ chá»n bá» COUNT; chá»‰ sau Ä‘Ã³ má»›i tá»›i partial top-k / prompt compression.
4. **Äá»£t 3 â€” quality cÃ³ ablation:** so Popularity / ItemCF / Semantic / SQL / union theo Recall@50/100/200 + latency; tÄƒng pool chá»‰ khi candidate recall cÃ²n room; tune ranker sau khi target reach Ä‘Æ°á»£c.

## 36.8. Káº¿t luáº­n

Äá»«ng tá»‘i Æ°u táº¥t cáº£ tool cÃ¹ng lÃºc: **xÃ¡c minh correctness cá»§a scorer trÆ°á»›c**, rá»“i Ä‘o vÃ  giáº£m overhead trong `Tool.__call__`/logger vÃ  `MemoryTool`, sau Ä‘Ã³ profile COUNT vÃ  planner LLM call. Song song, candidate recall quyáº¿t Ä‘á»‹nh tráº§n cháº¥t lÆ°á»£ng cá»§a ranker. Má»i cáº£i tiáº¿n pháº£i bÃ¡o **cáº£ latency láº«n quality**.

> Checklist "sá»­a ngay / chÆ°a nÃªn sá»­a" vÃ  20.9 chi tiáº¿t Ä‘Ã£ bá» khi tinh gá»n 30/10; ná»™i dung Ä‘Ã£ gá»™p vÃ o 4 Ä‘á»£t á»Ÿ 20.7.

---

# 37. Snapshot artifact 27/10 â€” `exp_009`â€“`exp_013`, ablation, component benchmark

> **Pháº¡m vi:** cÃ¡c artifact trong `experiments/agent_eval/` sinh ngÃ y **26â€“27/10**, Ä‘á»c ngÃ y **29/10**. Sá»‘ liá»‡u láº¥y trá»±c tiáº¿p tá»« `config.yaml`, `metrics.json`, `scored.jsonl`, `ablation/*/report.md` + `comparison.json`, `component_benchmarks/*.json`, `memory_utility_analysis/memory_utility.md`. **KhÃ´ng** pháº£i tÃ´i cháº¡y láº¡i experiment. Má»¥c 19â€“20 (snapshot 20/10) giá»¯ nguyÃªn Ä‘á»ƒ Ä‘á»‘i chiáº¿u lá»‹ch sá»­; chá»— nÃ o khÃ¡c nhau thÃ¬ má»¥c nÃ y má»›i hÆ¡n.

## 37.1. NÄƒm run agent_eval má»›i â€” cáº¥u hÃ¬nh thá»±c táº¿

| Run | Thá»i Ä‘iá»ƒm (UTC) | Commit | `reflect_rounds` | `inference_mode` | `per_segment` | `n_requests` | runtime |
|---|---|---|---|---|---|---|---|
| `exp_009` | 26/10 09:35 | `ec14e6d` | 0 | template | 15 | 66 | 851 s |
| `exp_010` | 26/10 10:09 | `ec14e6d` | 1 | template | 15 | 66 | 961 s |
| `exp_011` | 27/10 09:39 | `7828141` | 1 | llm | 2 | 14 | 571 s |
| `exp_012` | 27/10 10:16 | `7828141` | 0 | llm | 15 | 66 | 2.203 s |
| `exp_013` | 27/10 11:05 | `7828141` | 1 | llm | 15 | 66 | 2.339 s |

Chung cho cáº£ 5 run: `eval_on=validation`, `seed=42`, `k=10`, `request_scope=realistic`, `sparse_max=4`, `item_knn_k=20`, `llm_model=gpt-5.4`, agent `baseline / type1 / planner / planner_memory`.

Ba Ä‘iá»ƒm dá»… Ä‘á»c sai:

- **KhÃ´ng cÃ²n kind ORACLE.** `request_scope=realistic` â‡’ chá»‰ cÃ³ `personalized` (30), `similar` (30), `ambiguous` (6); **khÃ´ng cÃ³ `constrained` / `cold_text`**. VÃ¬ váº­y má»i so sÃ¡nh ORACLE á»Ÿ má»¥c 19 (exp_004/007/008) khÃ´ng ná»‘i tiáº¿p Ä‘Æ°á»£c vá»›i loáº¡t run nÃ y.
- **`exp_011` lÃ  smoke run** (`per_segment=2` â‡’ 4 request/kind, 14 request), Ä‘á»«ng so trá»±c tiáº¿p vá»›i run 66 request.
- **26/10 â‰  27/10 vá» artifact:** `mapping_hash` cá»§a `exp_009/010` lÃ  `13e3e5b3â€¦`, cá»§a `exp_011â€“013` lÃ  `1160c09bâ€¦`; tá»« 27/10 má»›i cÃ³ `mapping_hash_protocol: sorted_key_index_json_v1` vÃ  `sha256` cho tá»«ng split (`train/validation/test` giá»‘ng nhau giá»¯a 011â€“013). KhÃ´ng gá»™p hai nhÃ³m nÃ y thÃ nh má»™t chuá»—i.

## 37.2. `personalized` (n = 30 má»—i Ã´) â€” nÆ¡i khÃ¡c biá»‡t náº±m á»Ÿ Ä‘Ã¢u

| Run (reflect / inference) | Agent | recall@10 | task_success | first_attempt_ok | reflections | steps_ok_rate | answer_status_ok | answer_status_tool_error | wall p50 (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `exp_009` (0 / template) | `planner` | 0.000 | â€” | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.44 |
| `exp_009` (0 / template) | `planner_memory` | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.31 |
| `exp_010` (1 / template) | `planner` | 0.000 | â€” | 1.000 | 0.000 | 1.000 | 0.967 | 0.000 | 6.46 |
| `exp_010` (1 / template) | `planner_memory` | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 6.46 |
| `exp_012` (0 / llm) | `planner` | 0.000 | â€” | 0.400 | 0.000 | 0.600 | 0.400 | 0.600 | 5.85 |
| `exp_012` (0 / llm) | `planner_memory` | 0.000 | 0.400 | 0.400 | 0.000 | 0.577 | 0.533 | 0.467 | 5.49 |
| `exp_013` (1 / llm) | `planner` | 0.000 | â€” | 0.567 | 0.433 | 0.949 | 0.800 | 0.067 | 5.50 |
| `exp_013` (1 / llm) | `planner_memory` | 0.000 | 0.933 | 0.500 | 0.500 | 0.964 | 0.967 | 0.033 | 8.66 |

Ã” `task_success = â€”` cá»§a `planner` **khÃ´ng pháº£i lá»—i dá»¯ liá»‡u**: `score_trajectory.py:66-70` chá»§ Ä‘á»™ng Ä‘áº·t `task_success = tool_selection_ok = None` cho `personalized` + planner **khÃ´ng cÃ³** `MemoryTool`, vÃ¬ planner Ä‘Ã³ khÃ´ng cÃ³ cÃ¡ch cÃ¡ nhÃ¢n hoÃ¡ trung thá»±c (há»i láº¡i váº«n Ä‘Æ°á»£c coi lÃ  há»£p lá»‡). Há»‡ quáº£: muá»‘n nÃ³i vá» memory trÃªn `personalized` thÃ¬ pháº£i so `planner_memory` vá»›i baseline, hoáº·c cháº¥p nháº­n Ã´ `planner` bá»‹ bá» trá»‘ng.

- `similar` (n = 30) vÃ  `ambiguous` (n = 6): `task_success` = 1.000 cho má»i agent á»Ÿ cáº£ 5 run; `ambiguous` cÃ³ `asked_clarification` = 1.000; `recall@10` = 0.000 á»Ÿ má»i Ã´ `similar`.
- **`recall@10` vÃ  `ndcg@10` = 0.000 á»Ÿ *toÃ n bá»™* 5 run**, ká»ƒ cáº£ `baseline` vÃ  `type1`. ÄÃ¢y váº«n lÃ  váº¥n Ä‘á» cá»§a Â§19.6 chá»© khÃ´ng pháº£i phÃ¡t hiá»‡n má»›i, nhÆ°ng nÃ³ cÃ³ nghÄ©a: **khÃ´ng thá»ƒ dÃ¹ng loáº¡t run nÃ y Ä‘á»ƒ so cháº¥t lÆ°á»£ng gá»£i Ã½**; chá»‰ so Ä‘Æ°á»£c hÃ nh vi agent (plan, step, tool, answer).

## 37.3. Reflection: cáº·p so sÃ¡nh **sáº¡ch** Ä‘áº§u tiÃªn â€” `exp_012` vs `exp_013`

ÄÃ¢y lÃ  Ä‘iá»ƒm má»›i quan trá»ng nháº¥t cá»§a loáº¡t artifact nÃ y. Má»¥c 19 tá»«ng káº¿t luáº­n "chÆ°a cÃ³ ablation reflection sáº¡ch" vÃ¬ `exp_007`/`exp_008` khÃ¡c inference mode. `exp_012` vÃ  `exp_013` **giá»‘ng nhau má»i thá»©** (cÃ¹ng commit, cÃ¹ng split + `mapping_hash`, cÃ¹ng 66 request, `inference_mode=llm`, `seed=42`), chá»‰ khÃ¡c `reflect_rounds` 0 â†’ 1. BÃ¡o cÃ¡o: `ablation/planner_reflect0_vs_reflect1/` (66 paired requests, bootstrap 10.000, 95%).

| `personalized` (n = 30) | `exp_012` (r0) | `exp_013` (r1) | Diff | 95% CI |
|---|---:|---:|---:|---|
| `first_attempt_ok` | 0.400 | 0.567 | **+0.167** | [âˆ’0.133, +0.467] â€” McNemar b=8, c=13, **p = 1.000** |
| `reflections` | 0.000 | 0.433 | +0.433 | [+0.267, +0.600] |
| `steps_ok_rate` | 0.600 | 0.949 | +0.349 | (tá»« `metrics.json`) |
| `answer_status_ok` | 0.400 | 0.800 | +0.400 | (tá»« `metrics.json`) |
| `answer_status_tool_error` | 0.600 | 0.067 | **âˆ’0.533** | (tá»« `metrics.json`) |
| `llm_latency_seconds` | 5.98 | 7.41 | **+1.43 s** | [+0.226, +2.643] |
| `completion_tokens` | 346.0 | 457.9 | +111.9 | [+17.6, +208.0] |
| `inference_latency_seconds` | 3.29 | 5.82 | **+2.53 s** | [+0.578, +4.329] |
| `inference_completion_tokens` | 304.7 | 579.8 | +275.1 | [+88.6, +441.3] |

á»ž `similar` vÃ  `ambiguous` hai run gáº§n nhÆ° trÃ¹ng nhau (`first_attempt_ok` = 1.000 cáº£ hai; `llm_latency` 4.43 â†’ 4.19 s á»Ÿ `similar`, 3.25 â†’ 3.85 s á»Ÿ `ambiguous`).

**Äá»c tháº¿ nÃ o cho Ä‘Ãºng:**

1. CÃ³ **tÃ­n hiá»‡u rÃµ** ráº±ng reflection sá»­a Ä‘Æ°á»£c lá»—i tool á»Ÿ `personalized`: 60% request lá»—i á»Ÿ láº§n Ä‘áº§u (r0) xuá»‘ng cÃ²n 6,7% (r1); 43% request thá»±c sá»± pháº£i reflect.
2. **ChÆ°a pháº£i báº±ng chá»©ng thá»‘ng kÃª:** má»—i nhÃ³m chá»‰ **1 run** (bÃ¡o cÃ¡o ghi "Only 1 run per group, cannot compute variance"), n = 30, vÃ  McNemar cho `first_attempt_ok` ra **p = 1.000** â€” tá»©c chÆ°a Ä‘á»§ Ä‘á»ƒ káº¿t luáº­n.
3. **GiÃ¡ pháº£i tráº£:** +1,4 s planner latency vÃ  +2,5 s inference latency má»—i request `personalized`, cá»™ng thÃªm ~390 completion tokens.
4. Reflection **khÃ´ng** cáº£i thiá»‡n `recall@10` (váº«n 0.000 á»Ÿ má»i Ã´) â€” nÃ³ sá»­a *cÃ¡ch cháº¡y*, khÃ´ng sá»­a *cháº¥t lÆ°á»£ng gá»£i Ã½*.

## 37.4. Memory: `planner_memory` vs `planner` trÃªn cÃ¹ng run

**Trong `exp_013`** (`ablation/memory_vs_no_memory/`, cÃ¹ng 66 request):

- `similar`: hai agent **giá»‘ng há»‡t** (`task_success` 1.000, `first_attempt_ok` 1.000, `recall@10` 0.000). Chi phÃ­ cá»§a memory: `llm_latency` 4.357 â†’ 6.351 s á»Ÿ segment `warm` (+1.99 s), `answer_fallback` 0 â†’ 0.033.
- `personalized`: `planner` **khÃ´ng Ä‘Æ°á»£c cháº¥m** `task_success` (má»¥c 21.2) nÃªn chá»‰ so Ä‘Æ°á»£c hÃ nh vi: `first_attempt_ok` 0.567 vs 0.500; `steps_ok_rate` 0.949 vs 0.964; `answer_status_ok` 0.800 vs **0.967**; `answer_status_tool_error` 0.067 vs **0.033**; `wall p50` 5.50 s vs 8.66 s. `planner_memory` cÃ³ `task_success` = 0.933.
- Contrast nÃ y **bá» sÃ³t `personalized`**: `configs/agent/ablation.yaml` khai bÃ¡o `memory_vs_no_memory.kinds: [similar, constrained, cold_text]`, mÃ  `constrained`/`cold_text` khÃ´ng tá»“n táº¡i trong run realistic â‡’ bÃ¡o cÃ¡o chá»‰ cÃ²n `similar`, Ä‘Ãºng loáº¡i request mÃ  memory khÃ´ng thá»ƒ giÃºp gÃ¬.

**Trong `planner_memory_reflect0_vs_reflect1`** (r0 vs r1, cÃ¹ng `exp_012`/`exp_013`): `personalized` lÃ  nÆ¡i duy nháº¥t thay Ä‘á»•i máº¡nh â€” `task_success` 0.333 â†’ 0.933 á»Ÿ segment `sparse` (+0.600) vÃ  0.467 â†’ 0.933 á»Ÿ `warm` (+0.467); `llm_latency` +3.42 s / +2.19 s. CÆ¡ cháº¿ khá»›p vá»›i 21.3: `task_success` (v2) Ä‘Ã²i `answer_status = ok` **vÃ ** grounded, nÃªn sá»­a lá»—i tool báº±ng reflection lÃ  Ä‘iá»u kiá»‡n Ä‘á»ƒ Ã´ nÃ y cÃ³ Ä‘iá»ƒm.

**`memory_utility_analysis/`** (sinh 27/10 09:16) lÃ  phÃ¢n tÃ­ch ghÃ©p cáº·p 3 run/arm, bootstrap 5.000, `min_n = 20` â€” nhÆ°ng trÃªn **run cÅ© 20 request** (6 ORACLE + 14 realistic; `docs/evaluation/FINAL_SUMMARY.md` ghi lÃ  `exp_002`â€“`exp_004`), **khÃ´ng pháº£i** `exp_012/013`. Káº¿t quáº£: **má»i nhÃ³m Ä‘á»u `inconclusive`** vÃ¬ n < 20. VÃ i con sá»‘ Ä‘á»ƒ tham kháº£o, khÃ´ng Ä‘á»ƒ trÃ­ch dáº«n nhÆ° káº¿t luáº­n:

| Metric | Realistic (n=14) | Personalized (n=4) |
|---|---|---|
| `task_success` | 0.857 â†’ 0.929 (+0.071, CI [0.000, +0.214]) | 0.500 â†’ 0.750 (+0.250, CI [0.000, +0.750]) |
| `recall@10` | 0.000 â†’ 0.000 | 0.000 â†’ 0.000 |
| `llm_latency_seconds` | 12.25 â†’ 11.43 | 13.24 â†’ 15.04 |

â‡’ Káº¿t luáº­n trung thá»±c: **chÆ°a cÃ³ báº±ng chá»©ng memory cáº£i thiá»‡n cháº¥t lÆ°á»£ng**; chá»‰ cÃ³ tÃ­n hiá»‡u vá» hÃ nh vi/Ä‘á»™ trá»…, vÃ  má»i verdict Ä‘á»u `inconclusive`.

**Cháº¡y láº¡i `memory_utility.py` trÃªn 2 run má»›i (29/10)** â€” lá»‡nh: `--dirs experiments/agent_eval/exp_012 experiments/agent_eval/exp_013 --min-n 20 --resamples 5000` (66 request, **2 run/arm**, output ghi ra ngoÃ i repo):

| Metric | `realistic` (n = 66) | `personalized` (n = 30) | verdict |
|---|---|---|---|
| `task_success` | +0.000 [+0.000, +0.000] | **`no_pairs`** â€” planner khÃ´ng cháº¥m, `unscored` 30/0 | inconclusive / no_pairs |
| `recall@10`, `ndcg@10` | +0.000 (30 cáº·p) | +0.000 (30 cáº·p) | inconclusive |
| `first_attempt_ok` | âˆ’0.015 [âˆ’0.098, +0.068] | âˆ’0.033 [âˆ’0.217, +0.150] | inconclusive |
| `completion_tokens` | +7.3 [âˆ’18.6, +33.7] | +6.2 [âˆ’50.3, +63.7] | inconclusive |
| `llm_latency_seconds` | +0.323 [âˆ’0.272, +1.073] | +0.206 [âˆ’0.628, +1.049] | inconclusive |
| `constraint_satisfaction` | `no_pairs` (66/66) | `no_pairs` (30/30) | â€” |

Tá»•ng: **1 `memory_worse`, 46 `inconclusive`, 16 `no_pairs`**. Verdict duy nháº¥t: `completion_tokens` á»Ÿ `similar` +11,3 token [+2,75, +19,98] (W/L/T 22/7/1) â€” memory **tá»‘n token hÆ¡n** ngay cáº£ á»Ÿ loáº¡i request mÃ  nÃ³ khÃ´ng giÃºp gÃ¬.

> **Cáº£nh bÃ¡o phÆ°Æ¡ng phÃ¡p:** hai run nÃ y khÃ¡c `reflect_rounds` (0 vs 1), nÃªn bÆ°á»›c "trung bÃ¬nh qua cÃ¡c run" Ä‘ang trá»™n **hai Ä‘iá»u kiá»‡n**; cá»™t `run-std` vÃ¬ tháº¿ pháº£n Ã¡nh hiá»‡u á»©ng reflection chá»© khÃ´ng pháº£i nhiá»…u LLM. `memory_utility.py` **khÃ´ng** kiá»ƒm tra tÆ°Æ¡ng thÃ­ch config giá»¯a cÃ¡c run (khÃ¡c `ablation/_loader.check_compatibility`). VÃ¬ váº­y láº§n cháº¡y nÃ y chá»‰ dÃ¹ng Ä‘á»ƒ **kiá»ƒm tra pipeline cháº¡y Ä‘Ãºng**, khÃ´ng dÃ¹ng Ä‘á»ƒ káº¿t luáº­n vá» memory.

## 37.5. Component benchmark â€” `experiments/agent_eval/component_benchmarks/`

Sá»‘ dÆ°á»›i Ä‘Ã¢y láº¥y tá»« file **má»›i nháº¥t** cá»§a tá»«ng component (26â€“27/10), `run_count` ghi trong file.

| Component | File | Cases | Runs | Metric chÃ­nh | Latency |
|---|---|---:|---:|---|---|
| `memory` (fixture) | `memory_benchmark_20261027_114412.json` | 16 | 3 | `known_correct` 0.188, `n_interactions_correct` 0.188, `price_range_correct` 0.313, `recent_items_match` 0.250, `top_categories_match` 0.250 | ~0 |
| `memory_correctness` (oracle) | `memory_correctness_current.json` | 16 | 1 | `all_fields_match` 1.000, `error_behavior_correct` 1.000, `future_leakage` **0.000** (khÃ´ng rÃ²) | ~1 ms |
| `planner` (LLM tháº­t) | `planner_benchmark_20261027_084904.json` | 4 | 1 | `plan_validity` 1.000, `tool_selection_accuracy` 0.500, `argument_correctness` **0.375**, `constraint_handling` 0.500, `reference_correctness` 0.750, `clarification_precision` 0.500 / `recall` 0.750 | mean **5.29 s**, p95 7.84 s |
| `executor` + reflection | `executor_benchmark_20261027_084905.json` | 5 | 1 | `all_steps_ok` 0.600, `reflection_triggered` 0.400, `reflection_rescued` **0.000**, `reflection_worsened` 0.000, `reflection_no_change` 1.000 | ~0.1 ms |
| `grounding` (rule-based) | `grounding_benchmark_20261027_084906.json` | 5 | 1 | `grounding_rate` 0.800, `hallucination_rate` 0.200, `prompt_injection_detected` 0.200 | ~0 |
| `integration` | `integration_benchmark_20261027_114417.json` | 7 | 3 | `contract_valid` 0.571, `no_mismatch` 0.571 | ~0 |

Ba Ä‘iá»u cáº§n biáº¿t khi Ä‘á»c báº£ng nÃ y:

- **Hai benchmark memory cho káº¿t quáº£ trÃ¡i ngÆ°á»£c** (0.188 vs 1.000) vÃ¬ Ä‘o hai thá»© khÃ¡c nhau: `memory_benchmark` so vá»›i **fixture ká»³ vá»ng** trong `memory_correctness_dataset.jsonl`, cÃ²n `memory_correctness` so vá»›i **oracle Ä‘á»™c láº­p** (`memory_oracle.py`, khÃ´ng import `MemoryTool`/`ItemCorpus`). ChÃªnh lá»‡ch nÃ y **chÆ°a Ä‘Æ°á»£c Ä‘iá»u tra** â€” cÃ³ thá»ƒ fixture sai, cÃ³ thá»ƒ hai bÃªn hiá»ƒu khÃ¡c nhau vá» `recent_items`/`top_categories`. Äá»«ng trÃ­ch "memory Ä‘Ãºng 100%" mÃ  bá» qua Ã´ 0.188 (vÃ  ngÆ°á»£c láº¡i).
- **`run_all.py` chÆ°a gom Ä‘Æ°á»£c Ä‘á»§ 5 component:** `unified_report_20261027_184417.md` ghi 2/5 success, cÃ²n `planner` / `executor` / `grounding` lÃ  "Benchmark did not run". CÃ¡c file benchmark riÃªng cá»§a 3 component Ä‘Ã³ **váº«n cÃ³** (báº£ng trÃªn), nÃªn Ä‘Ã¢y lÃ  lá»—i cá»§a bÆ°á»›c tá»•ng há»£p, chÆ°a pháº£i lá»—i benchmark.
- TÃ¡c giáº£ Ä‘Ã£ tá»± tá»•ng há»£p trong `docs/evaluation/FINAL_SUMMARY.md` + 6 file theo phase; cÃ¡c "missing parts" Ä‘Æ°á»£c ghi á»Ÿ Ä‘Ã³ váº«n Ä‘Ãºng: **Jev cáº§n Typesafe API key** (OpenRouter key tráº£ 401), **reflection cáº§n LLM tháº­t** (mock LLM khÃ´ng táº¡o Ä‘Æ°á»£c plan sá»­a), **sample size 4â€“16 case** lÃ  quÃ¡ nhá».

## 37.6. CÃ¡i gÃ¬ Ä‘Ã£ chá»©ng minh Ä‘Æ°á»£c, cÃ¡i gÃ¬ chÆ°a

| Nháº­n Ä‘á»‹nh | Báº±ng chá»©ng trong artifact | Tráº¡ng thÃ¡i |
|---|---|---|
| Reflection sá»­a Ä‘Æ°á»£c lá»—i tool á»Ÿ `personalized` | `exp_012` vs `exp_013`: `answer_status_tool_error` 0.600 â†’ 0.067; `steps_ok_rate` 0.600 â†’ 0.949 | **TÃ­n hiá»‡u máº¡nh**, nhÆ°ng 1 run/nhÃ³m, n = 30, McNemar p = 1.000 â†’ chÆ°a káº¿t luáº­n |
| Reflection lÃ m agent "gá»£i Ã½ tá»‘t hÆ¡n" | `recall@10` = 0.000 á»Ÿ cáº£ hai run | **KhÃ´ng** â€” khÃ´ng cÃ³ báº±ng chá»©ng |
| Memory cáº£i thiá»‡n cháº¥t lÆ°á»£ng gá»£i Ã½ | `memory_utility_analysis` má»i nhÃ³m `inconclusive`; `recall@10` = 0 | **ChÆ°a chá»©ng minh** |
| Memory lÃ m cÃ¢u tráº£ lá»i á»•n Ä‘á»‹nh hÆ¡n | `answer_status_ok` 0.800 â†’ 0.967 vÃ  `tool_error` 0.067 â†’ 0.033 (`exp_013`, `personalized`) | TÃ­n hiá»‡u, cÃ¹ng run, chÆ°a láº·p |
| Agent > baseline vá» recommendation | `baseline`/`type1`/`planner` Ä‘á»u `recall@10` = 0 á»Ÿ `similar` | **KhÃ´ng thá»ƒ káº¿t luáº­n** â€” metric chÆ°a phÃ¢n biá»‡t Ä‘Æ°á»£c |
| Tá»«ng component cháº¡y Ä‘Ãºng há»£p Ä‘á»“ng | planner `plan_validity` 1.000 nhÆ°ng `argument_correctness` 0.375; integration `contract_valid` 0.571 | **Má»™t pháº§n** â€” cÃ²n lá»—i há»£p Ä‘á»“ng cá»¥ thá»ƒ |
| Há»‡ thá»‘ng eval Ä‘Ã£ Ä‘á»§ tin Ä‘á»ƒ viáº¿t káº¿t quáº£ | 10 test Ä‘á» (má»¥c 12), `run_all` 2/5 component, Jev 401, ORACLE kind bá»‹ bá» khá»i run má»›i | **ChÆ°a** |

## 37.7. Viá»‡c tiáº¿p theo (Ä‘á» xuáº¥t, theo thá»© tá»±)

1. **Láº·p `exp_012`/`exp_013` â‰¥ 3 láº§n** Ä‘á»ƒ cÃ³ phÆ°Æ¡ng sai cho cÃ¢u "reflection giáº£m lá»—i tool" â€” **cáº§n LLM tháº­t** (`LLM_BASE_URL` + `LLM_API_KEY`), má»—i run ~37â€“39 phÃºt nÃªn 3+3 run â‰ˆ 4 giá»; **chÆ°a cháº¡y Ä‘Æ°á»£c á»Ÿ mÃ´i trÆ°á»ng hiá»‡n táº¡i** (ba biáº¿n `LLM_*` Ä‘á»u rá»—ng). Lá»‡nh (Ä‘Ã£ kiá»ƒm qua `--help`): `python scripts/evaluation/run_agent_eval.py --reflect-rounds 0 --inference-mode llm --trajectory-file agent_llm_r0_rep2.jsonl`, láº·p láº¡i vá»›i `--reflect-rounds 1`; má»—i láº§n tá»± sinh `exp_NNN` má»›i.
2. **`memory_utility.py`**: pipeline Ä‘Ã£ cháº¡y Ä‘Æ°á»£c (29/10 â€” báº£ng á»Ÿ 21.4) nhÆ°ng trÃªn 2 run **khÃ¡c Ä‘iá»u kiá»‡n**, nÃªn chá»‰ Ä‘á»ƒ kiá»ƒm tra cÃ´ng cá»¥; muá»‘n káº¿t luáº­n cáº§n â‰¥ 3 run **cÃ¹ng cáº¥u hÃ¬nh**. Äá»“ng thá»i **thÃªm `personalized`** vÃ o `memory_vs_no_memory.kinds` (hiá»‡n chá»‰ cÃ²n `similar`) vÃ  nÃªn bá»• sung kiá»ƒm tra tÆ°Æ¡ng thÃ­ch config nhÆ° `ablation/_loader.check_compatibility`.
3. **Tráº£ lá»i "vÃ¬ sao recall@10 = 0"** trÆ°á»›c khi tune planner: cháº¡y `diagnose_splits.py` + `candidate_recall.py` trÃªn Ä‘Ãºng split Ä‘Ã£ dÃ¹ng cho `exp_012/013` vÃ  lÆ°u JSON.
4. **Sá»­a `run_all.py`** Ä‘á»ƒ report gom Ä‘á»§ 5 component (hiá»‡n 3 component bÃ¡o "Benchmark did not run"), vÃ  nÃ¢ng case planner/executor/grounding tá»« 4â€“5 lÃªn â‰¥ 20.
5. **LÃ m rÃµ chÃªnh lá»‡ch memory 0.188 vs 1.000** (fixture vs oracle) â€” chá»n má»™t Ä‘á»‹nh nghÄ©a "Ä‘Ãºng" vÃ  ghi vÃ o `memory_correctness_dataset.jsonl`/`memory_oracle.py`.
6. Náº¿u cáº§n má»™t káº¿t luáº­n vá» cháº¥t lÆ°á»£ng gá»£i Ã½: pháº£i cÃ³ Ã­t nháº¥t má»™t cáº¥u hÃ¬nh cho `recall@10 > 0` (ká»ƒ cáº£ baseline) â€” náº¿u khÃ´ng, má»i so sÃ¡nh agent chá»‰ Ä‘ang so hÃ nh vi, khÃ´ng so relevance.

---

## 37.8. Cáº¬P NHáº¬T PENDING (02/11/2026 - commit f00b62f)

ÄÃ£ cáº­p nháº­t:
- âœ… Commit f00b62f (02/11/2026) vÃ  GitNexus index (6.013 nodes, 11.804 edges, 209 clusters, 264 flows)
- âœ… Má»¥c 9.1 PlanExecutor: session reference `$S.field`, quality gate reflection, session update step 8
- âœ… Má»™t sá»‘ cáº­p nháº­t báº£ng 9.3: prompt (5 tool, multi-turn example), schema (_SESSION_REF), helper (session ref, quality gate), agent_tools (5 tool), _schema TEMPLATES (7 kind), _limits (re-export MemoryLimits), __init__ (export Session)

Cáº§n sá»­a thá»§ cÃ´ng (edit tool bá»‹ lá»—i string match):
1. **Báº£ng 9.3**: ThÃªm dÃ²ng `session.py` sau dÃ²ng `planner/plan_executor.py`:
   ```
   ||`session.py`|`Session`: quáº£n lÃ½ state multi-turn conversation (turns, shown_items, candidates, ranked, constraints, feedback). `_Turn` (internal dataclass): 1 lÆ°á»£t há»™i thoáº¡i. Limits (max_turns, max_shown_items, max_candidates, max_turn_chars). Methods: `add_turn`, `add_shown_items`, `set_candidates`, `update_constraints`, `add_exclusions`, `add_feedback`, `get_valid_ids`, `reset`, `to_dict`|
   ```
2. **Má»¥c 10.3**: Cáº­p nháº­t báº£ng request kinds tá»« 5 lÃªn 7 kind (thÃªm `exclusion`, `unanswerable`)




## 37.9. Cáº­p nháº­t tá»« Audit 02/11/2026

Xem file **`AUDIT_REPORT.md`** Ä‘á»ƒ cÃ³ bÃ¡o cÃ¡o kiá»ƒm tra toÃ n diá»‡n (so sÃ¡nh code vs docs, tráº¡ng thÃ¡i limitation, P0-P3 findings, files changed, verification).

TÃ³m táº¯t nhanh:
- **P0 Evaluation Correctness**: RESOLVED (scoring nháº¥t quÃ¡n, leakage prevention, request kinds 7 loáº¡i)
- **P1 Agent Reliability**: MOSTLY RESOLVED (reflection khÃ´ng detect poor recommendation quality khi tools succeed)
- **P2 Retrieval Quality**: PARTIALLY RESOLVED (Vietnamese-English mismatch, no embeddings, no hybrid fusion)
- **P3 Architecture Cleanup**: PARTIALLY RESOLVED (session.py fixed, 20+ files váº«n vi pháº¡m quy Æ°á»›c 1 symbol/file)

File changed: `package/agents/session.py` (Turn â†’ _Turn private).

---

# Phụ Lục: Tài Liệu Tham Khảo Đã Tích Hợp

> Nội dung dưới đây được tích hợp từ các file .md khác trong repo (AUDIT_REPORT.md, RUN_SCRIPTS.md, EVALUATION_PROTOCOL.md, package/evaluation/*.md) để tập trung thông tin tại một nơi.

---

## A. Kiến Trúc Package Chi Tiết (từ AUDIT_REPORT.md)

```
package/
├── agents/
├── api/
├── config/
├── data/
├── demo/
├── evaluation/
├── inference/
├── memory/
├── tools/
└── utils/
```

---

## B. Kiến Trúc Evaluation Framework (5 Layers + 7 Request Kinds)

**5 Evaluation Layers:**
1. L1: Recommendation Quality
2. L2: Task Success
3. L3: Retrieval & Grounding
4. L4: Planning & Execution
5. L5: Efficiency & Cost

**7 Request Kinds:** similar, personalized, constrained, cold_text, ambiguous, exclusion, unanswerable

**Component Benchmarks:** Planner, Executor, Grounding, Integration, Memory
**Multi-turn:** 7 scenarios M1-M7
**Campaign:** Experiment matrix, checkpoint/resume, bootstrap CI, paired significance
**Reporting:** Markdown, CSV, failure reports, visualizations

---

## C. Scripts Reference (từ RUN_SCRIPTS.md)

Working Directory: src/ (PYTHONPATH=.)
Config: load_config("agent/tools") reads configs/agent/tools.yaml

1. Data Pipeline: scripts/data_pipeline/run_pipeline.py
2. EDA: scripts/eda_diagnostic/run_eda.py, diagnose_splits.py
3. Demo: scripts/demo/run_demo.py, demo_full_agent.py
4. Evaluation: run_agent_eval.py, run_baselines.py, tune_baselines.py, candidate_recall.py, benchmark_categories_any.py, analyze_ranking_bottlenecks.py, evaluate_product_reply.py, evaluate_with_jev.py
5. Tools: scripts/tools/run_tools.py, check_llm_provider.py
6. LLM Agent: scripts/llm_agent/smoke_real_llm.py
7. Experiments: scripts/experiments/compare_experiments.py

Env: LLM_API_KEY, LLM_BASE_URL, DOMAIN, PYTHONPATH=.

---

## D. Metadata Policy & ItemKNN Provenance (từ EVALUATION_PROTOCOL.md)

- historical_static_catalog (default): Mask price, average_rating, rating_number
- snapshot: Retain values for non-causal comparison
- ItemKNN v2: exact sorted event pairs, int64 hash, SHA256 provenance
- Legacy v1 requires refit; use --no-prebuilt-corpus to build from sources

---

## E. Component Evaluation Framework Status

✅ Framework implemented, MemoryTool benchmark, CLI runner, Regression analysis, Unit tests
⏳ Planner/Executor/Reflection/Inference/Grounding benchmarks (to be implemented)

Limitations: Hand-crafted test cases, fixed regression thresholds
Future: Auto test generation, adaptive thresholds, CI integration, visualizations

---

## F. Hạn Chế Còn Lại & Trạng Thái

### Unresolved (Priority Order)
1. Reflection on recommendation quality (P1)
2. Vietnamese-English retrieval (P2)
3. Embedding-based retrieval (P2)
4. Hybrid retrieval with learned fusion (P2)
5. Package layout convention (P3)

### ✅ Đã Giải Quyết
- P1 Reflection: Implemented quality-based reflection with configurable threshold
- P2 Vietnamese-English: Removed non-ASCII query rejection
- P0 Evaluation: Verified as correct
- P3 Architecture: Minor violations remain; session.py fixed

### Test Results Summary
Evaluation Tests: 172 total, 170 passed, 0 failed, 2 skipped
Session Tests: 15 total, 15 passed
All Acceptance Criteria MET.

---

*Phụ lục này được tạo từ: AUDIT_REPORT.md, RUN_SCRIPTS.md, EVALUATION_PROTOCOL.md, package/evaluation/*.md, package/evaluation/component/README.md*