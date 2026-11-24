# Audit: hạ tầng có phù hợp để lắp bước "query distill" (extractor) không

**Date:** 2026-11-23 · **Scope:** PHASE 0 read-only audit · **Docs nền:** `idea.md`, `TODO.md`, `RETRIEVAL_RANKING_BOTTLENECK.md`, `BOTTLENECK_OPEN_QUESTIONS.md`

Schema dự kiến được audit: `{kind, category_path, price_range, min_rating, exclusions, seed_item, attributes, language}` — mỗi slot `strength: hard|soft` + `provenance: explicit|inferred`.

---

## A. Điểm chèn (insertion point)

### A.1 Luồng hiện tại (request → planner → tools → list)

```
AgentRequest.text (raw VI template)
  └─ run_planner()                      scripts/evaluation/run_agent_eval.py:252
       executor.run(request.text)       package/agents/planner/plan_executor.py:139
         └─ PlanExecutor.plan()        plan_executor.py:98 — 1 LLM call, response_format_json
              {"steps":[{tool,args}],"ask_user":...}  parsed by _extract_plan (_helper.py:166)
         └─ run() executes steps: SearchTool / FilterTool / SimilarTool / RankTool / MemoryTool / LookupTool
              tools built in package/agents/toolkit/build_tools.py:35-52
              step args support $N.path / $union.candidates / $S.<field> refs (_helper.py:77-145)
         └─ plan-reflect loop (plan_executor.py:150-178) on failure
  └─ compose_answer()                  inference template|llm (run_agent_eval.py:231+)
  └─ trajectory {steps, recommended[]} → score_trajectory → scored.jsonl
```

**Lưu ý quan trọng:** `AgentRequest` có structured fields (`kind`, `category`, `price_max`, `excluded_*`, `seed_item_id`) nhưng **chỉ `text` được gửi cho agent** — structured fields là eval-side ground truth (`run_agent_eval.py:252`, `_dataclass.py`).

### A.2 Planner đã distill một phần chưa? — CÓ, ngầm

Planner LLM đã tự trích category/price/keywords vào tool args trong 1 call:

- Bằng chứng thật: planner emit `filters.categories_any: ["Building Toys"]`, `domain`, SearchTool `query` keywords (`investigations/q3_search_timeouts.json:63-118`).
- Tool filter keys đã hỗ trợ: `categories_any/all`, `domain`, `price_min/max`, `min_rating`, `min_rating_number`, `exclude_item_ids`, `title_contains`, `store` (`package/tools/_schema.py:8-20`, `compile_filters.py:222-358`).
- **Failure modes đã đo:** planner bịa filter key `categories_exclude` (không tồn tại — prompt example ở `prompts.yaml:36` tự mâu thuẫn, `RETRIEVAL_RANKING_BOTTLENECK.md:499`); ~70% FilterTool calls dùng `filters:{}` rỗng; category names không tồn tại → `ToolInputError` → reflect retry.

**Slot coverage vs schema dự kiến:**

| slot | đã có ở đâu | thiếu gì |
|---|---|---|
| kind | chỉ eval-side (`AgentRequest.kind`) | không có ở runtime |
| category_path | `categories_any` nhận **leaf label**, exact-match | không có path/prefix concept; category exclusions không tồn tại |
| price_range | `price_min/max` filters | hoạt động, nhưng request không bao giờ mang price (xem C.4) |
| min_rating | `min_rating`, `min_rating_number` filters | request không mang |
| exclusions | `exclude_item_ids` OK; `categories_exclude` **không tồn tại** dù prompt gợi ý | category exclusion gap |
| seed_item | SimilarTool `items` | OK |
| attributes | chỉ `title_contains`, `store` | không có attribute/feature fields |
| language | ngầm (translator trong SearchTool) | không explicit |
| strength/provenance | **không có concept nào trong code** | hoàn toàn mới |

### A.3 Điểm lắp hợp lý

| option | ưu | nhược | verdict |
|---|---|---|---|
| **Trước planner** (rewrite/inject) | zero contract change; inject vào `Session.constraints` (đã có `$S.constraints` trong prompt `prompts.yaml:22`, `session.py:81-95`) | spec chỉ advisory — planner LLM có thể ignore (đã chứng minh bịa filter keys); enforce cần đổi `plan()` signature | khả thi, yếu ở enforcement |
| **Thành tool (DistillTool, step 0)** | fit plan/reflect/trajectory tự nhiên; `$N.path` refs đã support; spec inspectable trong `steps[]` | tốn 1 step; category_path string phải resolve → exact label trước FilterTool (`category_exists`/`suggest_categories` có sẵn); `tool_selection_ok` vs `reference_plans.yaml` cần cập nhật; plan kết thúc không có item → reflect loop cần xử lý | **khuyến nghị** — đúng chỗ nhất |
| **Thay planner** (spec→plan compiler) | deterministic, testable | phải reimplement ask_user, session refs, reflect, multi-turn; prompt hiện xử lý mọi kind trong 1 call | chi phí cao, chưa cần |

### A.4 Phá hợp đồng không?

- **Config:** cần file config mới + pydantic schema trong `_schemas.py` (additive, không phá). Overlay keys phải tồn tại trong base config (`_check_overlay_keys` fail-closed).
- **Tool signature:** tool mới là additive; `input_schema` chỉ check key-level (`_unknown_args`, `_helper.py:184-197`).
- **Trajectory:** steps là dict generic — tool mới serialize OK. Nhưng `tool_selection_ok`/reference-plan matching cần thêm entry vào `configs/agent/reference_plans.yaml`. Scorer layer4 duyệt `REFERENCE_PLANS[kind]` — kind mới cần entry (đã làm cho `descriptive`).
- **Resume/provenance:** `is_resumable` key trên request text + agent + protocol hash — distill thay đổi behavior mà không đổi `request.text` → **phải bump config signature/protocol hash**, nếu không resume cũ bị coi là tương đương sai.

---

## B. Taxonomy và category linking

### B.1 Lưu trữ

- DB: `resource/corpus/multi_domain/corpus_multi_domain.sqlite` (~3.2GB, qua `get_data_paths` → `corpus_{tag}.sqlite`).
- Schema (`package/corpus/_sql.py:13-57`): `items(...)`, `item_categories(item_id, category)` multi-label 1 row/(item,level), `items_fts` FTS5; indexes `idx_cat_item/cat/cat_item_cat`.
- Domains: Electronics 1,609,860 / Toys_and_Games 890,667 / Video_Games 137,249 items.

### B.2 Số đo thực tế (query trực tiếp, mode=ro, 2026-11-23)

| metric | value |
|---|---|
| distinct categories | **2,260** |
| items có ≥1 category | 2,407,801 / 2,637,776 (**91.3%**) |
| labels-per-item | 2–8 rows; phân bố: 2:91k, 3:597k, 4:805k, 5:756k, 6:143k, 7:16k, 8:126 → depth trung vị ~4 |
| category size | min=1, **median=138**, p90=5,726, **max=1,479,553** (`Electronics` root label) |
| categories <10 items | **652/2,260 (29%)** |
| categories <100 items | 1,066/2,260 (47%) |
| labels chứa `>` | 17 rows (outliers) |
| labels chứa `/` | ~2,259 rows (outliers) — **labels thực tế là flat, KHÔNG phải path string** |

**Kết luận quan trọng:** "category_path" không tồn tại dưới dạng string. Path của item = **sequence các label rows** (root→leaf theo rowid, `_deepest_category` = row cuối, `_helper.py:15-20`). Muốn prefix-match phải reconstruct sequence per item — không có sẵn.

### B.3 Helpers tái dùng được

- `_price_of`, `_deepest_category`, `items_satisfying`, `items_without_price` (`package/evaluation/requests/_helper.py:10-48`) — deterministic SQL, eval-side.
- `ItemCorpus`: `categories()`, `category_exists()`, `normalize_category_case()`, `suggest_categories()` difflib 0.6 (`item_corpus.py:257-315`).
- Filter compile: `categories_any` → `IN (SELECT …)`; `categories_all` → `GROUP BY/HAVING`; validation reject unknown + suggest (`compile_filters.py:123-315`).
- **Không có prefix/ancestor matching ở bất cứ đâu** — exact-label `=`/`IN` only. "Parent category" chỉ work vì items mang parent label như 1 row riêng.
- Precedent cho inferred provenance: `inferred_categories` backfill (`apply_metadata_policy.py:223-246`), kNN-vote prototype any_hit@1≈0.99 (`investigations/q2_categorization_proto.json`).

### B.4 Missing-category gap

- **~8.7% items (~230k) không có category row nào** — gap từ source Amazon metadata, không phải pipeline (`INVESTIGATION_REPORT.md:39`). Skew về low-engagement (rating_number<5: 10.9% missing vs ≥500: 3.1%).
- **42/155 oracle targets uncategorized** → spec scoring theo category sẽ đánh unreachable by construction.
- Category filter **silently excludes** uncategorized items (`compile_filters.py` không có NULL-category branch).
- **Khuyến nghị schema:** `category_path` nên mặc định `soft`, hoặc thêm flag "uncategorized allowed"; fallback `main_category` column (coverage 92-97.5%) có sẵn.

### B.5 Category string format

- English title-case, `&`, apostrophes; exact/case-sensitive contract; ASCII case-insensitive fallback qua `LOWER()` (`compile_filters.py:114-120,153-157`).
- Root labels trùng domain names (`Electronics`, `Toys & Games`, `Video Games`) — `category_exists` special-case domain names (`compile_filters.py:159-165`).

---

## C. Request data và gold

### C.1 Fields theo kind (AgentRequest: `request_id, kind, segment, text, user_id, user_idx, seed_item_id, targets, price_max, category, excluded_item_ids, excluded_categories, oracle`)

Nguồn: `requests.jsonl` exp_5 (152 rows). Census: similar=40, personalized=40, cold_text=20, ambiguous=6, exclusion=40, unanswerable=4, **constrained=0**, descriptive=0 (chưa chạy).

| kind | fields populated | gold w/o extractor? | leak target? | ví dụ request_id |
|---|---|---|---|---|
| similar | user_id/idx, seed_item_id, targets, text | seed = last **fit** item (honest) | không | `similar-sparse-0`, `similar-sparse-1`, `similar-warm-0` |
| personalized | user_id/idx, targets, text | chỉ user_id — không có spec | không | `personalized-sparse-0`, `-13`, `personalized-warm-0` |
| constrained | +price_max, category, targets | — | **CÓ (cả 2)** | **không tồn tại trong artifact nào** |
| cold_text | +category, targets | category = leaf của held-out | **CÓ** | `cold_text-cold-0..2` ("Baby Floats", "Building Toys", "Personal Radios") |
| ambiguous | chỉ text | n/a | không | `ambiguous-none-0..5` |
| exclusion | +excluded_item_ids, excluded_categories, targets | exclusions có sẵn | **CÓ** (exclude=held_out[0]) | `exclusion-sparse-0..2` |
| unanswerable | chỉ text | n/a | không | `unanswerable-none-0..3` |
| descriptive | user_id/idx, targets=[1], text=LLM paraphrase | không — text chính là mô tả target | **CÓ** | queries ở `investigations/retrieval_benchmark/descriptive_queries.jsonl` |

### C.2 Slot → gold derivability

- **Có sẵn dạng structured field (không cần extractor):** kind, segment, oracle; `category` (cold_text/constrained — nhưng là **leaf label**, không phải path); `price_max` (constrained); `excluded_item_ids/categories` (exclusion); `seed_item_id` (similar).
- **Không derive được:** mọi slot của personalized/ambiguous/unanswerable (by design); `attributes` của descriptive (free text); `min_rating` (không request field nào tồn tại — FilterTool support nhưng requests không mang).
- **Lưu ý:** `category` field là leaf name, không phải taxonomy path — schema `category_path` cần quyết định leaf vs sequence.

### C.3 Templates & overfitting risk

- `package/agents/_schema.py:4-31`: **9 templates × 2 ngôn ngữ = 18 fixed strings** (VI+EN). `ambiguous` 3 phrasings, `unanswerable` 1.
- **Rủi ro overfit CAO:** extractor eval trên template requests có thể đạt near-perfect bằng pattern-match frame ("Tôi là user … Gợi ý cho tôi {k} sản phẩm …") thay vì hiểu nội dung.
- Mitigation duy nhất hiện có: `descriptive` kind (196 LLM queries đa dạng) + `requests_file` override.

### C.4 Gold spec không nhìn held-out target?

**Các chỗ leak (xác nhận trong build_requests.py):**
- `constrained` :74-83 — price_max = held-out price × 1.25; category = deepest cat của held-out.
- `cold_text` :93-94 — category = deepest cat của held-out.
- `exclusion` :117-118 — exclude_item = held_out[0], exclude_category = deepest cat của nó.
- `descriptive` :149-154 — text = paraphrase của held-out item.
- `similar` :58 — seed = last fit item (pre-cutoff) — **honest, không leak**.

**Phát hiện quan trọng — `constrained` không bao giờ chạy:** `_price_of` đọc `items.price` qua TEMP view; dưới `metadata_policy: historical_static_catalog`, price/rating bị mask NULL toàn bộ (`apply_metadata_policy.py:109,156-158`) → `picked is None → continue`. Verified: **0 request `constrained` trong mọi requests.jsonl** (kể cả dryrun_offline_oracle). → **`price_range`/`min_rating` spec slots chết trong mọi artifact hiện có.**

### C.5 Tiếng Việt

- Request texts chỉ từ `TEMPLATES["vi"]` — không translator ở request-generation.
- `vietnamese_query_translator.py` (~100 phrase pairs) chạy runtime trong SearchTool, không liên quan request gen.
- VI datasets có sẵn: `vi_retrieval/vi_queries.jsonl` (510 LLM queries), `retrieval_benchmark/target_queries.jsonl` (196), `scripts/evaluation/benchmark_vi_cold_queries.py` `VI_SCENARIOS` (~30 curated intents) — benchmark set gần nhất cho VI.

---

## D. Scoring và artifact

### D.1 Backfill offline — KHẢ THI

- `scored.jsonl`: flat metrics per request×agent — **không có recommended item_ids** → không đủ một mình.
- `trajectories.jsonl`: có `recommended` = list item_id strings + `steps[].data` — **đủ**: join `request_id` → request fields + corpus categories. Không cần item2id (item_id strings tra trực tiếp).
- Multi-agent runs: 1 trajectory per agent (exp_1/2 scored.jsonl = 180 rows/2 agents).

### D.2 Thêm metric mới cần sửa

- `score_trajectory` merge các layer (`package/evaluation/trajectory/score_trajectory.py:18-95`) — layer return dict auto-merge.
- `summarize` (`trajectory/summarize.py:86-106`) auto-average mọi numeric key — **metric numeric mới được summarize free**; dict detail cần thêm `_NON_NUMERIC_KEYS`.
- Vị trí tự nhiên: `package/evaluation/layer1_outcome/spec_metrics.py` (hoặc trong `score_layer1_outcome.py` đã import corpus + đọc `trajectory["recommended"]` :48).
- Near-equivalents tái dùng: `items_satisfying`/`_deepest_category`; `constraint_satisfaction` (graded fraction, `score_layer2_interaction.py:43-85`), `exclusion_compliance`.
- Touch points khác: `SUMMARY_COLUMNS` (`run_agent_eval.py:97-101`), reporting adapter (`package/evaluation/reporting/_adapter.py` — registry chưa xác minh đầy đủ), metrics.json (auto), tests.

### D.3 Artifact inventory (verified trên disk)

| run | requests | trajectories | scored |
|---|---|---|---|
| campaign_005 exp_1,2,5,6 (+3,4,7-12 metrics.json có) | ✅ 152 | ✅ | ✅ |
| `agent_eval/hybrid_scorer/exp_6/run_1` | ✅ | ✅ | ✅ 152 |
| `agent_eval/learned_scorer/exp_5/run_1` | ✅ | ✅ | ✅ 152 |
| `agent_eval/filter_ab/exp_1_always_category`, `exp_3_inferred_cats`, `exp_4_gated` | ✅ | ✅ | ✅ 152 |
| `agent_eval/filter_ab/exp_2_baseline` | ✅ | chưa xác minh | ✅ |
| `agent_eval/union_ab/exp_1_union_prompt/run_1` | ✅ | ✅ | ✅ 152 |
| `agent_eval/descriptive_kind/exp_1/run_1` | ❌ **không tồn tại** — overlay có, run chưa chạy | — | — |

Tất cả runs trên **cùng 152-request set** (seed 42) → paired comparison tốt cho spec metrics.

### D.4 Hiệu năng relevant-set helpers

- Deterministic SQL + indexes → đo thực tế: 10 single-item category lookups **0.0ms**, category membership **0.0ms**, category count **1.0ms**. Trên 152 requests: negligible (<1s tổng).
- Caveat: `_deepest_category` phụ thuộc insertion order (`ORDER BY rowid DESC`) — stable trên prebuilt corpus cố định, fragile nếu rebuild.
- `items_satisfying` yêu cầu `price IS NOT NULL` khi có price_max — moot vì constrained không tồn tại.

---

## E. LLM / chi phí / độ ổn định

- Provider: `openai_compatible`, model `gpt-5.5` (`configs/agent/llm.yaml:4-7`), `LLM_BASE_URL`/`LLM_API_KEY` env. Temperature **0.0** ở planner+inference; **không có seed param**; provider có thể non-deterministic (comment trong config).
- `response_format_json=True` → `{"type":"json_object"}` only — **không có json_schema, không tool-calling**. Parse+validate phía client (pattern `_extract_plan`/`parse_llm_reply`); pydantic v2 có sẵn cho config validation — tái dùng được cho spec validation.
- **Không có LLM caching** — mỗi `complete()` gọi network. Extractor cần cache riêng (key = request text hash); 2 agents (planner, planner_memory) sẽ distill cùng request 2 lần nếu không share.
- Chi phí thực đo (metrics.json exp_6): ~4.5-4.7k prompt tokens, $0.024-0.036/request planner-only. Extractor ~1 call/request ≈ +50% calls trên planner-only eval; 300-sample benchmark ≈ vài USD (chưa xác minh exact extractor prompt size).
- Calls/request: planner 1 (+1 retry +reflect_rounds); inference 1 khi mode=llm. Eval 152 req × 2 planner agents = ~304 plan calls.

---

## F. Test và quy ước

- Tests mirror `package/`: `tests/evaluation/agent/test_agent_eval.py` (907 lines, build_requests tests không cần LLM); fixtures `corpus` (5-item ItemCorpus synthetic, `tests/tools_helpers.py:22-56`), `cf_setup`; `ScriptedLLM` fake (`tests/agents/fakes/scripted_llm.py`) — **dùng lại được cho extractor tests**.
- Run: `PYTHONPATH=. python -m pytest tests/` từ `src/`.
- Config mới = `configs/agent/*.yaml` + pydantic schema trong `_schemas.py` + đăng ký `validate_config`; overlay không tạo key mới.
- Artifacts: `data_paths.yaml` outputs → `experiments/`; jsonl artifacts hiện gitignored nhưng tồn tại trên disk.
- Code mới trong `src/`; `src/AGENTS.md` bắt buộc GitNexus impact trước edit + detect-changes trước commit.

---

## G. Kết luận

### Verdict: **PHÙ HỢP CÓ ĐIỀU KIỆN**

Hạ tầng đủ tốt để lắp query distill và spec-based scoring: insertion point rõ (DistillTool step-0 hoặc pre-planner injection), taxonomy helpers sẵn, gold fields đã structured cho phần lớn kinds, trajectories đủ cho offline backfill, LLM wrapper + pydantic sẵn, tests có fixture/fake LLM. Nhưng có 3 điều kiện: (1) category linking phải label-based chứ không phải path-based — "category_path" trong schema cần định nghĩa lại thành leaf label hoặc per-item label sequence; (2) ~9% items uncategorized + `constrained`/`price_range`/`min_rating` slots chết trong artifacts hiện tại → các slot này chưa đo được; (3) extractor-eval trên 18 templates có overfit risk cao — cần paraphrase/descriptive set để đo thật.

### Readiness theo A–F

| section | trạng thái | chi phí |
|---|---|---|
| A insertion point | sẵn sàng (DistillTool hoặc pre-planner) | S-M |
| B taxonomy/linking | **cần sửa nhỏ** — path→label-sequence, uncategorized handling | M |
| C request data/gold | sẵn sàng cho structured kinds; personalized/descriptive cần định nghĩa relevant-set | S |
| D scoring/artifacts | sẵn sàng — backfill offline được, helpers nhanh | S |
| E LLM/cost | sẵn sàng — cần thêm cache + pydantic validation | S |
| F tests/conventions | sẵn sàng — ScriptedLLM, fixtures có sẵn | S |

### Blockers & rủi ro (theo mức độ)

1. **[Cao] Overfit template** — 18 fixed templates; extractor benchmark phải có paraphrase set, nếu không metrics vô nghĩa.
2. **[Cao] `constrained` chết + price masked** — price_range/min_rating slots không có coverage trong mọi artifact; spec schema cần quyết định có giữ slots này không.
3. **[Trung] Category path không tồn tại** — phải redefine slot; ~9% items uncategorized → hard category filter blind spot đã đo (42/155 targets).
4. **[Trung] `categories_exclude` không tồn tại** — exclusion spec chỉ item-level được; category exclusion cần filter key mới hoặc session-level handling.
5. **[Thấp] Không LLM cache/seed** — extractor variance cần đo; determinism temp=0 chưa đảm bảo từ provider.
6. **[Thấp] Resume/provenance hash** — quên bump sẽ làm resume cũ sai.

### Đề xuất schema chỉnh sửa

```yaml
kind: enum(similar|personalized|constrained|cold_text|exclusion|ambiguous|unanswerable|descriptive|unknown)
category_label: str | null        # leaf label exact-match (KHÔNG phải path)
category_labels: list[str] | null # full label sequence nếu cần depth-awareness
price_max: float | null           # giữ, nhưng biết là dead slot trong artifacts hiện tại
min_rating: float | null          # giữ, dead slot tương tự
exclusions:
  item_ids: list[str]
  category_labels: list[str]      # cần categories_exclude filter key mới để enforce
seed_item_id: str | null
attributes: dict | null           # free-form, provenance=inferred only
language: vi|en|mixed|unknown
uncategorized_ok: bool            # default true — tránh blind spot 9%
slots:                            # per-slot
  category: {strength: hard|soft, provenance: explicit|inferred}
  ...
```

### Đề xuất kế hoạch phase sau

- **Phase 1 (schema+validator):** như phác thảo — dataclass/pydantic Spec, validator, gold-converter từ AgentRequest fields; unit tests với corpus fixture. *Điều chỉnh:* gold converter chỉ cover kinds có structured fields; personalized/descriptive gold = partial.
- **Phase 2 (pilot backfill spec metrics):** như phác thảo — offline trên scored.jsonl+trajectories.jsonl của exp_2/exp_5/exp_6/F3/learned; spec_recall chỉ trên kinds có relevant-set định nghĩa được (cold_text=category membership, exclusion=exclusion compliance đã có, similar=category of seed); báo cáo ranking đảo chiều vs task_success không. *Bỏ:* price/min_rating metrics (dead slots).
- **Phase 3 (extractor benchmark):** như phác thảo — gold từ build_requests + paraphrase EN/VI/code-mix/thiếu thông tin; **bắt buộc** leakage check (LLM đoán lại item từ paraphrase); 200-300 mẫu manual check; slot-F1, kind accuracy, category match, Struct rate.
- **Phase 4 (extractor + ablation):** như phác thảo — oracle vs predicted distill, variance giữa runs.
- **Phase 5 (pipeline, flag-off):** như phác thảo — DistillTool step-0, live A/B, không default bật nếu chưa A/B.

### Câu hỏi cần người quyết (5)

1. **`category_path` redefine:** chấp nhận leaf-label + optional label-sequence, hay giữ "path" như abstraction resolve sau?
2. **Uncategorized items:** spec matching có nên include uncategorized items khi category constraint là soft? (đề xuất: yes, `uncategorized_ok` flag)
3. **`constrained`/`price_range`/`min_rating`:** giữ slots trong schema dù dead trong artifacts, hay cắt khỏi v1?
4. **Insertion point:** DistillTool step-0 (khuyến nghị) hay pre-planner injection vào Session.constraints?
5. **Personalized kind:** có định nghĩa relevant-set cho spec scoring không, hay kind này chỉ đo task_success?
