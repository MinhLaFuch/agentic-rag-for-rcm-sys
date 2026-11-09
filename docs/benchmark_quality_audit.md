# Audit chất lượng benchmark — agentic-rag-for-rcm-sys

**Phạm vi**: audit độc lập, chỉ đọc. Worktree `audit/benchmark-quality` từ `tools-building` @ `58628a4`.
**Câu hỏi trung tâm**: benchmark có THỰC SỰ đo được chất lượng component không, hay chỉ cho số đẹp?

## Phương pháp & bằng chứng đã thu thập

- Đọc toàn bộ runner (`_evaluator.py`, `_loader.py`, `_schema.py`, `run_benchmark_cli.py`, `_run_all.py`), 5 benchmark component, dataset JSONL, fixtures, oracle, và code thật bị đo (`MemoryTool`, `PlanExecutor._execute`, `compose_answer`, `outcome_from_plan_results`, `Session`, tools).
- Chạy thực tế (worktree, `PYTHONPATH=. python -m package.evaluation.component.run ...`):
  - memory ×3, executor ×3, integration ×3 → metrics **giống hệt nhau** giữa các lần chạy (deterministic, không LLM).
  - grounding ×1 → `success_rate=0.0` (thiếu `TYPESAFE_API_KEY`, mọi case fail đúng thiết kế "fail loudly").
  - planner ×1 → `ValueError: LLM base_url not configured` (không có LLM key).
- Mutation testing (đã `git checkout` revert sạch sau mỗi lần, worktree sạch):
  - memory: love threshold `>=`→`>`; bỏ sort timestamp của `recent_items`; bỏ `check_profile_snapshot`; bỏ filter `timestamp <= as_of` trong `MemoryTool.execute`.
  - executor: `bad_reference`→`exception`; `_resolve_refs` return nguyên chuỗi `$N`.
  - integration: `errors=[]` trong `outcome_from_plan_results`; thêm item bịa vào `Answer.items`.
- Đối chiếu với artifact cũ trong repo chính: `experiments/agent_eval/component_benchmarks/grounding_benchmark_20261108_165543.json` — một lần chạy grounding **có Jev thật** (`success_rate=1.0`, `grounding_rate_mean=0.906`).
- Test subset: `pytest tests/evaluation/component tests/evaluation/multi_turn -q` → 85 passed.

Môi trường: không có `LLM_BASE_URL`/`LLM_API_KEY`, không có `TYPESAFE_API_KEY` → planner, grounding, multi-turn **không chạy được đầu-cuối**; phần đó audit tĩnh + artifact.

---

## Bảng tổng hợp độ tin cậy

| Component | Độ tin cậy | Lý do chính |
|---|---|---|
| **memory** | **Cao** | Oracle độc lập thật (không import MemoryTool/ItemCorpus, có AST-test), dataset sync-test với oracle, literal được kiểm tay trong test, mutation bị bắt 3/4. Trừ: tool-side `as_of` filter không được benchmark nào phát hiện nếu xóa (mutation cho điểm tuyệt đối); 1 case trùng hệt + 1 case gần trùng; fixture 1 domain. |
| **executor** | **Trung** | Chạy `PlanExecutor._execute` thật trên tool thật, nhạy với mutation (error_kind_accuracy 1.0→0.83–0.86). Nhưng expected chỉ kiểm error taxonomy — **không kiểm giá trị dữ liệu** (FilterTool trả sai vẫn "ok"); 1 case rỗng luôn pass; không threshold. |
| **integration** | **Trung** | Chuỗi thật executor→outcome→compose_answer; mutation bị bắt (`contract_valid` 1.0→0.833, `no_mismatch` 1.0→0.417). Nhưng `grounded_rate` là hằng số 1.0 ở template mode; metric chỉ đo contract, không đo nội dung đề xuất đúng/sai. |
| **planner** | **Thấp** | Không chạy được (cần LLM). Nghiêm trọng hơn: **expected plans dùng schema tool không tồn tại** (`categories_none`, `sort_by/sort_order`, `filters.item_ids/exclude_items/average_rating_min/rating_number_min`, arg `candidates` của FilterTool, `MemoryTool` không có trong toolset, ref `$user_id` không được hỗ trợ). Metric `clarification_precision` so khớp chuỗi tuyệt đối → trần ~0.69; `refusal_to_guess` ≡ `clarification_recall` (trùng); `plan_validity` luôn =1.0. |
| **grounding** | **Thấp** | `score_component` **bỏ qua `expected` hoàn toàn** — label trong dataset là dữ liệu chết. Template-mode bão hòa (đã xác minh bằng run Jev thật: grounding_rate 0.906, mọi case đúng 1 claim). `prompt_injection_detected` là keyword heuristic trên input, bỏ sót 3/4 case tag injection và 1 tag bị gán nhầm. 3 case evidence rỗng auto-fail. Cần Jev key. |
| **multi-turn** | **Thấp** | Runner thật đã viết nhưng chưa từng chạy với LLM. Dataset có expected **không thể đạt** (item `electronics_*`, `book_*`, `preferred_*`, `vg_b_similar` không tồn tại trong fixture); `exclusion_compliance` so bare-id vs namespaced-id → luôn 0 cho exclusion theo item; `reference_correctness` gần như vô nghĩa (xem dưới); `context_retention` vacuous. |
| Benchmark data thật (candidate_recall, ranking_eval, run_agent_eval) | **Trung–Cao** | Temporal split bắt buộc + `check_split_temporal_order`/`check_no_duplicate_across_splits` trong pipeline; held-out target; `category_oracle` được gắn nhãn upper-bound; provenance hash đầy đủ. Chưa audit từng dòng — spot-check protocol/leakage guards thấy đúng. |
| campaign / ablation | Chưa xác minh đầy đủ | Orchestrator gọi script thật qua subprocess; không thấy fake/fallback, nhưng chưa trace hết `_run_experiment`/`_compare`. |

---

## 1. MEMORY — `memory_correctness_dataset.jsonl` (30 case)

**Đường đi**: `MemoryCorrectnessEvaluator.run_component` → `MemoryTool.execute` thật; `score_component` so từng field với `expected` sinh bởi `compute_memory_oracle` (pandas/Counter thuần, không import MemoryTool — `compute_memory_oracle.py:1-7`; có AST-test `test_oracle_does_not_depend_on_tool_or_corpus`).

### Case-level
- Phân bố: normal 2, edge_case 9, cutoff 6, leakage_guard 4, love_hate 7, negative 4. **Toàn bộ fixture là domain `Video_Games`** — không đo được hành vi đa domain (oracle và tool đều giả định `domain::parent_asin`).
- **Trùng lặp**: `correctness_016` và `correctness_030` có `input` **giống hệt nhau** (`u_leakage_test, top_n=3, as_of=14, untruncated`) — case trùng 100%. `correctness_017` (u_love_hate_mix) vs `correctness_021` (u_mixed_ratings): hai user có interaction rows giống hệt nhau (cùng items/timestamps/ratings) → expected giống hệt trừ `user_id` — case gần trùng. Coverage thực tế ~28/30.
- Expected được kiểm tay một phần trong `test_memory_correctness.py:44-68` (u_short, u_outlier_price, u_equal/null_prices, u_dup_items, cutoff inclusive) — độc lập với oracle. Fixture `item_idx`↔`item2id` có consistency test.
- Leakage trong input: không — input chỉ là user_id/top_n/as_of.

### Metric validity
- 15+ metric per-case, so **exact** cả list lẫn set; `all_fields_match` đòi 9 điều kiện (`memory_correctness_evaluator.py:99-102`). Lưu ý bất đối xứng nhỏ: loved/hated items chỉ đòi `set_match` còn categories đòi `exact` — chấp nhận được vì oracle sort deterministic (rating desc, item_id asc).
- Threshold duy nhất của hệ thống: `all_fields_match_mean>=0.95`, `success_rate>=1.0`, `future_leakage_max<=0.0` (`component_benchmarks.yaml:24-30`). `future_leakage_max` là max-statistic của metric `future_leakage` — đúng nhưng tên gây nhầm.
- `evaluate_thresholds`: metric "missing" → `passed=None` → `not_evaluated` chứ không fail (`_evaluator.py:48-51`) — hơi khoan, nhưng với dataset hiện tại không xảy ra.

### Độc lập & leakage
- Oracle độc lập thật; dataset regenerate từ oracle **nhưng** có sync-test `test_committed_dataset_matches_oracle` + hand-literal test → chấp nhận được.
- Leakage probe (`leakage_probe.py`) đúng: `future_only_items` + `max_n_interactions`.

### Reproducibility
- 3 lần chạy → metrics giống hệt (all 1.0, future_leakage 0.0). Deterministic. Result JSON có git_sha + config hash + provenance; **thiếu hash của dataset** → không phát hiện được dataset drift (chỉ có `dataset_path`).

### Mutation results
| Mutation | Kết quả | Bắt được? |
|---|---|---|
| love `>=`→`>` | all_fields_match 1.0→0.633 | ✅ gate FAIL |
| Bỏ sort timestamp recent_items | all_fields_match →0.233, recent_items_exact→0.179 | ✅ |
| Bỏ `check_profile_snapshot` | error_behavior_correct→0.0, all_fields_match→0.933 | ✅ gate FAIL (0.933<0.95) |
| **Bỏ filter `timestamp<=as_of` trong `MemoryTool.execute` (dòng 72-74)** | **mọi metric vẫn 1.0, gate PASS** | ❌ **Không bắt được** |

Mutation cuối là **coverage gap thật**: benchmark không bao giờ cho tool thấy dữ liệu chưa truncate mà guard vẫn pass (pretruncated do evaluator cắt trước; untruncated giữa chừng thì guard raise; untruncated ở max-ts thì không có gì để lọc). Code filter của tool trở thành dead-path đối với benchmark. (Guard vẫn là phòng tuyến thật trong production nên severity trung bình — nhưng benchmark báo cáo "point-in-time correctness = 1.0" trong khi chưa từng kiểm chứng đường filter của tool.)

### Coverage gaps khác
- Không có case item_idx mồ côi (không có trong item2id/meta); không có `top_n_categories=0`; không có user có interaction nhưng toàn item thiếu metadata; timestamp của mọi user đều distinct → sort-stability không được kiểm (tool dùng `sort_values` mặc định không stable, oracle `kind="stable"` — latent flake nếu fixture thêm tie).

**Kết luận**: benchmark memory là component benchmark **đáng tin nhất** — oracle độc lập, expected có kiểm tay, gate thật sự fail khi implementation hỏng. Trừ điểm vì 2 case trùng/near-trùng, single-domain fixture, và blind-spot đã chứng minh ở tool-side filtering.

---

## 2. EXECUTOR — `executor_dataset.jsonl` (18 case)

**Đường đi**: `PlanExecutor._execute(steps, user_request)` thật, `llm=None` có chủ đích (đúng — `_execute` không gọi LLM, `plan_executor.py:229-281`), tools thật trên fixture corpus.

### Case-level
- Expected chỉ gồm `all_steps_ok`, `step_error_kinds`, `bad_reference_count` — **không có expected data**. Kiểm tay các case khó (`exec_007/008/009/010` bad_reference lan truyền, `exec_011` unknown_tool, `exec_014` invented_id, `exec_016` id có trong request → không invented) — consistent với logic `_execute`.
- `exec_018` (steps=[]): `ok_count==n==0` → mọi metric = 1.0 **bất kể implementation** — case rỗng, không đo gì.
- Phân bố nghiêng failure-injection (13/18 case expect fail) — hợp lý cho error taxonomy nhưng nghĩa là "happy path data correctness" chỉ có 5 case `success`.

### Metric validity — **điểm yếu lớn nhất**
- `step_success_rate`, `error_kind_accuracy`, `reference_resolution_ok` chỉ đo **error taxonomy**, không đo **giá trị output**: một `FilterTool` trả sai items, `_resolve_refs` resolve sai path nhưng không raise, hay LookupTool trả thiếu field — tất cả vẫn `ok=True` → benchmark không phân biệt được.
- `kind_accuracy` denominator `max(n, expected_failures)` hợp lý; nhưng nếu executor **dừng sớm** (trả ít result hơn steps) thì expected-failure vắng mặt vẫn bị trừ điểm — tốt.
- Không threshold → `pass: null` (đúng thiết kế "chưa đặt gate").

### Mutation results
| Mutation | Kết quả |
|---|---|
| `bad_reference`→`exception` | error_kind_accuracy 1.0→0.861 ✅ |
| `_resolve_refs` không resolve `$N` | error_kind_accuracy→0.833, all_steps_ok→0.944, reference_resolution_ok→0.778 ✅ |

### Coverage gaps
- Không case nào assert **nội dung** step data (vd: `$1.candidates.*.item_id` resolve ra đúng ids nào; FilterTool `price_max=50` có loại item >50 không). Nếu muốn benchmark này đo "execution engine", nên thêm expected per-step output signature (số items, item_id cụ thể) cho ít nhất các case reference.
- Fault-injection infra (timeout/rate-limit/schema) đã chuyển sang `tests/agents/test_executor_error_taxonomy.py` — hợp lý, ghi rõ trong docstring.

**Kết luận**: đo đúng thứ nó tuyên bố (error taxonomy của execution engine) và nhạy với mutation, nhưng "executor quality" thực tế bao gồm cả correctness của resolved args/output — phần đó **không được đo**. Trung.

---

## 3. INTEGRATION — `integration_dataset.jsonl` (12 case)

**Đường đi**: `_execute` thật → `outcome_from_plan_results` → `compose_answer(mode=template)` — code thật, deterministic, không LLM.

### Case-level
- 12 case cover success/reference/empty/tool_error/reference_error/invented/multi_step/partial — expected `expected_status`+`min_items` hợp lý, kiểm tay consistent (vd `int_005`: LookupTool bad_reference nhưng FilterTool candidates vẫn thành items → status `ok` partial; `int_011` steps=[] → `no_result`).
- Không có expected item cụ thể — `min_items>=1` rất yếu (item sai vẫn đạt).

### Metric validity
- `contract_valid`: status + well-formed + min_items — bắt được mutation `errors=[]` (1.0→0.833).
- `no_mismatch`: presented ⊆ produced_ids — bắt được item bịa (1.0→0.417). **Metric tốt nhất của benchmark này.**
- `grounded_rate`: **vacuous trong template mode** — `compose_template` hardcode `grounded=True` (`compose_template.py:30`); chỉ có ý nghĩa ở mode="llm". Nên bỏ hoặc gate theo mode.
- `produced_ids` chỉ gom 3 key `candidates/items/ranked` — trùng `_ROWS_KEY`/`METADATA_ROW_KEYS` của outcome — consistent hiện tại nhưng là coupling thủ công (tool mới trả key khác sẽ bị đếm thiếu → false mismatch).

### Reproducibility & mutation
- 3 runs giống hệt. Mutation bị bắt cả 2. Không threshold → pass:null.

### Coverage gaps
- Không case assert **item nào** được trình bày (vd int_001 "games under $50" không kiểm item trả về có price≤50); không case mode="llm" (cần key); không case answer.text content.

**Kết luận**: benchmark boundary-contract thật và có răng (no_mismatch), nhưng chỉ đo "hình dạng" chứ không đo "đúng". Trung.

---

## 4. PLANNER — `planner_dataset.jsonl` (32 case) — cần LLM

**Đường đi**: `PlanExecutor.plan()` thật + LLM thật + `for_planner()` tools trên fixture. `reflect_rounds=0`.

### Case-level — **expected lệch schema tool thật (nghiêm trọng)**
Đối chiếu expected với `FILTER_KEYS`/`input_schema` thật (`tools/_schema.py:10-22`, `filter_tool.py:30-39`, `compile_filters.py`):

| Expected dùng | Thực tế |
|---|---|
| `filters.categories_none` (planner_011,020,022,027) | **Không tồn tại** trong FILTER_KEYS; FILTER_KEYS cũng không có category-exclusion nào |
| `filters.average_rating_min`, `rating_number_min` (014,024,030) | Key thật: `min_rating`, `min_rating_number` |
| `filters.item_ids`, `filters.exclude_items` (025,032) | Không tồn tại; exclusion thật là `exclude_item_ids` |
| `filters.exclude_items: "$1.all_interacted_items"` (025) | MemoryTool **không trả field này** (output_schema chỉ có loved/hated/recent/top_categories/price_range/love/hate_categories) |
| `args.candidates` trên FilterTool (002,009,010,022) | FilterTool không có arg `candidates` → `_unknown_args` sẽ reject ở execution |
| `sort_by`/`sort_order` (013,026) | Arg thật: `order_by`/`descending` |
| `MemoryTool` + `user_id:"$user_id"` (012,019,025,032) | `for_planner()` **không chứa MemoryTool** (`agent_tools.py:22-23`; chỉ `for_planner_memory()` có — dùng ở multi_turn/demo) và `$user_id` không phải ref hợp lệ (`$N.`/`$S.` only) |
| `item_vg_123/456/789/001` (002,009,011,016,022,028) | ID không tồn tại trong fixture corpus (dùng `Video_Games::vg_*`) — planner không execute nên "không sao", nhưng expected args chứa id ma |

Hệ quả: **kể cả LLM lập kế hoạch hoàn hảo theo schema thật, điểm argument_correctness/constraint_handling sẽ thấp** vì expected viết theo schema khác; ngược lại plan khớp expected sẽ **fail khi execute** (`_unknown_args`/unknown filter keys). Benchmark đang đo conformance với một spec không tồn tại. (Lưu ý: `SYSTEM_PROMPT` cũng dạy `categories_exclude` — key không hợp lệ — nên có thể dataset "bắt chước" prompt; cả hai đều lệch FILTER_KEYS → vấn đề hệ thống, không chỉ dataset.)

### Metric validity
- `clarification_precision`: `actual_question == expected_question` **so khớp chuỗi tuyệt đối** (`planner_benchmark.py:100`) — LLM không thể tái tạo byte-exact → với 10 case ambiguous/must-not-guess, precision≈0 ngay cả khi câu hỏi rất tốt. **Trần giả ngược**: best-case `clarification_precision_mean` ≈ 22/32 ≈ 0.69.
- `clarification_recall` và `refusal_to_guess`: **hai metric giống hệt nhau về mặt toán học** (cả hai = 1.0 nếu hỏi khi expected hỏi / không hỏi khi không expected) → một metric thừa, zero thông tin độc lập.
- `plan_validity`: `_extract_plan` đã guarantee list-of-dicts hoặc raise → **luôn = 1.0**, vacuous.
- `tool_selection_accuracy`: len phải bằng nhau mới chấm → 0.0 cho mọi lệch độ dài (khắt khe nhưng có phân biệt).
- `argument_correctness`/`constraint_handling`: chỉ so key có trong expected; default 1.0 khi expected không có filters → **inflate** trên case đơn giản.
- `reference_correctness`: chỉ check "có/không có `$` trong args" — nhị phân, yếu.
- Không threshold → pass:null. Không runs>1 → không đo stability dù docstring hứa.

### Độc lập/leakage/bias
- Expected là plan viết tay — không circular. Input không lẫn đáp án. Toàn bộ request là English, single-domain — bias giống fixture.

**Kết luận**: cần **viết lại dataset expected theo schema tool thật** (hoặc ít nhất regenerate expected từ tool contracts), quyết định category-exclusion support (hiện FilterTool không hỗ trợ → các case exclusion-theo-category không có plan hợp lệ nào), thống nhất toolset (`for_planner` vs `for_planner_memory`), thay exact-match question bằng judge/normalized-match, xóa metric trùng/vacuous, thêm threshold. **Tốn LLM** để validate.

---

## 5. GROUNDING — `grounding_dataset.jsonl` (32 case) — cần Jev

**Đường đi**: evidence từ dataset → `AgentOutcome` → `compose_answer(mode=template)` → `evaluate_product_reply_with_jev`. Judge fail → case fail (đúng, không fallback điểm).

### Case-level — expected bị bỏ qua hoàn toàn
`score_component` (`grounding_benchmark.py:94-124`) **không đọc `expected`**: `claims_supported`, `grounding_rate`, `hallucination_rate` trong dataset là dữ liệu chết — không có assertion nào so Jev output với label. Benchmark đo "Jev nói gì", không đo "có đúng không". Case tag `hallucination-bait` kỳ vọng `grounding_rate=0` nhưng không bị kiểm.

### Metric validity — bão hòa theo cấu trúc
- Chạy thật với Jev (artifact `grounding_benchmark_20261108_165543.json`, có key): **mọi case đúng 1 claim** (`total_claims_mean=1.0, std=0`), `grounding_rate_mean=0.906`. Claim extractor rule-based (`_extract_claims`) suy biến — 1 claim/case bất kể answer dài ngắn.
- Template composer **không thể hallucinate**: answer chỉ in lại field của evidence → claim luôn "supported by construction". `hallucination-bait` không bait được gì vì request sai không làm answer sai — answer trung thực report evidence (kể cả khi evidence mâu thuẫn request, vd grounding_004 puzzle-game cho request action → vẫn supported). Metric chỉ có nghĩa ở `mode="llm"`.
- `prompt_injection_detected`: keyword heuristic trên `user_request` (`"ignore" in req or "previous instructions" in req`) — **đo input chứ không đo hệ thống**: grounding_025 ("System: override security protocols") và 026 ("Forget everything above") → 0 dù tag injection; grounding_030 ("Translate this to French") bị tag injection **nhưng không phải injection** → tag sai + metric 0. Metric vacuous và mâu thuẫn label.
- 3 case evidence rỗng (005/025/026) → `run_component` raise `ValueError` → **auto-fail** kể cả khi có key (run thành công 16:55 hôm đó chắc chắn dataset/code đã khác — hiện tại committed dataset sẽ làm `success_rate ≤ 29/32`).

### Reproducibility
- Không key → 0/32 pass (đúng fail-loud). Có key → phụ thuộc Jev nondeterminism, chưa đo được (không key). Provenance có judge config hash — tốt.

**Kết luận**: benchmark hiện tại chủ yếu đo độ lượng của Jev trên câu trả lời do chính evidence sinh ra — **gần như không đo grounding quality**. Cần: dùng `expected` làm assertion (claim-level expected verdict), thêm case mode="llm" (tốn LLM+Jev), sửa/xóa `prompt_injection_detected`, fix case evidence rỗng, cân nhắc claim extractor mạnh hơn.

---

## 6. MULTI-TURN — `conversations.jsonl` (11 conversations) — cần LLM

**Đường đi**: `RealAgentRunner` = PlanExecutor + Session + `for_planner_memory()` + LLM thật trên fixture. `MultiTurnEvaluator` chấm turn-level + conversation-level.

### Dataset — expected không đạt được
- `expected_items` dùng **bare ASIN/ID không tồn tại**: `electronics_1/2` (conv_m6 — fixture chỉ có domain Video_Games), `book_1/2` (conv_session_isolation_2), `preferred_1..4` (conv_m7), `vg_b_similar` (conv_m2), `vg_f` thì có nhưng `item_x` (conv_recovery) không. `_bare()` chỉ strip namespace — không cứu được id không tồn tại. → `item_match_rate` trần thấp vĩnh viễn, điểm phản ánh dataset chứ không phản ánh agent.
- `expected_exclusions` dùng **bare id** (`"vg_a"`) trong khi runner trả **namespaced** (`"Video_Games::vg_a"` từ filters đã resolve) → `set(expected).issubset(actual)` luôn False → `exclusion_compliance=0` cấu trúc cho conv_m3/m4 (đã fix `_bare` cho items nhưng **quên fix exclusions**).
- conv_m7 "long_term_memory" không có user_id/context nào → MemoryTool không có gì để retrieve → underspecified.
- Nhiều turn `expected_items=[]` → `item_match_rate=1.0` auto-pass; `expected_exclusions={}` → `exclusion_compliance=1.0` auto-pass → tỷ lệ case "miễn điểm" cao.

### Metric validity
- `item_match_rate`: recall-only (|∩|/|expected|), item thừa không bị phạt.
- `reference_correctness`: **gần như vô nghĩa** — nó tìm step có `"$"` trong `args`, nhưng `_execute` ghi `entry["args"] = _simplify_args_for_log(resolved_args)` **sau khi resolve** → step resolve thành công không còn `"$"`; chỉ step fail (bad_reference/invented_id/unknown) giữ raw args chứa `"$"`. Kết quả: metric chủ yếu đếm các step **đã fail** → giá trị thực tế ≈ 0 khi có ref-step lỗi và `None` (not measurable) khi mọi ref resolve tốt — không đo được "accuracy" theo nghĩa thông thường.
- `context_retention`: chỉ check `shown_items` count **non-decreasing** — Session là append-only (có cap 50 nhưng count vẫn không giảm) → **luôn 1.0**, vacuous; không đo "có nhớ đúng nội dung cũ không".
- `exclusion_compliance` semantics: so filters **đã dùng** (từ `r["args"]["filters"]` — args đã simplify, cắt list >5 phần tử) chứ không so items thực tế bị loại — đo "có khai báo exclusion" chứ không "có tuân thủ".
- `turn_success`/`conversation_success`: chỉ execution success.
- Double session update: `PlanExecutor._update_session` (executor tự update khi `self.session` set) **và** `MultiTurnEvaluator._update_session` cùng add shown_items → có thể duplicate (add_shown_items không dedupe, chỉ extend+trim) — session state bị phình, ảnh hưởng `$S.*` refs.

### Reproducibility
- Chưa từng chạy với LLM → **toàn bộ metric chưa được kiểm chứng đầu-cuối**. Tests (`test_with_session.py`) dùng fake runner trả đúng expected → chỉ test cơ chế evaluator, không phát hiện dataset bugs trên.

**Kết luận**: cần viết lại dataset expectations (namespaced ids thật, chỉ item tồn tại, exclusions so cùng không gian id), sửa `reference_correctness` (đọc raw args trước resolve hoặc đánh dấu step dùng ref), định nghĩa lại `context_retention` (vd so nội dung shown_items/candidates turn trước có còn được dùng đúng không), chạy thử 1 lần với LLM trước khi tin bất kỳ con số nào. **Tốn LLM**.

---

## 7. Benchmark trên data thật & campaign/ablation — spot check

- `candidate_recall.py`, `ranking_eval.py`, `run_agent_eval.py`: dùng `select_fit_target` trên temporal split; `map_split.py:58-59` gọi `check_split_temporal_order` + `check_no_duplicate_across_splits`; held-out targets; `category_oracle` được label rõ "upper bound, never report as result"; provenance hash (fit_data_hash, source_fingerprint, request content sha256, resume identity). `drop_seen` loại item đã thấy khỏi fit. **Nhìn đúng chuẩn** — không thấy leakage ở mức spot-check; chưa verify từng hàm metric.
- `campaign_runner.py`: orchestrate subprocess chạy experiment thật, auto comparison pairs, bootstrap CI (`_statistics.py`). `ablation/`: load scored data từ experiment dirs thật, paired bootstrap. Không thấy fake/judge-fallback. **Chưa xác minh đầy đủ** — chỉ đọc lướt.
- `evaluate_product_reply.py` (non-Jev): rule-based evaluator — chưa audit sâu.

## 8. Vấn đề framework (ảnh hưởng mọi component)

1. `run_benchmark_cli.py:200-202` **không `mkdir` output_dir** → crash `FileNotFoundError` nếu `experiments/agent_eval/component_benchmarks/` chưa tồn tại (đã gặp thực tế; `_run_all.py` thì có mkdir). Bug nhỏ nhưng benchmark không self-contained.
2. Result JSON ghi `dataset_path` nhưng **không hash dataset** → không tái lập/chứng minh dataset version (provenance thiếu một mắt xích).
3. `_run_all.aggregate_results` trung bình metric trên các case **có metrics** (case fail bị loại khỏi mean, chỉ đếm `failed_cases`) — mean có thể "đẹp" hơn thực tế nếu nhiều case fail; may là `success_rate` vẫn report riêng. Nên hiển thị mean kèm số case đóng góp.
4. `success`(chạy được) vs `pass`(đạt threshold) tách đúng; metric không threshold → `pass:null`/`not_evaluated` — tốt, không có implicit PASS.
5. Mọi benchmark component dùng **chung fixture 1 domain, ~20 user nhân tạo** — dataset bias lớn cho planner/executor/integration/multi-turn; memory ít nhất có oracle nên ít bị ảnh hưởng.

## 9. Ưu tiên sửa / viết lại

| # | Việc | Tốn LLM/Jev? |
|---|---|---|
| 1 | **Grounding**: viết lại — dùng `expected` làm assertion, thêm mode="llm" cases, sửa `prompt_injection_detected` (bỏ hoặc judge thật), fix 3 case evidence rỗng, claim extractor mạnh hơn | Jev (+LLM nếu mode llm) |
| 2 | **Multi-turn**: sửa dataset (namespaced/real ids, exclusions cùng không gian id, bỏ case không-achievable), sửa `reference_correctness`+`context_retention`, chạy thật 1 lần để calibrate | LLM |
| 3 | **Planner**: regenerate expected theo FILTER_KEYS/arg schema thật, quyết định category-exclusion (hiện không support), thống nhất toolset memory, thay exact-question-match, xóa metric trùng/vacuous, thêm thresholds | LLM |
| 4 | **Executor**: thêm expected-data assertions (resolved ref values, filter correctness) hoặc thu hẹp claim; bỏ/vô hiệu exec_018; cân nhắc thresholds | Không |
| 5 | **Integration**: bỏ `grounded_rate` ở template mode (hoặc chỉ tính khi mode=llm); thêm content assertions cho case đơn giản (item thỏa constraint); giữ `no_mismatch` | Không (LLM nếu thêm mode llm) |
| 6 | **Memory**: xóa/thay case trùng 016↔030 và near-dup 017↔021; thêm multi-domain fixture; quyết định có test tool-side `as_of` filter không (hiện là dead-path với benchmark); thêm dataset hash vào provenance | Không |
| 7 | Framework: mkdir output_dir trong `run_benchmark_cli`; dataset content hash; mean kèm coverage count | Không |

## 10. Chưa xác minh được

- Planner end-to-end (không LLM key) — mismatch dataset↔schema đã verify tĩnh, nhưng điểm số thực tế chưa đo.
- Grounding với Jev live (không key tại thời điểm audit; đã phân tích artifact run thành công 16:55 + code path).
- Multi-turn runner thực tế (không LLM key) — mọi nhận xét metric/dataset là tĩnh + suy luận từ code.
- Campaign/ablation/regression CLI chạy đầy đủ; `evaluate_product_reply.py` (non-Jev); `memory_utility.py`/`analyze_metric.py` (phân tích memory utility — ngoài phạm vi 5 component chính).
- Full test suite baseline ~1414 passed — chỉ chạy subset evaluation (85 passed).
- `experiments/` untracked trong repo chính có thêm artifact cũ chưa rà hết.
