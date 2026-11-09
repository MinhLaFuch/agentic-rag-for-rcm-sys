# Kế hoạch tích hợp `retrieval-embedding` → `tools-building` — BƯỚC 1 (chỉ đọc)

**Trạng thái**: phân tích xong, CHƯA merge, CHƯA sửa code. Chờ duyệt chiến lược.
**Nhánh nguồn thực tế**: `origin/retrieval-embedding` (prompt ghi `[TÊN_NHÁNH]` — placeholder).
**Môi trường**: `tools-building` local = `8385078` (ahead origin `c929202` 1 commit — "quick save" đã rebase lên `c929202`).

---

## A. Quan hệ hai nhánh

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Merge-base | `6b0c740` "week snapshot" | `git merge-base` |
| Source head | `53eb6a1` "baseline test" | `git rev-parse origin/retrieval-embedding` |
| Target head | `8385078` (local) / `c929202` (origin) | `git rev-parse` |
| Commits source sau merge-base | **10** | `git rev-list --count` |
| Commits target sau merge-base | **90** | `git rev-list --count` |
| Diff source→base | 269 files, +98,881 / −2,889 | `git diff --stat 6b0c740 origin/retrieval-embedding` |
| Diff target→base | 887 files, +1,834,370 / −861,268 | `git diff --stat origin/retrieval-embedding...tools-building` |

10 commit nguồn: `53eb6a1` baseline test, `d4fe5b4` new hybrid, `e83bf33` full data preflight, `6acf144` temporal pipeline safeguards, `3c7bb25`/`fc0b8c9`/`de64880`/`b88968d`/`4871743` (merge main/tools-building cũ), `e05879c` semantic embeddings + sparse eval.

**Nhận định**: hai nhánh diverge rất xa. Source tách từ `6b0c740`, trước khi tools-building đổi tên package (`tools/corpus`→`corpus`, `tools/recommenders`→`recommenders/{shared,evaluation,runtime}`, `tools/sql_query`→`tools/sql`, `tools/score`→`tools/scoring`, tool renames ItemCFTool→SimilarTool, RecoModelTool→RankTool, SemanticSearchTool→SearchTool, SQLTool→FilterTool, QueryTool→LookupTool), xóa `--tag`/`run_tag.yaml`, thêm `resolve_dataset_tag`/`outputs:`/Pydantic `extra=forbid`, và tái cấu trúc `evaluation/` thành layer1-5 + `recommender/`. Source **không có `pyproject.toml`** (tools-building thêm sau merge-base).

## B. Nhánh nguồn làm gì (theo module DATA)

| # | Module (path trên source) | Làm gì | Ai gọi | Input → Output |
|---|---|---|---|---|
| B1 | `data/pipeline/_streaming_temporal_stage3.py` (490 dòng, mới), `prepare_train_core.py`, `build_evaluation_cohort.py` | Protocol `temporal_train_core`: stage 3 streaming, fit-core mappings `mapped_dir/fit_core/`, `train_core.parquet`; opt-in qua `data_protocol` | `map_split`, `build_artifacts`, scripts | filtered parquet + cutoffs YAML → splits + train_core + fit mappings |
| B2 | `data/manifest/*` (7 file, mới) | Stage manifest JSON (write/verify/check upstream, tag manifest) | `map_split`, `merge_filter_domains`, `clean_domain`, `build_artifacts` | stage outputs → `stage_N.manifest.json` + warnings |
| B3 | `data/pipeline/clean_domain.py` (+125) | Stage 1: bắt buộc pandas string dtype, validate rating/timestamp qua `clean_interactions` tham số mới, upsert `ON CONFLICT DO UPDATE`, bảng chẩn đoán `observed_user_timestamp_items`, đếm consecutive dup | `run_pipeline.py --stages 1` | raw jsonl.gz → cleaned parquet + report |
| B4 | `data/clean/clean_interactions.py` | Thêm `validate_values`, `min/max_timestamp_ms`, `max_invalid_timestamp_fraction`, `duplicate_keep`; report `num_dropped_invalid_*` | `clean_domain` | df → (clean df, report) |
| B5 | `data/pipeline/merge_filter_domains.py` (+112) | Ghi parquet streaming theo row-group 250k (tránh categorical vocabulary phình), check manifest stage 1, flag `legacy_kcore_before_split` | `run_pipeline.py --stages 2` | cleaned per-domain → filtered parquet |
| B6 | `data/pipeline/map_split.py` (+140) | Nhận `data_protocol`, rẽ nhánh temporal_train_core → `_run_streaming_temporal_stage3`; legacy giữ nguyên; check manifest stage 2 | `run_pipeline.py --stages 3` | filtered → splits (+train_core) |
| B7 | `data/pipeline/build_artifacts.py` (+121) | Stage 4: verify manifest stage 3, nhánh `use_train_core` (fit-only mappings + train_core.parquet), `first_seen_ts`, `min_coverage_by_domain`, chặn ghi đè khi thiếu `--force` | `run_pipeline.py --stages 4` | mapped/splits → corpus.sqlite + item_knn npz |
| B8 | `data/build_first_seen_timestamps.py` (mới), `data/leakage/check_fit_core_subset.py` (mới) | first_seen_ts = min timestamp mỗi item trên toàn cleaned; kiểm fit_core ⊂ train | build_artifacts, tests | cleaned parquet per domain → {item_id: ts} |
| B9 | `tools/corpus/*` (build/load/save/policy/fingerprint/_sql/_schema) | Schema items **+`first_seen_ts`**, `ITEMS_TABLE_SCHEMA`, dedup meta theo `(domain,parent_asin)` theo completeness, `coverage_by_domain`, `duplicates_dropped_by_domain`, policy v2 `first_seen_filter` (TEMP view items + rebuild FTS), provenance `first_seen_protocol`, `CORPUS_LOGIC_VERSION=2`, **bỏ `allow_missing_sources`**, coverage theo domain | build_artifacts, LiveBackend, agent eval | meta_files + item2id + first_seen_ts → corpus_<tag>.sqlite |
| B10 | `tools/recommenders/recommender.py` (+57) | Hook `_recommend_sparse` (fast path), `history_matrix` thay `train_matrix` cho history_sizes, viết lại top-k deterministic (partition + lexsort) | mọi recommender | — |
| B11 | `tools/recommenders/sparse_topk.py` (mới), `hybrid_item_knn_recommender.py` (mới, 75 dòng) | Exact sparse Top-K + HybridItemKNN = CF chuẩn hóa × weight + popularity pre-cutoff | evaluate_recommender, ranking_eval, tune_item_knn_hybrid | train_matrix + similarity → top-k int64 |
| B12 | `item_knn_matrix/popularity_matrix/fallback_recommender` (+12/+8/+9), `fit_provenance`/`load`/`save_item_knn` (+`fit_splits` override) | `_recommend_sparse` cho model hiện có; provenance `fit_splits` tường minh | eval/scripts | — |
| B13 | `tools/retrieval/semantic_search_tool.py` | +`exact_count` flag (bỏ COUNT query khi eval) | SemanticSearchTool callers | — |
| B14 | `tools/retrieval/outside_core_content_retriever.py` (mới, 54 dòng), `tokenize_search_query.py` (mới) | Probe FTS5 trên items ngoài CF core, cutoff `first_seen_ts`, timeout | `outside_core_content_probe.py` (eval) | history_ids → candidate ids |
| B15 | `tools/ranking/item_cf_tool.py`, `reco_model_tool.py` | SimilarTool/ItemCFTool + RecoModelTool/RankTool: lọc seed/item theo `first_seen_filter` của corpus policy | planner, benchmarks | — |
| B16 | `tools/evaluation/*` (~30 module, một phần) | build_core_model, confirmation_cohort, policy_chain_compare, diagnose_hit_losses, history_title_query, core_inputs, cohort_policy_for_tag, classify_cf_link, global_core_pairs, recent_priority_order, candidate_policy_order, retrieval_loss_breakdown… | scripts/evaluation/* | — |
| B17 | `evaluation/recommender/core/evaluate_recommender.py` (+54), `evaluation_protocol.py`, `save_experiment.py` | `evaluation_users` subset, `progress_every`, sparse fast-path batch=1024, `item_familiarity_matrix`, `cohort_policy` tham số | ranking_eval, run_baselines | — |
| B18 | `scripts/evaluation/*` (~20 script mới/sửa) | sparse_seed/content/guard/ranking replay, sparse_retrieval_probe, sparse_data_diagnostic, semantic_candidate_eval/preflight/cohort, policy_chain_eval, full_data_preflight, outside_core_content_probe, retrieval_loss_diagnostic, tune_item_knn_hybrid, verify_tag, build_semantic_embeddings | chạy tay | — |
| B19 | **Embedding**: `scripts/evaluation/build_semantic_embeddings.py` (240 dòng, độc lập) | `all-MiniLM-L6-v2`, dim **384**, float32, L2-normalized; pin model bằng commit SHA + checksum; artifacts `documents.jsonl, item_ids.json, vectors.npy, valid.npy, manifest.json, checkpoint.json`; resume + verify provenance | `semantic_candidate_eval.py` (eval-only) | corpus.sqlite + mapping → vector store |
| B20 | `tools/embeddings/__init__.py` | **Rỗng** (`__all__ = []`) — không có runtime embedding | — | — |
| B21 | `agents/type1/recommend_from_intent.py` + `recent_seed_items.py` (mới), `demo/backend/live_backend.py` (+180), `memory_tool.py` (+12), `demo/adapter`, `view/_dataclass`, `sample_users`, `evaluation/requests/build_requests.py` (+26) | Đường intent-search deterministic (BM25 + LookupTool, không LLM), `initialize_planner` lazy, first_seen trong RAM-corpus build | LiveBackend/demo | — |
| B22 | Configs | `cleaning.yaml` +min/max_timestamp_ms +max_invalid_fraction; `split.yaml` +`temporal_train_core` −`item_knn_splits`; `agent_eval.yaml` −5 key +`min_metadata_coverage_by_domain` +`experiments_subdir`; `domains.yaml` −`merged_name` +`role`; `data_paths.yaml` **schema cũ** (không `outputs:`/`src_root`/`config_dir`); `run_tag.yaml` mới (tag=`multi_domain_v2_audit_20261030`); 4 eval yaml mới | load_config | — |
| B23 | `src/experiments/**` (~100 artifact: config.yaml/metrics.json/README/log) + `src/tests/logs/test_results_*.md` (1 file 18,351 dòng) + `behavior_snapshot.json` (5,194 dòng) | Kết quả thí nghiệm đã commit | — | — |

**Embedding KHÔNG vào runtime**: `semantic_search_tool` vẫn là BM25/FTS5 (docstring ghi "semantic là aspirational"); vector chỉ phục vụ eval (`semantic_candidate_eval`). `build_semantic_embeddings.py` tự ghi "Does not import project runtime dependencies" — cần env riêng (torch, sentence-transformers, huggingface_hub), không thêm vào pyproject.

## C. Đối chiếu tools-building

| Phần nguồn | Tương đương tools-building | Phân loại |
|---|---|---|
| B9 corpus first_seen/policy v2/dedup/coverage | `src/package/corpus/*` (cùng module, đã rename) | **(3) Xung đột trực tiếp** — schema SQLite đổi, artifact cũ fail `load_corpus` ("lacks first_seen_ts provenance") |
| B10–B12 sparse_topk/hybrid/_recommend_sparse/fit_splits | `recommenders/shared/recommender.py`, `evaluation/*_recommender.py`, `shared/{fit_provenance,load,save}_item_knn.py` | **(2) Trùng chức năng, khác cách làm** — phần lớn additive, port được; top-k rewrite cần kiểm chứng metric không đổi |
| B17 evaluate_recommender mở rộng | `evaluation/recommender/core/evaluate_recommender.py` | **(2)** — additive, portable |
| B1+B2+B5+B6+B7 pipeline protocol+manifest | `data/pipeline/{map_split,clean_domain,merge_filter_domains,build_artifacts}.py` — tools-building đã audit/sửa (build_artifacts có check riêng, `--domain` thay `--tag`) | **(3)** — chồng lấn nặng trên cùng file; source thêm tính năng lớn nhưng viết trên API cũ (`paths.tag`, `--tag`, message lỗi) |
| B3+B4+B8 clean_domain/clean_interactions/first_seen | cùng file tools-building | **(2)+(3)** — clean_interactions tham số mới additive; clean_domain upsert+diagnostic thay đổi semantics stage 1 |
| B13–B15 tool changes | `tools/retrieval/search_tool.py`, `tools/ranking/{similar,rank}_tool.py` | **(2)** — nhỏ: `exact_count`, first_seen visibility; port vào tên mới |
| B14/B16 outside_core retriever + tools/evaluation | không có tương đương (eval-only); metrics đã có ở `evaluation/recommender/metrics/` | **(1) Mới** — nhưng phải relocate khỏi `tools/evaluation/` (path chết trên tools-building) |
| B19 build_semantic_embeddings | không có | **(1) Mới** — script độc lập, port gần như nguyên văn |
| B18 scripts eval mới | `scripts/evaluation/*` tools-building (run_baselines/tune đã chuyển `src/benchmarks/`) | **(1)+(2)** — script mới OK; script sửa đổi source vẫn dùng `--tag`/`get_data_paths(tag)`/path cũ → phải adapt |
| B21 intent-search/demo | `agents/type1/`, `demo/backend/live_backend.py` tools-building (đã refactor: `_limits`, `_consumed_by`, memory snapshot) | **(2)** — tính năng mới nhưng code source viết trên layout/import cũ |
| B22 configs | `configs/**` + `_schemas.py` Pydantic | **(3)** — merge tự động đã cho thấy fail (mục E-d) |
| B23 experiments/logs | `experiments/` tools-building | **(1) nhưng rác** — khuyến nghị KHÔNG đưa |

## D. Xung đột dự kiến (merge thử `tmp/merge-probe`, đã abort sạch)

Merge thường cho: **28 file UU + 5 DU + 5 UA** chưa merge được, **172 file A + 55 M** auto-merge (nhiều cái auto-merge SAI ngữ nghĩa — vd `agent_eval.yaml` hợp nhất ra key `min_metadata_coverage_by_domain` bị schema forbid). Git rename-detection map khá tốt (`tools/corpus`→`corpus`, `tools/recommenders`→`recommenders/{shared,evaluation}`, ItemCFTool→similar_tool...).

**UU (28)**: `.gitignore`, `src/benchmarks/run_baselines.py`, `configs/data/split.yaml`, `package/__init__.py`, `config/__init__.py`, `data/pipeline/build_artifacts.py`, `demo/backend/live_backend.py`, `evaluation/__init__.py`, `evaluation/ablation/__init__.py`, `evaluation/component/benchmarks/memory_utility.py`, `evaluation/component/run.py`, `evaluation/provenance/build_run_provenance.py`, `inference/compose/__init__.py`, `memory/memory_tool.py`, `tools/_schema.py`, `scripts/data_pipeline/run_pipeline.py`, `scripts/demo/run_demo.py`, `scripts/evaluation/{analyze_ranking_bottlenecks,candidate_recall,ranking_eval,run_agent_eval}.py`, `tests/config/{test_config_loader,test_data_paths}.py`, `tests/corpus/test_metadata_policy.py`, `tests/demo/test_live_backend.py`, `tests/evaluation/agent/behavior_snapshot.json`, `tests/tools/evaluation/test_ranking_streaming.py`.

**DU (5, tools-building xóa/di chuyển — source còn sửa)**: `configs/path/run_tag.yaml` (đã bị thay bằng domains/merged_name → bỏ), `evaluation/component/benchmarks/planner_mock_llm.py`, `evaluation/component/link_e2e.py`, `evaluation/component/run_all.py`, `evaluation/layer5_deployment/layer5_deployment.py` (tools-building đã relocate — cần port tay nếu muốn giữ thay đổi).

**UA (5)**: `recommenders/shared/{hybrid_item_knn_recommender,sparse_topk}.py` (rename-detect đặt đúng chỗ mới), `experiments/test_logs/test_results_*.md` ×3 (rác, bỏ).

**Rác auto-add cần loại khi merge/port**: ~100 file `src/experiments/**` (metrics/config/README/log của source), `src/tests/logs/test_results_20261108_*` (18k dòng), `src/package/tools/evaluation/*` 12 module (path chết — evaluation đã chuyển `package/evaluation/recommender/`).

## E. Rủi ro cụ thể

| # | Rủi ro | Đánh giá |
|---|---|---|
| a | **Artifact/provenance** | Corpus: **bắt buộc rebuild** nếu port B9 — `load_corpus` raise khi thiếu `first_seen_protocol`; schema +`first_seen_ts`, `CORPUS_LOGIC_VERSION` 1→2, policy v1→2. ItemKNN `.npz`: `fit_splits` là optional → file cũ vẫn load; NHƯNG top-k rewrite (B10) có thể đổi thứ tự/vị trí tie → metric benchmark có thể lệch, cần chạy lại ranking_eval để so. Splits/mappings: `temporal_train_core` là opt-in (`data_protocol` default legacy) → artifact cũ vẫn dùng được nếu không bật; manifests chỉ warn (`allow_manifest_mismatch`). Thời gian rebuild: stage1–4 full data **chưa xác minh** (repo không ghi); corpus rebuild riêng = phần stage 4, ước lượng theo kinh nghiệm pipeline hiện tại — cần đo. |
| b | **`--tag`/path cũ** | **Xác nhận còn dùng nhiều**: `run_pipeline.py --tag`, `get_data_paths(tag)` positional, `run_demo.py --tag`, `verify_tag.py --tag` bắt buộc, `diagnose_splits.py --tag`, `candidate_recall.py --tag`, `data_paths.yaml` schema cũ, `run_tag.yaml`. Mọi script/module port sang phải viết lại theo `--domain` + `get_data_paths(domains=...)` + `resolve_dataset_tag`. |
| c | **Giao diện tool** | Tên tool trên tools-building đã cố định (SearchTool/SimilarTool/RankTool/FilterTool/LookupTool) — source chỉ khác tên + import. Thay đổi chức năng nhỏ: `exact_count`, first_seen visibility trong SimilarTool/RankTool. **Rủi ro**: khi `first_seen_filter` bật, output SimilarTool/RankTool đổi → `behavior_snapshot.json`, planner/executor/integration benchmark có thể fail → phải chạy lại toàn bộ `component_benchmarks`. Planner tool schema (`build_tools`) không đổi → planner benchmark ít rủi ro hơn. |
| d | **Config YAML vs Pydantic `extra=forbid`** | **Xác nhận fail**: merge tự động `agent_eval.yaml` sinh key `min_metadata_coverage_by_domain` không có trong `AgentEvalConfig` → `ConfigError`. `split.yaml` conflict: source thiếu `item_knn_splits` (bắt buộc) và thêm `temporal_train_core` (forbid → phải mở rộng `SplitConfig`). `cleaning.yaml` không có schema → OK. 4 eval yaml mới không có schema → pass-through OK. `data_paths.yaml`/`domains.yaml`/`run_tag.yaml` của source là schema cũ → **không được lấy**, giữ bản tools-building. |
| e | **Dependency mới** | pyproject không tồn tại trên source → không có dep mới trong project. `build_semantic_embeddings.py` cần torch/sentence-transformers/huggingface_hub trong **env riêng** (docstring nói rõ) → không đụng pyproject. scipy/numpy/pandas đã có. |

## F. Đề xuất chiến lược — **CHỌN: (3) Port thủ công theo nhóm, source làm tham chiếu**

**Lý do**: (1) Merge thường để lại 36 file conflict + ~12 module `tools/evaluation` ở path chết + import `package.tools.*` sai khắp nơi + configs auto-merge sai ngữ nghĩa — chi phí giải conflict ≈ viết lại, mà kết quả vẫn phải audit từng chỗ. (2) Cherry-pick theo commit không khả thi: chỉ 10 commit nhưng mỗi commit đụng cả trăm file không liên quan (merge commits kéo theo tools-building cũ). (3) Phần lớn thay đổi source là **additive và đã được git rename-map chỉ ra đích đến** — port theo module sang layout mới an toàn, review được từng nhóm, pytest sau mỗi nhóm.

**Thứ tự đề xuất** (mỗi nhóm = 1 commit trên `integrate/retrieval-embedding`, pytest đầy đủ sau mỗi nhóm, báo cáo trước khi sang nhóm tiếp):

| # | Nhóm | Nội dung | Điểm dừng duyệt | Kiểm chứng |
|---|---|---|---|---|
| G0 | Dựng nhánh + baseline | `git switch -c integrate/retrieval-embedding tools-building`; chạy pytest baseline, ghi số pass | — | pytest count = baseline |
| G1 | Corpus + first_seen | B8+B9+B13(một phần)+B15: `first_seen_ts` vào `data/_schema`, corpus schema/policy/build/load/save/fingerprint, SimilarTool/RankTool visibility, SearchTool `exact_count` | **Duyệt trước**: xác nhận rebuild corpus artifact (E-a) | pytest corpus/tools; `load_corpus` trên corpus hiện có phải fail đúng thiết kế hoặc rebuild |
| G2 | Recommenders sparse/hybrid | B10+B11+B12+B17: `sparse_topk`, `HybridItemKNNRecommender`, `_recommend_sparse`, `fit_splits`, evaluate_recommender mở rộng | — | pytest recommenders/evaluation; chạy lại `ranking_eval`/`run_baselines` so metric trước/sau (top-k rewrite có thể đổi tie-order) |
| G3 | Eval modules + scripts | B16 relocate → `evaluation/recommender/` hoặc `scripts/evaluation/`; B18 adapt `--tag`→`--domain`; B19 `build_semantic_embeddings.py` nguyên văn | **Duyệt**: có đưa `tools/evaluation` eval modules không hay chỉ scripts | pytest evaluation; chạy 1 script eval smoke |
| G4 | Data pipeline protocol (lớn nhất) | B1–B7: manifest, temporal_train_core, clean_domain upsert, merge_filter streaming, build_artifacts | **Duyệt**: có bật `temporal_train_core` không hay chỉ mang code opt-in; quyết định rebuild splits | pytest data/pipeline; `run_pipeline.py --stages 1-4` trên subset/domain nhỏ |
| G5 | Demo/agent intent | B21: `recommend_from_intent`, `recent_seed_items`, live_backend intent path (adapt layout) | — | pytest demo/agents; demo smoke |
| G6 | Dọn dẹp + docs | Cập nhật `reading.md` (quyết định bên nào thắng), README/docs nếu cần; KHÔNG đưa experiments/logs rác | — | pytest full + `detect_changes` GitNexus trước commit cuối |

**Loại trừ khỏi port**: B22 phần config cũ (data_paths/domains/run_tag — giữ tools-building), B23 experiments+test logs, `tools/embeddings/` rỗng, mọi import `package.tools.corpus|recommenders|sql_query|score` (viết lại theo layout mới).

## G. Cần bạn quyết

1. **Corpus artifact**: chấp nhận rebuild corpus (bắt buộc nếu port first_seen — E-a)? Có muốn giữ chế độ tương thích artifact cũ không (sẽ phải nới `load_corpus` provenance check — không khuyến nghị)?
2. **`temporal_train_core`**: chỉ mang code opt-in (G4) hay thật sự chuyển protocol và rebuild toàn bộ splits/mappings/train_core? (ảnh hưởng lớn nhất tới thời gian + artifact)
3. **ItemKNN**: giữ `.npz` cũ (fit_splits optional) rồi chạy lại benchmark so sánh, hay rebuild luôn cho đồng bộ provenance?
4. **`tools/evaluation/*` modules**: port hết sang `evaluation/recommender/` hay chỉ những gì scripts G3 cần?
5. **Experiments artifacts** của source (~100 file metrics/config): bỏ hết hay giữ một số README/analysis có giá trị?
6. **Benchmark baseline**: top-k rewrite + first_seen visibility có thể đổi số benchmark — chấp nhận re-baseline mới, hay yêu cầu bit-exact với artifact cũ?
