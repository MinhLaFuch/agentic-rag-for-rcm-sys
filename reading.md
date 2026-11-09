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

### G3 review — bảng delta chức năng 6 module "TB thắng" (kiểm chứng lại bằng diff trực tiếp)

| Module | Delta chức năng ngoài CLI | Đã port? |
|---|---|---|
| `tune_baselines` | **Không** — chỉ khác cờ CLI (`--models/--ks/--run-final-test/--splits-dir`) + import path; logic tuning y hệt | N/A (TB thắng, yaml-driven) |
| `analyze_ranking_bottlenecks` | **Không** — source delegate `candidate_policy_order` cho rrf_60/popularity_first; TB inline tương đương + yaml `ranking_diagnostics`; module `candidate_policy_order` đã port ở G3 cho scripts khác | N/A (tương đương ngữ nghĩa) |
| `evaluate_product_reply` | **Không** — chỉ khác import path | N/A |
| `evaluate_with_jev` | **Không** — chỉ khác cơ chế config (`--config-file` flag vs `CONFIG_OVERLAY_PATH` env của TB) | N/A (TB thắng theo Phase 5) |
| `candidate_recall` | **Có, defer G4**: `verify_tag_manifest` + `config.manifest_status/manifest_sha256` — phụ thuộc `package.data.manifest` chưa tồn tại; corpus `manifest_path/sha256` TB đã ghi sẵn | Defer G4 |
| `ranking_eval` | **Có — ĐÃ PORT** (commit follow-up G3): `_load_eval_splits` selective load, exclusion cohort `exclude_users_from` (yaml), `all_users` mode, insufficient-sample guard, `build_core_model` wiring (no-op cho legacy tag), popularity từ `knn.scores` cho train-core, `cohort_exclusions` trong config | ✅ |

- G2 hash hiện tại: **`ddecf1e`** (đã amend bỏ `--scorer`/`--hybrid-popularity-weight`; đọc `scoring.mode`/`scoring.hybrid_popularity_weight` từ yaml + validate).
- G3 commit: `f1f17d7` — message `Port eval analysis modules + eval scripts + train-core baselines (G3)`, nguồn `e05879c`/`e83bf33`/`d4fe5b4`/`53eb6a1`, `Co-authored-by: Quan Anh`.
- **Pre-G4 artifact baseline**: `docs/pre_g4_artifact_hashes.json` — sha256 đầy đủ của `user2id.json`/`item2id.json`/`train|validation|test.parquet` (multi_domain) chụp trên `f1f17d7`. Short-hash khớp listing cũ.

## G4 — Data pipeline protocol (6acf144): manifests + temporal_train_core

### File mới
- `package/data/manifest/` (7 file): `__init__`, `_helper`, `check_upstream_manifests`, `pipeline_config_files`, `verify_manifest`, `verify_tag_manifest`, `write_manifest` — adapt import `sha256_file`/`file_hash` → `package.recommenders.shared.file_hash`, `get_domains`/`PROJECT_ROOT` → `package.config`.
- `package/data/leakage/check_fit_core_subset.py` — verify train_core ⊆ train.
- `package/data/pipeline/_streaming_temporal_stage3.py`, `build_evaluation_cohort.py`, `prepare_train_core.py`.
- `scripts/data_pipeline/verify_tag.py` — adapt `--tag` → `--domain` (append, mặc định all → multi_domain).
- Tests: `test_stage_manifests.py`, `test_streaming_temporal_stage3.py`, `test_train_core_protocol.py`.

### Merge delta (bên nào thắng)
| Điểm | Quyết định | Lý do |
|---|---|---|
| `data_protocol` | **source thắng, default `legacy_kcore_before_split`** trong `split.yaml`; `temporal_train_core` opt-in TẮT | Yêu cầu user: mặc định TẮT, legacy path giữ nguyên semantics. |
| `temporal_train_core` cutoffs + `train_ratio/validation_ratio/test_ratio` | **source thắng**: keys mới trong `split.yaml` + schema (`SplitConfig` validate tổng ratio = 1.0, split names giới hạn eval splits) | Cần cho chronological split khi protocol bật. |
| `cleaning.yaml` chunk/timestamp bounds | **source thắng**: `chunk_size`, `min/max_timestamp_ms`, `max_invalid_timestamp_fraction` + schema | Streaming clean + validate timestamp ms; synthetic fixtures cập nhật sang ~900000000000. |
| `clean_domain.py` | **merge**: upsert/last-duplicate-wins cho (user_id,parent_asin,timestamp), string-dtype preserve (ASIN "0486418189"), invalid-row drop + unit-hint error khi vượt fraction | Source delta thật; giữ DataPaths/config conventions TB. |
| `iter_reviews_dataframes` | chunked read + dtype str | +1 dòng dtype pin. |
| `merge_filter_domains.py` | **merge**: streaming merge/filter + stage-2 manifest; `legacy_kcore_before_split` flag ghi vào manifest flags | Source delta; stage2 manifest là mắt xích chain. |
| `map_split.py` | **merge**: đọc `split.data_protocol`; temporal → `prepare_train_core` + `check_fit_core_subset` + `build_evaluation_cohort` + fit-core mappings `mapped/<tag>/fit_core/` + `train_core.parquet` + stage-3 manifest flags/reports; legacy → y hệt cũ | Opt-in; legacy không đổi. |
| `build_artifacts.py` | **merge**: đọc stage-3 manifest; temporal → bắt buộc train_core + fit-core mappings, ItemKNN fit trên train-core, `fit_splits=["train_core"]`; legacy → fit cũ; upstream manifest check mặc định fail-closed | `allow_manifest_mismatch` cho synthetic/legacy tests. |
| `clean_interactions`/`merge_domains`/`tag_domain` | **merge delta nhỏ** theo source (first_seen/timestamp policy liên quan G1) | Đã review trong diff 6acf144. |
| `data/_schema.py`, `split/load_splits.py` | **TB thắng**: giữ ITEM_COLUMNS/SCHEMA_HINT; error message không có `--tag` | Source xóa constants (layout khác) / flag `--tag` không tồn tại ở TB. |
| `run_pipeline.py` | **merge**: +`--allow-manifest-mismatch`, `--scratch-dir`; `data_protocol` đọc từ `split.yaml` (không cờ); stage-3 pre-check thêm temporal outputs khi protocol bật | Phase 5: protocol qua yaml. |
| `verify_tag.py` | **adapt**: `--domain` thay `--tag`; in expected/actual hashes + status | Read-only verifier. |
| Eval scripts manifest wiring | **source delta port**: `verify_tag_manifest` + `manifest_status`/`manifest_sha256` vào candidate_recall, ranking_eval, run_agent_eval, run_baselines | Defer G3 nay đã có `package.data.manifest`; `domains=args.domain or get_domains()` theo semantics TB. Incomplete chain → ValueError (fail-closed đúng source). |
| `memory_tool.py`, `tools/_schema.py`, `__init__.py` các package, `compare_experiments.py`, `live_backend.py`, conftest/tools_helpers | **TB thắng / skip**: source revert love-hate memory, inline schema constants, xóa exports, thêm `--config` flag — đều ngược Phase 5/TB architecture | live_backend Type1 wiring → G5. |

### Lưu ý vận hành
- `verify_tag_manifest` trả `legacy_unmanifested` khi KHÔNG có manifest nào; raise `ValueError` khi chain thiếu một phần (fail-closed). Sau khi chạy stage 2-3 riêng, multi_domain ở trạng thái incomplete → eval scripts sẽ báo lỗi cho tới khi chạy đủ stage 1 (per-domain) + 4.
- Manifest paths tương đối project_root; absolute path bị reject khi verify.

### Verify G4
- pytest full: **1570 passed, 2 xfailed** (1549 + 21 test mới G4), 0 failed.
- Benchmark: memory **29/29**, executor **18/18** (`step_success_rate_mean=0.6111`), integration **12/12** — y hệt baseline.
- Legacy stage run thật (`--stages 2,3 --force --allow-manifest-mismatch`, multi_domain): stage2 486s + stage3 150s, `data_protocol=legacy_kcore_before_split` (k-core chạy ở stage 2 như cũ), leakage_check PASS, cutoffs giữ nguyên.
- **Artifact hash so với `docs/pre_g4_artifact_hashes.json`:**
  - `user2id.json`/`item2id.json`: **byte-identical MATCH**.
  - 3 file parquet: **byte-hash DIFF** nhưng **content 100% identical** — đã so từng cột (decode dictionary→string, cast large_string→string, order-sensitive `Array.equals`) trên cả train (21.69M rows)/validation/test: **0 value diffs**. Nguyên nhân byte-diff: write-path source mới `_write_filtered_parquet` (chunked `ParquetWriter` + `StringDtype`→`large_string`, column order `original_item_id` trước `domain`) thay `df.to_parquet` cũ (dictionary-encoded `string`, `domain` trước). Cùng SNAPPY, cùng row counts/row groups. → Không phải data regression; là format-level delta cố ý của source.
- `verify_tag.py` trên multi_domain sau run: stage2/3 manifests tồn tại, stage1/4 chưa → incomplete chain (fail-closed đúng thiết kế); eval scripts sẽ báo `legacy_unmanifested`→lỗi incomplete cho tới khi chạy đủ pipeline.
- GitNexus `detect_changes --scope all`: 40 symbols/26 files, risk **critical** — do chạm hub functions (build_artifacts/map_split/merge_filter_domains/clean_domain + các `main` eval scripts); expected cho G4, mọi thay đổi additive/opt-in, verify bằng pytest + real pipeline run + benchmarks.

## G5 — Type1 tool-call audit + demo intent path (0a0d20a và liên quan)

### File mới
- `package/agents/type1/recent_seed_items.py`, `recommend_from_intent.py` — port gần nguyên source.
- `scripts/evaluation/sparse_seed_eval.py` — port với adapt layout TB (xem bảng dưới).
- Tests: `tests/evaluation/agent/test_type1_audit.py`, `tests/demo/test_intent_flow.py`, `tests/tools/evaluation/test_sparse_seed_eval.py`.

### Merge delta (bên nào thắng)
| Điểm | Quyết định | Lý do |
|---|---|---|
| `Type1Agent.last_tool_calls` | **source thắng, adapt**: wrapper `call()` đọc `tool.logger.records[start:]` + gắn `data` (ToolResult.data) vào mỗi entry | TB `ToolCallLogger.records` đã tồn tại; `data` thêm để funnel scorer (`step["data"]`) hoạt động cho type1 — planner steps vốn đã lưu full `data`. |
| `run_type1` (run_agent_eval) | **merge**: try/except quanh `recommend`, `tools_available=[SimilarTool,RankTool,LookupTool]`, `tool_calls`, `steps` (kèm `data`, `error_kind`) | Source delta thật; TB tool names + `error_kind`/`data` cho layer4/funnel tương thích. Phần `main()` CLI flags của source **không lấy** (TB yaml-driven). |
| `live_backend.initialize(initialize_planner=True)` + `_ensure_planner()` | **merge**: lazy LLM/planner; `respond` truyền `initialize_planner = mode!="type1" or inference_mode=="llm"` | Mặc định planner/type1+llm init LLM như cũ; chỉ type1+template mới skip health-check (cho phép demo type1 không cần key — đúng intent source). `_ensure_planner` được gọi lại trong `_respond_planner` và khi `initialize()` re-entry. |
| Intent path (`_respond_intent`, `recommend_from_intent`) | **GATE `demo.intent_path_enabled` mặc định FALSE** (yaml + `DemoConfig`) | Điều kiện user: không đổi hành vi mặc định. Flag off: intent fields → ask_user; user_history.empty → no_result như cũ. Flag on: theo semantics source (user thiếu/lạ/rỗng history → intent; không keyword → ask_user; no-CF candidates → fallback intent). |
| `live_backend` type1 answer | **TB thắng**: giữ `compose_answer`/`adapt_from_inference` (LLM answer); source bỏ inference cho type1 | Source rewrite làm mất tính năng inference answer của TB — regression. |
| `live_backend` memory snapshots, `mock_backend`, `IDENTITY_INJECTION`, `get_data_paths(tag=,domains=)` | **TB thắng**: giữ nguyên | Source layout cũ, không có memory panel/mock backend. |
| `demo/view/_dataclass.py` | **merge**: +`intent_query`/`intent_filters` (DemoRequest, default None), +`recommendation_source` (DemoResult, default None, đặt SAU `memory` để không vỡ positional args) | Field mới có default → backward compatible. |
| `sample_users` | **source delta**: `sparse_max=None`→đọc `eval/segment_thresholds`, validate non-negative, **dedupe (user_idx,item_idx) trước bincount** | Fix đếm trùng interaction; `sparse_max` lên yaml đúng convention. `_profile_builder` vẫn truyền `sparse_max=5` explicit (source giữ nguyên). |
| `adapt_from_plan_executor._extract_items_from_results` | **source delta**: metadata fallback từ tool `results` (`candidates`/`ranked`/`items`) khi `item_id_to_metadata` thiếu | Item hiển thị đủ title/price kể cả khi corpus snapshot không có. |
| `demo.yaml` | **TB thắng + thêm key**: giữ `eval_on`/`use_prebuilt_corpus`/`allow_missing_corpus_sources`; +`intent_path_enabled: false` | Source xóa các key LiveBackend của TB; chỉ thêm key mới. |
| `memory_tool.py` | **KHÔNG đụng** | Source revert love-hate thresholds — ngược TB audit-hardened behavior; không bắt buộc cho G5. |
| `sparse_seed_eval.py` | **port adapt**: tool names SimilarTool/RankTool/LookupTool/SearchTool; imports → TB layout (`package.tools`, `package.corpus`, `package.evaluation.recommender.*`, `package.recommenders.shared`); **fix 2 latent bug của source**: `_ObservedTool` thiếu `.logger` (type1_agent.call crash) → thêm logger shim; `_ContentRetriever`/`_RRFModelTool.__call__` thiếu `**_ignored` cho agent/action kwargs → thêm | Source script không chạy được với type1_agent mới (last_tool_calls); fix tối thiểu, eval-only. |
| `plan_executor` steps/tool_calls | **không port — TB đã có** | TB `plan_executor` ghi `entry["data"]=res.data`, `output_summary`, `args`, `error_kind` sẵn (line ~236-265); source delta rỗng. |

### Bug fix kèm theo (phát hiện khi port sparse_seed_eval)
- `ranking_eval._run_stages` tham chiếu `tag_manifest` (local của `main()`) → `NameError` trên mọi run chưa-scoring-complete. Fix: truyền `tag_manifest` vào `_run_stages`. **Thuộc G4** — tách commit riêng `ca23757` (không nằm trong G5 `4b310ac`). Test `test_ranking_streaming` bắt được: FAIL (NameError) trước fix → PASS sau.
- `_ObservedTool` trong `sparse_seed_eval` thiếu `.logger` → `Type1Agent.call()` crash `AttributeError`. Fix: forward inner tool logger hoặc `ToolCallLogger()` rỗng.
- Wrappers `_ContentRetriever`/`_RRFModelTool` thiếu `**_ignored` → `TypeError` khi `Type1Agent` truyền `agent=`/`action=`. Fix: thêm `**_ignored` (kwargs chỉ là metadata, không vào `execute` — `Tool.__call__` đã reserved sẵn).

### Verify G5 (bổ sung sau review)
- `type1_agent.recommend()` output **byte-identical** với bản f1f17d7 (stub tools, diff JSON — IDENTICAL).
- **Parity tool thật**: `build_tools` (ItemKNNRecommender + BaselineScorer + corpus/cf fixture → SimilarTool/RankTool/LookupTool/SearchTool/FilterTool/MemoryTool thật) — old `Type1Agent`@f1f17d7 vs new, 23 requests (11 users × k, + unseen user cold-start): `recommend()` outputs **identical 23/23**; `run_type1` trajectories **identical modulo field mới** (`tool_calls`, `steps`, `wall_seconds`) 23/23. Khác biệt duy nhất còn lại: `agent`/`action` trong log records (mục đích feature) — không ảnh hưởng `execute` kwargs. **Giới hạn**: fixture tools_helpers (5 items, 17 interactions), không phải corpus multi_domain đầy đủ — chấp nhận làm bằng chứng parity, không phải benchmark.
- pytest full: **1605 passed, 2 xfailed** tại `4b310ac` → **1614 passed, 2 xfailed** sau hardening (`cd2686c` + smoke tests)
- Benchmark: memory **29/29**, executor **18/18**, integration **12/12** — y hệt baseline. Planner/grounding vẫn fail do thiếu LLM_BASE_URL (môi trường, như mọi nhóm trước). Lưu ý: executor suite **không chứa Type1** — bằng chứng Type1 nằm ở parity run_type1 ở trên.
- GitNexus `detect_changes --scope all`: 15 symbols/10 files, risk **critical** — LiveBackend/Type1Agent là hub; mọi thay đổi additive/opt-in, verify bằng pytest + benchmark + parity proof.

### FAIL-before → PASS-after (bug latent, revert-fix chứng minh)
| Bug | Revert fix → test | Kết quả |
|---|---|---|
| `tag_manifest` NameError (G4) | `test_ranking_streaming` | FAIL (NameError) → PASS sau `ca23757` |
| `_ObservedTool.logger` thiếu | `test_runner_json_only_same_sample_budget_and_resume[False]` | FAIL (AttributeError → tool_error rows) → PASS sau restore |
| `**_ignored` thiếu | `test_content_retriever_accepts_agent_action_kwargs` (+ `_RRFModelTool` case) | FAIL (TypeError) → PASS sau restore |

### Mutation test thật (sửa code → test đỏ → revert)
| Mutation | Test bắt được | Kết quả |
|---|---|---|
| `_intent_path_enabled` → `return True` | `test_intent_path_disabled_by_default` | FAIL → revert PASS |
| `_intent_path_enabled` → `return False` | 4 enabled-path tests (`test_demo_no_history_user_can_search_without_llm`, `test_cold_free_text_...`, `test_existing_user_explicit_intent_...`, `test_known_user_without_cf_candidates_...`) | FAIL ×4 → revert PASS. **Lưu ý**: ban đầu fixture `intent_enabled` patch chính `_intent_path_enabled` → mutation `False` sống sót; đã sửa fixture patch `load_config("agent/demo")` để gate thật chạy — cả 2 chiều mutation giờ đều bị bắt. |
| bỏ `self.last_tool_calls.append(entry)` | `test_type1_preserves_ordered_calls_and_failures_without_previous_request[None]` | FAIL → revert PASS |
| bỏ `entry["data"] = data` | cùng test trên | FAIL → revert PASS |

### `LiveBackend.respond` — điều kiện skip LLM trước/sau G5
- **Trước (27a8cee)**: `initialize()` không tham số; `respond()` gọi nó ở request đầu tiên bất kể mode → luôn `build_llm_provider` + `health_check()` + dựng 2 PlanExecutor. Type1+template **vẫn bắt buộc LLM sống**; thiếu creds → RuntimeError → `tool_error`.
- **Sau (HEAD)**: `respond()` gọi `initialize(initialize_planner = request.mode != "type1" or inference_mode == "llm")` → skip LLM/planner **chỉ khi `mode=="type1"` AND `inference_mode=="template"`**; planner mode và type1+llm vẫn init đầy đủ. `_respond_planner`/`_respond_type1` gọi `_ensure_planner()` lazy khi cần. `initialize()` default `initialize_planner=True` giữ nguyên chữ ký.
- **Đây là đổi hành vi thật** ở nhánh type1+template (trước: yêu cầu LLM; sau: không cần) — **ngoại lệ có chủ đích được chấp nhận**: hành vi cũ ở nhánh này thực chất là lỗi (template inference không dùng LLM nhưng vẫn bắt health-check); planner path và type1+llm không đổi.

### Còn nợ / lưu ý
- Multi-turn vẫn chưa nối `_run_all` (đã báo từ G3, không thuộc G5; tách riêng, không trộn G6).
- `filtered/interactions.parquet` vẫn là bản format mới sau G4 — **không có backup bản cũ**, không nằm trong 5/5 hash match; content tương đương chỉ verify gián tiếp qua splits đã decode-compare. Ghi nhận: artifact set hiện là hỗn hợp (splits=old bytes, filtered= new format).
- `intent_path_enabled` hiện chỉ có tác dụng khi UI/request truyền `intent_query`/`intent_filters`; `run_demo.py`/mock backend chưa có control cho 2 field này.

### Coverage debt (đo bằng coverage.py, full suite 1614 passed)
- `scripts/data_pipeline/{run_pipeline,verify_tag}.py`: trước đây **0 test import** → đã thêm `tests/data/pipeline/test_cli_smoke.py` (7 test: stage order, precheck fail-closed, verify_tag status/MISSING/mismatch/legacy).
- `scripts/evaluation/`: `run_agent_eval` 38%, `candidate_recall` 30%, `evaluate_with_jev` 30%, `analyze_ranking_bottlenecks` 29%, `sparse_content_replay` 19% — phần chưa chạm chủ yếu `main()`/CLI parsing và nhánh hiếm (resume, all_users, manifest-mismatch exits). Không chặn G6.
- `package.evaluation/product_reply/evaluate_product_reply.py` 12%, `multi_turn/_reporting`+`_run` 0%, diagnostics 0% — **nợ có sẵn của TB**, không phải integration debt.

## G6 — prep (chưa chạy `merge -s ours`)

`git fetch` xác nhận `origin/tools-building-2` vẫn = `0a0d20a` (không đổi kể từ G5). **Chờ user xác nhận với đồng đội trước khi merge-ours.**

### Bảng phủ 11 commit nguồn → nhóm → trạng thái
Bằng chứng: `git merge-base origin/tools-building origin/tools-building-2` = `6b0c740`; `git log --oneline 6b0c740..origin/tools-building-2` = đúng 11 commit (5 merge + 6 content).

| Source commit | Nội dung | Nhóm | Trạng thái |
|---|---|---|---|
| `4871743` | Merge PR#6 | — | skipped (merge commit, không content riêng; `merge -s ours` ghi nhận ancestry) |
| `b88968d` | Merge main→tb2 | — | skipped (merge commit) |
| `de64880` | Merge PR#7 | — | skipped (merge commit) |
| `e05879c` | semantic embeddings + sparse eval tools | G3 + G5 | **ported/adapted**: 15 eval scripts + analysis modules (G3 `f1f17d7`/`ddfd205`); `recommend_from_intent`, `recent_seed_items`, `sparse_seed_eval`, demo dataclasses (G5 `4b310ac`) |
| `fc0b8c9` | Merge PR#8 | — | skipped (merge commit) |
| `3c7bb25` | Merge main→tb2 | — | skipped (merge commit) |
| `6acf144` | temporal pipeline safeguards | G4 + G5 | **ported/adapted**: manifests, temporal_train_core (opt-in, default off), pipeline deltas, configs, verify_tag, manifest wiring (`27a8cee`); live_backend/sample_users deltas (`4b310ac`) |
| `e83bf33` | full data preflight | G3 | **ported/adapted**: `full_data_preflight` script + train-core baseline wiring trong `run_baselines` (`f1f17d7`) |
| `d4fe5b4` | new hybrid | G2 + G3 | **ported/adapted**: sparse_topk, HybridItemKNN, fit_splits, eval deltas (`ddecf1e`); eval-script phần hybrid (`f1f17d7`) |
| `53eb6a1` | baseline test | G2 + G3 | **ported/adapted**: scorer/provenance tests + eval test ports (`ddecf1e`, `f1f17d7`) |
| `0a0d20a` | Type1 tool-call + scorer | G2 + G5 | **ported/adapted**: HybridScorer/scoring.yaml (`ddecf1e`); Type1Agent.last_tool_calls + run_type1 trajectory (`4b310ac`) |

### Còn lại cho G6
- `test_agent_scorer_cli.py`: **SKIP có lý do + adapted coverage** — source test kiểm cờ `--scorer`/`--hybrid-popularity-weight` đã bị G2 chủ động loại (Phase 5: tunables chỉ trong yaml). Test thay thế: `tests/evaluation/agent/test_scorer_yaml_cli.py` — inject `agent/scoring` qua `CONFIG_OVERLAY_PATH`, chạy `run_agent_eval.main()` end-to-end trên fixture, assert `config["scorer"]["mode"]`, `config["protocol"]["scorer"]`, `history_splits`, `knn_cache_used`, type1 `steps`/`tool_calls`, và hybrid seen-exclusion trên baseline recommendations. **Test này bắt được 2 latent bug** (xem dưới).
- **Latent bug #4 (G1 `3fc6d97`)**: `run_agent_eval.py:291` dùng `paths.cleaned_path` thay `data_paths.cleaned_path` → `NameError` trên mọi run `use_prebuilt_corpus: false` (default true nên chưa ai chạy). Fix riêng, FAIL (NameError) → PASS.
- **Latent bug #5 (G1 policy × TB helper)**: `apply_metadata_policy` tạo `TEMP VIEW item_categories` không có `rowid` → `_deepest_category` (`ORDER BY rowid DESC`, TB pre-existing) crash `OperationalError` khi build constrained/cold_text/exclusion requests trên corpus đã apply policy. Fix: view expose `c.rowid AS rowid` (cùng pattern `items` view). FAIL (OperationalError) → PASS; 577 corpus/evaluation/demo/data tests không regression.
- `merge -s ours origin/tools-building-2` sau khi user xác nhận source không đổi — lệnh chuẩn bị sẵn: `git merge -s ours origin/tools-building-2 -m "Merge origin/tools-building-2 (manual port complete G1-G6)"` — **CHƯA CHẠY**.
- Multi-turn `_run_all` wiring: **tách riêng**, không thuộc G6.
