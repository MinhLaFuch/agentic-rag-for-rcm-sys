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
