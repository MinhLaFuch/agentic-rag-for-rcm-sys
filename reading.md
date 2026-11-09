# reading.md — nhật ký quyết định tích hợp tools-building-2

> **Đổi nguồn tham chiếu (2026-11-09)**: nhánh port là `origin/tools-building-2` @ `0a0d20a`
> (tag `archive/tools-building-2-0a0d20a`), KHÔNG phải `retrieval-embedding`.
> `origin/retrieval-embedding` (53eb6a1) là ancestor trực tiếp của tb2; tb2 = retrieval-embedding + `0a0d20a`.
> Merge-base(tools-building, tools-building-2) = `6b0c740` (giống merge-base cũ).

Mỗi nhóm port ghi: nguồn tham chiếu, các quyết định "bên nào thắng", lệch so với source.

## G1 — Corpus schema v2 + first_seen_ts + metadata policy v2 (nguồn: `6acf144`)

Port thủ công từ `origin/tools-building-2` (= `origin/retrieval-embedding` + `0a0d20a`; layout cũ `package.tools.corpus`/`package.tools`),
viết lại theo kiến trúc tools-building (`package.corpus`, `package.data`, `package.tools.{ranking,retrieval,sql}`).

### Quyết định bên-thắng / thích nghi

| Điểm | Quyết định | Lý do |
|---|---|---|
| Đường dẫn module | **tools-building thắng**: `package.corpus.*`, `package.data._schema`, `package.tools.{SimilarTool,RankTool,SearchTool,FilterTool,LookupTool}` | Source dùng layout cũ `package.tools.corpus`, `ItemCFTool/SQLTool/QueryTool/SemanticSearchTool` — đã bị đổi tên có chủ đích ở Phase 5. |
| `first_seen_ts` semantics | **source thắng (port nguyên)**: cột mới trong `items`, proxy = min timestamp trong cleaned interactions, KHÔNG phải launch date | Đây là giá trị cốt lõi của nhánh nguồn. |
| `build_corpus` coverage | **source thắng**: exact per-domain coverage + `_Coverage.by_domain` + dedupe metadata theo completeness + `min_coverage_by_domain` | Source bỏ sampling `COVERAGE_SAMPLE=5000`; TB đang sample → port bản exact. `COVERAGE_SAMPLE` đã xóa khỏi `corpus/_schema.py`. |
| `apply_metadata_policy` | **source thắng (port v2)**: TEMP views `items`/`item_categories`/`items_fts` lọc `first_seen_ts <= as_of`, mask `price/average_rating/rating_number` ở `historical_static_catalog`, authorizer chặn main.* | TB chỉ có policy v1 (mask aggregates, không lọc catalog). |
| `load_corpus`/`save_corpus` provenance | **source thắng một phần**: thêm `first_seen_protocol`, `num_items_with_first_seen_ts`, `coverage_by_domain`, `duplicates_dropped_by_domain`, siết hash/domain check. **TB giữ** `allow_missing_sources` thoát hiểm (source đã bỏ) | TB audit cần escape hatch cho corpus thiếu meta thô; source xóa nó. Giữ TB để không phá `allow_missing_corpus_sources` trong agent_eval. |
| `memory_tool.py` | **port phần first_seen bắt buộc**: khi `first_seen_filter` active → lọc interactions `timestamp <= cutoff` + chỉ giữ item visible trong catalog | Source `6acf144` có block tương đương; không port phần khác của memory_tool. |
| `similar_tool`/`rank_tool` | **port visibility gate**: chỉ kích hoạt khi `corpus._evaluation_metadata_policy.first_seen_filter` truthy → mặc định KHÔNG đổi hành vi | Đúng yêu cầu: visibility chỉ bật khi policy được set (eval path), benchmark mặc định y hệt. |
| `search_tool` `exact_count` | **port**: tham số keyword-only `exact_count=True` mặc định → hành vi mặc định không đổi; `total_matches=None` khi tắt | Source thêm để tránh COUNT(*) đắt trong eval loop. |
| `run_agent_eval`/`ranking_eval`/`candidate_recall` | **adapt**: chỉ thêm `build_first_seen_timestamps` + truyền `first_seen_ts` vào `build_corpus`; KHÔNG port `--tag`/`cohort_policy_for_tag` (G3/G4) | TB đã bỏ `--tag`; `apply_metadata_policy` bắt buộc first_seen nên bắt buộc wire. |
| `live_backend.py` | **TB giữ nguyên ở G1** (build_corpus không first_seen → first_seen NULL, không policy → không đổi hành vi demo). Source có wire first_seen — để G5 xử lý cùng intent path. | Tránh trộn G5 vào G1. |
| `agent_eval.yaml` + `AgentEvalConfig` | **port key mới** `min_metadata_coverage_by_domain: {}` + field Pydantic `dict[str,float]` default `{}` | Source thêm cho per-domain threshold; default rỗng = hành vi cũ. |
| Corpus artifact cũ | **sẽ invalidate**: `logic_version` 1→2 + `first_seen_protocol` bắt buộc → `load_corpus` raise → rebuild là bước riêng (backup trước) | Đã báo user; benchmark component dùng fixture in-memory nên không bị ảnh hưởng. |
| Tests | **adapt tên module** sang TB (`FilterTool` thay `SQLTool`, `SearchTool` thay `SemanticSearchTool`, `LookupTool` thay `QueryTool`, `SimilarTool` thay `ItemCFTool`); `test_deterministic_chain` viết lại theo `package.agents.build_tools` + `AgentTools.{search,reco,query}` | Test source viết trên API cũ; semantics giữ nguyên. |
| `test_metadata_policy.py` | **TB gốc thắng cho 6 test cũ**: giữ nguyên expectation `["D::a","D::b"]`, chỉ thêm `first_seen_ts=[1,1]` (cả hai visible ở cutoff 10) + `first_seen_filter` assert. Kịch bản ẩn item (first_seen 5 vs 15) đưa vào `make_temporal_corpus()` + 6 test mới riêng | Tránh sửa expectation của test có sẵn; tách rõ "policy v1 behavior" vs "first_seen visibility". |
| `test_ranking_streaming.py` fixture | **TB sửa**: thêm `cleaned_dir` vào `replace(DataPaths)` + cleaned parquet + `first_seen_ts` vào meta mock | Script giờ đọc cleaned parquet cho first_seen; fixture cũ thiếu → FileNotFoundError. |
| `tools_helpers.py` corpus fixture | **port 1 dòng**: `first_seen_ts: [1]*5` | Source fixture có; cần cho `apply_metadata_policy` trong test mới. |

### Không port trong G1
- `prepare_train_core`, `_streaming_temporal_stage3`, manifests, `data_protocol` → G4.
- Recommender sparse/hybrid top-k → G2.
- `outside_core_content_retriever`, `tokenize_search_query` → G5/G3.
- Embedding scripts → G3.

### Verify G1
- pytest: **1483 passed, 2 xfailed** (baseline 1475 + 8 test mới: first_seen, per-domain coverage, dedupe, metadata_policy mở rộng, fingerprint).
- memory 29/29 (success_rate 1.0), executor 18/18 (step_success_rate_mean 0.6111), integration 12/12 — **y hệt baseline**.
- planner/grounding/multi-turn: chưa so (cần LLM/Jev key) — giống giới hạn audit trước.
- GitNexus `detect_changes --scope all`: 27 files / 49 symbols / risk critical (blast radius rộng nhưng expected; đã verify bằng pytest + benchmark).

### Bổ sung sau đổi nguồn sang tools-building-2

- **Corpus artifact phải rebuild trên mỗi máy**: `load_corpus` kiểm `source_hashes` (sha256 file meta), `mapping_hash`, `schema_fingerprint`, `logic_version`, `first_seen_protocol`. Artifact sqlite build trên máy A vẫn load được trên máy B **chỉ khi** các file `resource/` (meta, cleaned, mapped, splits) giống hệt byte — nếu dataset khác version thì phải chạy lại stage 4. Backup cũ giữ tại `_backups/corpus_pre_first_seen_20261109/` (ngoài repo).
- **`0a0d20a`** (commit duy nhất của tb2 ngoài 53eb6a1): "save tool call of Type1 and scorer agent" — `HybridScorer`/`HybridItemKNNRecommender` mới, type1 tool-call recording, `agent/scoring.yaml`, sửa `run_agent_eval.py`/`type1_agent.py`. Gán **G2** (hybrid scorer/recommender) + **G5** (type1). Không đụng file G1 ngoài `run_agent_eval.py` (vùng khác, không conflict logic) → **G1 không cần cập nhật**.

## G2 — Sparse top-k + HybridItemKNN + fit_splits provenance + eval deltas + HybridScorer (nguồn: `d4fe5b4`, `0a0d20a`)

Port thủ công, merge delta vào file TB (không copy đè). Layout: `package.recommenders.{shared,evaluation}` thay `package.tools.recommenders`; `package.tools.scoring` thay `package.tools.score`; `package.evaluation.recommender.*` thay `package.tools.evaluation.*`.

### File mới
- `recommenders/shared/sparse_topk.py` — copy nguyên (không import tương đối).
- `recommenders/evaluation/hybrid_item_knn_recommender.py` — adapt import `..shared.recommender`, `..shared.sparse_topk`.
- `tools/scoring/hybrid_scorer.py` — adapt import `.baseline_scorer`; export qua `tools/scoring/__init__.py` + `tools/__init__.py`.
- `configs/agent/scoring.yaml` + `ScoringConfig` trong `config/_schemas.py` (key `scoring`, `extra=forbid`).

### Merge delta (bên nào thắng)
| Điểm | Quyết định | Lý do |
|---|---|---|
| `recommender.py` dense ranking loop | **TB giữ lexsort loop**; chỉ thêm `_recommend_sparse` fast-path + `_get_popularity_order` + `history_matrix`/`_popularity_order` pop trong `fit()` + `history_sizes` getattr | Source viết lại dense loop (partition-based); TB lexsort tương đương ngữ nghĩa (score desc, index asc, chỉ >-inf) và là audit-hardened. Sparse path mới chạy TRƯỚC dense → dense loop chỉ còn cho model không hỗ trợ sparse. |
| `_recommend_sparse` hooks | **source thắng**: port vào `item_knn_matrix`, `popularity_matrix`, `fallback` (delegate primary), base `Recommender` trả None | Tính năng cốt lõi: exact sparse top-k không materialize B×catalog. |
| `score_batch`/`history_sizes` `history_matrix` getattr | **source thắng**: `getattr(self, "history_matrix", self.train_matrix)` | Cho phép eval trên history khác train_matrix (train_core/full-history hybrid). |
| `fit_splits` override | **source thắng**: param mới trong `fit_provenance`/`save_item_knn`/`load_item_knn`/`Provenance.fit_provenance` + validation (cần dataset-bound + non-empty strings) | Phục vụ `fit_splits=["train_core"]` ở G4/build_core_model G3. TB `_model_metadata.py` đã có `fit_split_names`/`mapping_hash`/`file_hash`/`item_knn_data_hash` — giữ, không tách file. |
| `evaluate_recommender.py` | **merge delta đúng bảng hunk**: +`progress_every`, +`evaluation_users` (validate 1D-int/unique/target-bearing), sparse-model batch=1024, `item_familiarity_matrix` getattr cho `item_seen`, hits qua `target[np.repeat(u,max_k), safe_top]` (không `toarray`), progress ETA prints, `relevant_items` cho seen_ratio khi subset | Giữ toàn bộ cấu trúc/segment logic TB; import recommender paths → `package.recommenders.evaluation.*`. |
| `evaluation_protocol.py` | **merge delta**: +param `cohort_policy` default giữ literal cũ | Caller TB chưa truyền → output y hệt. |
| `save_experiment.py` | **merge delta**: +param `write_readme=True` + early return sau metrics.json | Source sparse scripts cần `write_readme=False` (G3). Giữ `parents[5]` của TB (source `parents[3]` theo layout cũ — TB thắng). |
| `run_agent_eval.py` scorer wiring | **adapt**: `agent/scoring.yaml` load + validate (KHÔNG thêm cờ CLI — Phase 5: tunables chỉ trong yaml; `--scorer`/`--hybrid-popularity-weight` của source bị loại), `HybridScorer`/`BaselineScorer` chọn theo mode, `baseline_model` = `HybridItemKNNRecommender` khi hybrid (cf similarity = `knn.similarity.T`), `scorer_provenance` vào `protocol_manifest["scorer"]` + `exp_config["scorer"]`, `knn_cache_used` expression | TB script khác source (domain-based, agents từ config) — port phần scorer, giữ nguyên phần còn lại. |

### Không port trong G2 (ghi nhận)
- `type1_agent.py` `last_tool_calls` + trajectory `tool_calls`/`steps` recording + `test_type1_audit.py` → **G5** (Type1 tool-call).
- `test_agent_scorer_cli.py` → **chưa port / adapted-test-pending (G6)**: file không tồn tại ở TB (không phải skip/xfail); test viết trên kiến trúc run_agent_eval của source (`--agents`, `build_core_model`, `verify_tag_manifest`, `--trajectory-file`) không tồn tại ở TB; cần viết lại test tương đương khi G5 ổn định.
- `build_core_model.py`, `core_inputs.py`, `global_core_pairs.py`, `outside_core_content_retriever.py`, `tune_item_knn_hybrid.py`, `run_baselines.py` history_matrix/sparse args → G3/G4.
- `experiments/**`, docs, test logs của source → skip (artifacts).

### Tag note (theo yêu cầu)
- `v1`, `exp_002`, `exp_003` trong docstring demo/baseline scripts: **chỉ là ví dụ, không map** — script gặp tag lạ sẽ báo lỗi qua `get_data_paths`/config, không tự map.

### Verify G2
- Golden dense-equivalence: hash `recommend()` của popularity/item_knn/random/bpr_mf × k∈{1,7,25} trên fixture cố định — **12/12 hash giống hệt trước và sau port** (sparse path cho kết quả byte-identical).
- pytest: **1510 passed, 2 xfailed** (1485 + 25 test mới: hybrid_item_knn 12, sparse_evaluator_optimization 6+param, hybrid_scorer 4+param... thực tế 25 case).
- memory 29/29 (1.0), executor 18/18 (`step_success_rate_mean=0.6111`), integration 12/12 (1.0) — **y hệt baseline**.
- planner/grounding/multi-turn: chưa so (cần LLM/Jev).

## G3 — Eval modules + scripts (e05879c, e83bf33, d4fe5b4 phần eval, 53eb6a1)

- **Modules**: 12 module `tools/evaluation/*` → `package/evaluation/recommender/analysis/` (sub-package mới, eval-only); `outside_core_content_retriever` cũng vào analysis (tránh tools↔evaluation vòng); `tokenize_search_query` → `package/tools/retrieval/` (public wrapper `_tokenize`). `_helper`/`_dataclass` source **không port** — TB đã có tương đương ở `core/`.
- **`cohort_policy_for_tag` → `cohort_policy_for_paths`**: adapt `--tag`→`--domain`; hàm nhận DataPaths đã resolve (test fake được, không resolve kép); `cohort_policy_for_domains` wrapper bỏ để giữ rule 1-public-symbol/file. Wire vào `evaluation_protocol(cohort_policy=...)` ở candidate_recall/ranking_eval/run_agent_eval.
- **Scripts port (15)**: benchmark_categories_any, build_semantic_embeddings, full_data_preflight, outside_core_content_probe, policy_chain_eval, prepare_semantic_candidate_cohort, retrieval_loss_diagnostic, semantic_candidate_eval, semantic_candidate_preflight, sparse_{content_replay,data_diagnostic,guard_replay,ranking_replay,retrieval_probe}, tune_item_knn_hybrid. `--tag`→`--domain`(append); `get_data_paths(d['tag'])` từ experiment record giữ nguyên (tag override đọc artifact cũ, không map); tool names ItemCFTool→SimilarTool, SemanticSearchTool→SearchTool, RecoModelTool→RankTool, QueryTool→LookupTool; `verify_tag_manifest`/`package.data.manifest` **defer G4** — policy_chain_eval ghi `dataset.get("tag_manifest")` thay vì re-verify.
- **`sparse_seed_eval.py` → G5**: phụ thuộc `agents/type1/recent_seed_items` + Type1Agent runtime (G5 scope).
- **`run_baselines.py`**: merge delta train-core — `core_inputs`/`global_core_pairs`/`build_core_model`/`HybridItemKNNRecommender`/`history_matrix` attach/`fit_splits_by_model` + sha256 split files; tunables `popularity_source`+`item_knn_hybrid_weight` vào `eval/baselines.yaml` (+schema), KHÔNG cờ CLI. Legacy path (core=None) giữ `model.fit(fit_matrix)` y hệt.
- **TB thắng, không port source version**: `tune_baselines` (source = bản cũ flag-driven, TB đã yaml-hóa), `analyze_ranking_bottlenecks` (source thêm CLI flags + delegate candidate_policy_order; TB đã inline + yaml `ranking_diagnostics`), `evaluate_product_reply`/`evaluate_with_jev` (chỉ khác import path/`--config-file` flag — TB thắng), `candidate_recall`/`ranking_eval` (TB đã là bản Phase-5; chỉ thêm cohort_policy wire).
- **Configs mới**: eval/{policy_acceptance, semantic_candidate_pilot, sparse_content_eval, sparse_seed_eval}.yaml (pass-through, không schema).
- **Tests port (5)**: test_{confirmation_cohort, outside_core_content, policy_chain_eval, semantic_embeddings, train_core_model} → `tests/tools/evaluation/`; adapt import paths; `test_baseline_runner_*` viết lại theo yaml-config (bỏ `--models/--ks/--popularity-source/--item-knn-hybrid-weight` flags — Phase 5); monkeypatch get_data_paths lambda nhận **kwargs.
- **Verify**: pytest **1549 passed, 2 xfailed** (1510+39); benchmark memory 29/29, executor 18/18, integration 12/12 — y hệt baseline.
