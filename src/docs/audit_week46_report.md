# Audit Week 46 — Tasks 1, 3, 4, 5 (read-only)

- **Repo**: `agentic-rag-for-rcm-sys`, thư mục `src`
- **HEAD**: `0354f6cc7237ada77665aa503632c4135b5b0c72`
- **Branch thực tế**: `tools-building` (task ghi `refactor-phase-0`; `refactor-phase-0` tồn tại nhưng không phải nhánh đang checkout — HEAD là merge của refactor-phase-0 vào tools-building)
- **`git status`**: sạch trước audit (chỉ phát sinh `experiments/` output từ các lần chạy benchmark kiểm chứng, và file `nul` rác do lệnh redirect Windows — đã xóa)
- **Môi trường**: KHÔNG có `LLM_BASE_URL`, `LLM_API_KEY`, `TYPESAFE_API_KEY`, `OPIK_*` (đã kiểm `env | grep`). `resource/` tồn tại đầy đủ (raw/cleaned/splits/corpus...). `opik` package đã cài (v2.2.143).

## 0. Baseline test

Lệnh: `cd src && PYTHONPATH=. python -m pytest tests/ -q`

**Kết quả: 1327 passed, 8 skipped, 2 xfailed, 13 warnings in 59.57s — 0 failed.**

(Số liệu cũ 368/1320 không khớp; số thật là 1327 passed.)

Skip/xfail — tất cả là skip có chủ đích, không phải thiếu key/dữ liệu:

| Test | Lý do |
|---|---|
| `test_stage4_integration.py` ×2 | `pytest.skip("Requires full splits setup")` — tests/data/pipeline/test_stage4_integration.py:47,89 |
| `test_memory_correctness.py` ×2 | skip do cache môi trường + "Leakage detection test needs update for new MemoryTool signature" — tests/evaluation/component/test_memory_correctness.py:97,142 |
| `test_sql_filter_validation.py`, `test_sql_hardening.py` ×4 | `@pytest.mark.skip("Config patching needs refactoring after corpus moved to package/corpus")` |
| `test_inference_behavior.py` ×2 xfail(strict) | known issues a/b trong `parse_llm_reply` — tests/agents/test_inference_behavior.py:257,264 |

---

## 1. Bảng tóm tắt

| Task / subtask | Trạng thái | Bằng chứng ngắn |
|---|---|---|
| 0. Baseline pytest | Xong | 1327 passed / 8 skipped / 2 xfailed / 0 failed |
| 1. Opik | Một phần | Chỉ có `scripts/evaluation/opik_poc.py` (PoC in "Would create...", metric placeholder 0.95); không có `@opik.track`, không span instrumentation; các file `opik_phase_*.md` KHÔNG tồn tại trong repo |
| 3.1 Audit bias/leakage/reproducibility | Một phần | Có leakage guard (`package/data/leakage/`, `LeakageError`, `leakage_probe`), split protocol có test chống leak train→test, ablation có bootstrap CI + McNemar; chưa thấy audit riêng về dataset bias / scoring bias |
| 3.2a comparison_pairs auto-gen | **Lỗi xác nhận** | `campaign_runner.py:46-51` sinh `comparison_pairs` local nhưng `_run_comparisons` (dòng 303) đọc `self.config.comparison_pairs` → auto-gen không bao giờ được dùng |
| 3.2b metrics keys | Xong (có caveat) | `_load_experiment_metrics` đọc `summary[agent][kind]["all"]` — khớp cấu trúc `save_experiment` + `trajectory/summarize.py:88`; không verify được trên metrics.json thật vì `experiments/` không có run agent_eval nào |
| 3.2c campaign_id vào config.yaml exp | **Không** | campaign_id chỉ nằm trong tên trajectory_file (campaign_runner.py:218) và campaign_result.json; không truyền vào run_agent_eval → config.yaml của exp không có campaign_id |
| 3.2 `_run_all.py` | Một phần | Executor luôn fail (không có evaluator); run_all luôn exit 0; `success_rate` default 1.0 → nguy cơ PASS giả; không có caller trong code (chỉ docs) |
| 3.3 Multi-turn | Chưa | `_run.py:32` `SystemExit("real runner not implemented yet")`; `reference_correctness` hardcode 1.0 (multi_turn_evaluator.py:187-190) |
| 3.4 statistics/_bootstrap | Một phần | Được `reporting/_generator.py` dùng; campaign KHÔNG dùng (tự average mean); ablation có `_statistics.py` riêng (bootstrap + McNemar); có mean/std per-case runs trong `_evaluator.py`, chưa có CI theo multiple runs trong campaign |
| 4. Component verification | Một phần | memory = real+oracle (PASS thật, synthetic fixture); planner = real LLM+tools (không chạy được thiếu key); grounding = **fake/circular**; integration = self-referential; executor = chưa implement |
| 4. except Exception audit | Xong | 10 site trong package/evaluation; 0 site trong package/inference, package/api; phân loại bên dưới |
| 5.1-5.3 Hygiene paths/seed/provenance | Một phần | data_paths.yaml là nguồn duy nhất; có vài path tương đối hardcode; seed có trong YAML; provenance rất đầy đủ (git_commit, source_fingerprint, env, hardware) nhưng component benchmark thiếu provider/model hash |
| 5.4 .md inventory | Xong | 17 file .md liệt kê + đề xuất bên dưới; `repo reading.md` không tồn tại — thực tế là `Project repository reading 29.10.md` |
| 5.5 Mock/fake inventory | Xong | Phân loại bên dưới; phát hiện script báo thành công mà không làm gì + 1 script import hỏng |

---

## 2. Chi tiết

### Task 1 — Opik

**Hiện có trong repo:**

- `scripts/evaluation/opik_poc.py` (185 dòng): load experiment `exp_002` từ `get_data_paths().experiments_dir / "agent_eval" / "exp_002"` (dòng 145), in ra "Would create Opik dataset..." (dòng 111), "Would create Opik experiment..." (dòng 134) — **không gọi Opik API thật**, chỉ in pattern. `RCMMetricWrapper.score()` trả `value = 0.95  # Placeholder` (dòng 56). Import `opik` và `BaseMetric` thật (dòng 27-29) nhưng không dùng tới mức tạo dataset/experiment.
- `package/evaluation/__init__.py` và toàn bộ `package/` không có `@opik.track` hay span instrumentation nào (grep `opik` toàn repo chỉ ra 2 file: opik_poc.py và `Project repository reading 29.10.md`).
- **`opik_phase_*.md` không tồn tại** ở bất kỳ đâu trong repo (`find . -name "opik_phase*"` → rỗng; tìm cả repo root → rỗng).

**Tài liệu `Project repository reading 29.10.md` §8.4 (dòng 428-438, 836, 923)** ghi nhận:

- A0/A1/A2 phase docs được tham chiếu như tài liệu ngoài repo (không có file trong src).
- Kết luận đã có: "Opik cannot replace RCM metrics; recommends Option B: Complementary Integration"; "PoC demonstrated: load 58 trajectories, create Opik dataset, log metrics as metadata... Feasible, 1-2 weeks effort"; "PoC only. No live Opik server deployed. No span instrumentation in RCM agents yet."

**Kết luận Task 1:** Đã làm đến bước PoC script (pattern demo, không gọi API thật) + đánh giá/framework comparison ghi trong repo reading. Còn thiếu so với yêu cầu: (a) các file `opik_phase_0/1/2*.md` không nằm trong repo — chỉ được tóm tắt trong repo reading; (b) không có tracing/span instrumentation trong agent code; (c) không có quyết định Replace/Complement/Keep Current dạng văn bản quyết định trong repo (chỉ có đánh giá "Option B" trong repo reading + docstring opik_poc.py); (d) chưa verify opik_poc.py chạy được — chưa chạy thử vì cần `exp_002` trong experiments/ (hiện `experiments/agent_eval/` chỉ có `component_benchmarks/`).

### Task 3 — Evaluation system

#### 3.1 Dataset bias / scoring bias / data leakage / reproducibility

**Có:**

- Leakage guard runtime: `package/data/leakage/` gồm `check_no_duplicate_across_splits.py`, `check_profile_snapshot.py`, `check_split_temporal_order.py`, `_error.py` (`LeakageError`); `package/memory/memory_tool.py` raise `LeakageError` khi nhận full frame + as_of (được test bởi case `correctness_015/016` trong memory_correctness_dataset — đã PASS trong lần chạy thật bên dưới).
- Split protocol chống leakage: `package/evaluation/recommender/core/evaluation_protocol.py` + test `test_uses_train_plus_validation_to_fit_and_never_leaks_test_into_fit` (PASSED).
- EDA diagnostic: `package/data/eda/diagnose_splits.py`, `scripts/eda_diagnostic/diagnose_splits.py`.
- Thống kê: `package/evaluation/statistics/_bootstrap.py` (bootstrap CI, paired bootstrap, Wilcoxon/Mann-Whitney); `package/evaluation/ablation/_statistics.py` (bootstrap_ci + McNemar riêng); `reporting/_generator.py:14-19` import và dùng bootstrap CI.
- Reproducibility: `save_experiment` ghi `seed`, `git_commit`, `source_fingerprint`, `environment` (versions), `hardware`, `runtime_seconds`, dataset hashes vào `config.yaml` (save_experiment.py:63-75); seeds tập trung trong `configs/eval/baselines.yaml:5` (seed: 42), `configs/agent/ablation.yaml:16`, `configs/eval/memory_utility.yaml:11`, `configs/eval/ranking_diagnostics.yaml:5`, `configs/eval/tool_validation.yaml:8`.

**Chưa thấy:** audit/test riêng về *dataset bias* (phân phối domain/user) hay *scoring bias* (judge bias) — chỉ có leakage và reproducibility. Ghi "chưa xác minh đầy đủ" cho phần bias.

#### 3.2 Campaign + run_all

**File**: `package/evaluation/campaign/campaign_runner.py` (408 dòng), config `configs/evaluation/campaign.yaml`.

**(a) comparison_pairs auto-gen — LỖI XÁC NHẬN:**

- `run_campaign()` dòng 46-51: tính `comparison_pairs` local (auto-gen baseline-vs-rest khi `self.config.comparison_pairs` rỗng và có `parameter_grid`).
- `_run_comparisons()` dòng 303: `for exp_a, exp_b in self.config.comparison_pairs:` — đọc lại từ config, **bỏ qua biến local vừa sinh**.
- `configs/evaluation/campaign.yaml` có `comparison_pairs: []` + `parameter_grid` → với config hiện tại, `run_campaign` in "Auto-generated N comparison pairs" nhưng `_run_comparisons` lặp trên list rỗng → `comparisons = {}`. Auto-gen hoàn toàn vô hiệu. (May là `if comparison_pairs:` ở dòng 70 dùng biến local nên block được gọi, nhưng bên trong không có pair nào → trả `{}`.)

**(b) metrics keys:** `_load_experiment_metrics` (dòng 250-285) parse `saved -> <dir>` từ stdout, đọc `metrics.json`, lấy `data.get("summary", ...)` rồi duyệt `agent → kind → segment`, chỉ lấy `segment == "all"`, flatten key `{agent}_{kind}_{metric}`. Cấu trúc khớp: `save_experiment(metrics={"k":k,"summary":summary})` (run_agent_eval.py:456) và `trajectory/summarize.py:87-88,103` tạo bucket `"all"`. **Caveat**: mọi giá trị int/float đều bị coi là metric — kể cả `n` (sample count) → key `agent_kind_n` lọt vào metrics so sánh. Chưa verify trên metrics.json thật (không có exp run nào trong `experiments/`).

**(c) campaign_id vào config.yaml của exp — KHÔNG:**

- `_build_config_overlay` (dòng 215-235) chỉ ghi `agents`, `allow_missing_corpus_sources`, `trajectory_file` (= `{campaign_id}_{exp}_run{n}_trajectories.jsonl`), `per_segment`, `inference_mode`, `reflect_rounds`, `baselines.seed`. Không có field campaign_id.
- `run_agent_eval.py` nhận campaign_id gián tiếp duy nhất qua tên trajectory_file; `save_experiment` config dict (run_agent_eval.py:437-456) không chứa campaign_id.
- campaign_id chỉ xuất hiện trong `campaign_result.json` (campaign_runner.py:77) và tên file trajectory. → **Không truy vết được exp → campaign từ config.yaml một mình.**

**`_run_all.py` (290 dòng):**

- 5 component hardcode ở dòng 23-29: memory, planner, executor, grounding, integration.
- **Executor**: `_get_evaluator` (run_benchmark_cli.py:19-50) không có nhánh `executor` → `NotImplementedError` → subprocess exit 1 → `results["executor"] = None` → aggregate ghi `{"status": "failed"}`. Đã chạy thật: `python -m package.evaluation.component.run --component executor ...` → traceback NotImplementedError, exit code 1 (xác nhận bằng `$?`=1). `executor_benchmark.py` không tồn tại; `executor_dataset.jsonl` (35 case) và `configs/eval/component_benchmarks.yaml` có entry `executor.reflect_rounds: 2` — config mồ côi.
- **Exit code**: `main()` (dòng 265-286) không `sys.exit` theo kết quả → **luôn exit 0** kể cả khi component fail. `_run_all` cũng không có caller nào trong code (ch chỉ docs: EXECUTION.md:18, repo reading:883).
- **`success_rate` default 1.0**: `aggregate_results` dòng 138 `result.get("success_rate", 1.0)` — nếu file kết quả thiếu key này, component được tính PASS giả. (Trên thực tế `_evaluator._aggregate_metrics` luôn ghi `success_rate` — dòng 192 — nên default chỉ là rủi ro khi file bị cắt/ghi tay.)
- Metric aggregation (dòng 104-118) chỉ trung bình các metric xuất hiện trong `per_case_results`; case fail (`success=False`, `metrics={}`) bị loại khỏi mean → mean metric chỉ tính trên case chạy được, tách biệt với `success_rate`. Có ghi chú trong report nhưng dễ đọc nhầm.

**Chạy thật các component CLI** (không LLM/key):

| Component | Lệnh | Kết quả |
|---|---|---|
| memory | `run --component memory --dataset ...memory_correctness_dataset.jsonl` | **30/30 PASS**, mọi metric = 1.0000, success_rate 1.0 — real MemoryTool vs oracle độc lập trên synthetic fixture |
| integration | `run --component integration --dataset ...integration_dataset.jsonl` | 35/35 "Passed", contract_valid_mean 0.6857 — nhưng xem Task 4: không chạy component thật |
| executor | như trên | exit 1, NotImplementedError |
| grounding | `run --component grounding --dataset ...grounding_dataset.jsonl` | 32/32 "Passed", grounding_rate_mean 0.9062, success_rate 1.0 — **fake PASS** (xem Task 4) |
| planner | `run --component planner --dataset ...planner_dataset.jsonl` | crash `ValueError: LLM base_url not configured` (planner_benchmark.py:62) — **không chạy được vì thiếu LLM_BASE_URL/LLM_API_KEY**, không phải lỗi code |

#### 3.3 Multi-turn

- `package/evaluation/multi_turn/_run.py:32`: `raise SystemExit("real runner not implemented yet")` — CLI parse args xong là thoát. `load_conversations()` (dòng 35-63) có thật nhưng không ai gọi trong runtime (chỉ `__main__`).
- `multi_turn_evaluator.py`: `MultiTurnEvaluator.evaluate_conversation` có logic thật (session, per-turn scoring, aggregation) nhưng cần `agent_runner` do caller truyền — không có runner thật nào trong repo gọi nó.
- **`reference_correctness` là placeholder 1.0**: dòng 187-190 — cả hai nhánh đều `= 1.0` ("Placeholder: assume correct if references used"). `context_retention` (dòng 259-271) và `reference_accuracy` fallback cũng default 1.0 khi thiếu data → nhiều metric multi-turn là PASS giả mặc định.
- `run_multi_turn_cli` không có caller ngoài `__main__` của chính nó.

#### 3.4 statistics/_bootstrap.py

- Được dùng bởi: `package/evaluation/reporting/_generator.py:14-19` (import bootstrap_confidence_interval, paired_bootstrap_difference, aggregate_metrics, compute_percentiles).
- KHÔNG được campaign dùng: `campaign_runner.py` không import statistics; `_compare_experiments`/`_average_metrics` chỉ tính mean/delta thuần (dòng 321-376), `statistical_settings` trong campaign.yaml (confidence_level, bootstrap_samples, paired_comparison) **không được đọc ở đâu trong campaign_runner** — grep `statistical_settings` chỉ thấy trong yaml.
- Ablation có bộ riêng `ablation/_statistics.py` (bootstrap_ci + McNemar) — trùng chức năng, không dùng `_bootstrap.py`.
- Mean/std theo multiple runs: `ComponentEvaluator.run_benchmark(runs=N)` lặp case và `_average_results`/`_aggregate_metrics` cho mean/std/min/max (evaluator.py:119-194) — có, nhưng ở component level; campaign level chỉ mean qua `_average_metrics`, không std/CI.

### Task 4 — Component verification

| Component | Implementation thật? | Provider/tool | Ghi chú |
|---|---|---|---|
| memory | **Có** — `MemoryCorrectnessEvaluator` chạy `MemoryTool` thật (memory_correctness_evaluator.py:46-62), so với oracle độc lập `compute_memory_oracle` + `leakage_probe`; dataset 30 case có oracle tính sẵn, kể cả negative/leakage-guard cases | Data: synthetic fixture (`fixtures/create_test_interactions.py` etc.) — fixture được build bởi code, oracle tính độc lập, không phải mock runtime | PASS thật nhưng trên dữ liệu synthetic, không phải Amazon thật |
| planner | **Có** — `PlannerBenchmark` dùng `PlanExecutor` thật + `build_llm_provider` thật + `build_tools`/`ItemKNNRecommender`/`BaselineScorer` thật trên fixture corpus (planner_benchmark.py:21-76) | LLM thật (OpenAI-compatible), tools thật | Không verify được — thiếu LLM key; code path đúng |
| executor | **Không** — không có evaluator | — | `_get_evaluator` raise NotImplementedError; dataset + config tồn tại nhưng không có code |
| grounding | **Một phần, có vấn đề nghiêm trọng** — `GroundingBenchmark.run_component` **tự sinh câu trả lời** từ evidence (grounding_benchmark.py:39-52: `"{title} is a good choice."`, `"It belongs to the {category} category."`, `"The price is ${price}."`) rồi hỏi Jev xem có supported không → **circular**: answer được build từ chính evidence nên grounding_rate gần như luôn cao; không chạy inference/grounding component thật | Jev (TYPESAFE_API_KEY) hoặc rule-based fallback | Xem phân tích except bên dưới — **đã PASS giả 32/32 khi không có key** |
| integration | **Không chạy component thật** — `IntegrationBenchmark` chỉ kiểm tra các dict **có sẵn trong case_input** (`plan`, `executor_output`, `memory_profile` là input của case, không phải output của component chạy) — integration_benchmark.py:19-98 | Không | Self-referential: nó "test" dữ liệu fixture, không test boundary thật; metric `contract_valid`/`no_mismatch` trùng nhau 100% (dòng 110-119 gán cùng giá trị) |

**Audit `except Exception`** — 10 site trong `package/evaluation` (+0 trong `package/inference`, `package/api`; không có bare `except:` hay `except (Exception, ...)`):

| Vị trí | Xử lý | Đánh giá |
|---|---|---|
| campaign_runner.py:177 | set `success=False`, `error=str(e)` vào ExperimentRun | OK — lỗi được flag vào kết quả |
| component/_evaluator.py:77 | `success=False`, `error=str(e)`, metrics={} | OK — lỗi flagged; nhưng case fail bị loại khỏi metric mean (xem 3.2) |
| component/_run_all.py:70,142 | ghi `results[component]=None` / `{"status":"error"}` | OK — flagged, nhưng exit code vẫn 0 |
| component/benchmarks/grounding_benchmark.py:62 | catch mọi lỗi (kể cả JevProvider init raise do thiếu TYPESAFE_API_KEY) → trả `{"jev_error": str(e)}` | **NGUY HIỂM**: score_component thấy không có `jev_result` → rơi vào rule-based fallback → `evidence>0` ⇒ `grounding_rate=1.0` (dòng 101-104) → **Jev sập/thiếu key vẫn cho PASS**. Đã xác nhận thực nghiệm: chạy grounding benchmark không có TYPESAFE_API_KEY → 32/32 passed, grounding_rate_mean 0.9062 hoàn toàn từ fallback |
| component/benchmarks/memory_utility.py:29 | `except Exception: pass` khi load config | Chấp nhận được — config optional cho phân tích tương thích; ghi comment rõ |
| multi_turn_evaluator.py:55 | turn fail → `success=False`, `conversation_success=False`, `failure_stage`, `error` | OK — flagged, dừng conversation |
| product_reply/evaluate_product_reply_with_jev.py:102 | top-level catch → trả `evaluation_state="provider_error"`, claims=[] | OK — explicit state, không fake score (đã được sửa so với bản cũ trả mid-range) |
| product_reply/evaluate_product_reply_with_jev.py:298 | **Jev batch call fail → mark TẤT CẢ claims trong batch là `verdict="unsupported"`, `noul=0.0`** | **NGUY HIỂM**: lỗi API Jev bị đếm vào `unsupported_count` → `unsupported_count`/`hallucination_rate` phình to như thể model hallucinate. Phân biệt được duy nhất qua `why` chứa "Jev error:" — caller (`grounding_benchmark.score_component`) KHÔNG đọc `why`/`evaluation_state` → không phân biệt được lỗi judge với lỗi thật |
| product_reply/evaluate_product_reply_with_jev.py:360 | print + re-raise → bắt bởi except ở dòng 102 → provider_error | OK |

**`evaluate_product_reply_with_jev` còn một lỗ hổng nữa**: `JevProvider(...)` được khởi tạo ở dòng 53 **ngoài** try → thiếu TYPESAFE_API_KEY raise ValueError propagate thẳng ra caller (không trả provider_error dict). Trong grounding_benchmark bị catch ở dòng 62 → fallback rule-based (fake pass như trên). Trong `scripts/evaluation/evaluate_with_jev.py` sẽ crash — hành vi đúng nhưng không nhất quán với contract "always return dict".

**Benchmark PASS nhưng thực chất fake:**

1. **grounding** — như trên: (i) answer tự sinh từ evidence → circular; (ii) Jev fail → rule-based cho grounding_rate=1.0; (iii) provider_error → `total_claims=0` → grounding_rate=0, hallucination_rate=0, vẫn `success=True`.
2. **integration** — không chạy component nào; chỉ so dict input với expected.
3. **multi_turn** — chưa implement; metric mặc định 1.0.
4. **executor** — luôn fail (không phải fake pass nhưng chiếm slot trong run_all).
5. **opik_poc.py** — metric `0.95` placeholder, mọi thứ chỉ in "Would create...".

**Happy/edge/failure coverage:**

- memory: có negative cases (user_not_exists, empty_history), edge (tie_break, null_prices, equal_prices, outlier_price, duplicate_items, top_n_exceeds), leakage_guard (expect_error LeakageError + control không raise), love_hate variants → coverage tốt trên fixture.
- planner dataset 32 case, grounding 32, integration 35, executor 35 — chưa audit nội dung từng case (ngoài phạm vi nhanh); planner/grounding/executor/integration datasets tồn tại nhưng executor không có evaluator.
- `tests/evaluation/component/` có test cho memory correctness + controlled tools.

### Task 5 — Repo hygiene & runtime integrity

#### 5.1/5.2/5.3 Paths, params, seed, provenance

- **Path tập trung tốt**: `configs/path/data_paths.yaml` là nguồn duy nhất; code đi qua `get_data_paths()`; outputs qua `output_dir(<key>)`. Comment yaml map rõ từng consumer.
- **Path hardcode còn sót** (ngoài data_paths):
  - `planner_benchmark.py:46` `config_path = "configs/agent/llm.yaml"` — path tương đối CWD, chỉ đúng khi chạy từ src_root (run_benchmark_cli không cd; nếu gọi từ chỗ khác sẽ miss → llm_config rỗng → ValueError).
  - `run_campaign.py:28` `DEFAULT_CAMPAIGN_CONFIG = "configs/evaluation/campaign.yaml"` — tương đối CWD.
  - `campaign_runner.py:129` `"scripts/evaluation/run_agent_eval.py"` — tương đối nhưng subprocess `cwd=src_root` nên OK.
  - **Docstring sai**: `run_campaign.py:10` vẫn ghi "campaign config path is hardcoded to package/evaluation/campaign/example_campaign.yaml" — path đó không tồn tại; thực tế đã có argparse `--campaign-config` với default `configs/evaluation/campaign.yaml`. Docstring lỗi thời.
- **Tham số hardcode chưa vào YAML**: `_run_all.py:23-29` hardcode danh sách 5 component + dataset paths; `opik_poc.py:145` hardcode `exp_002`; `run_campaign.py` DEFAULT path (đã có argparse); `grounding_benchmark.py:88` `prompt_injection_detected: 0.0` hardcode (Jev không detect); `multi_turn_evaluator.py` nhiều default 1.0.
- **Seed**: có trong YAML (baselines.seed=42 etc.), campaign truyền `experiment.random_seed` → overlay `eval/baselines.baselines.seed` (campaign_runner.py:235). `_bootstrap.py` nhận `random_seed` optional. Component benchmark KHÔNG có seed (deterministic trừ LLM/Jev).
- **Provenance — rất đầy đủ ở agent_eval**: `build_run_provenance` (git sha + dirty flag + prompt/tool-schema hashes + limits) → `config.yaml.provenance` (run_agent_eval.py:322,448); `save_experiment` ghi `git_commit`, `source_fingerprint`, `environment`, `hardware`, `seed`, dataset file hashes (save_experiment.py:63-75).
- **Provenance thiếu ở component benchmark**: `run_benchmark_cli.py:152-157` ghi `git_sha`, `config` (component config — với planner là `{}` vì LLM config đọc riêng từ llm.yaml), `dataset_path`, `runs` — **không ghi LLM provider/model/base_url hash, không ghi TYPESAFE model** → grounding/planner runs không tái lập được provider nào đã chấm.

#### 5.4 Danh sách .md trong src (trừ experiments/)

Không có `src/repo reading.md`; file tương đương là **`Project repository reading 29.10.md`** (tồn tại, ~900 dòng, là tài liệu tổng quan duy nhất tham chiếu hầu hết module). `AGENTS.md` là rules file GitNexus (always-on) — bắt buộc giữ.

| File | Nội dung | Được tham chiếu bởi | Đề xuất |
|---|---|---|---|
| `AGENTS.md` | GitNexus rules (always-on) | hệ thống rules | **GIỮ** |
| `Project repository reading 29.10.md` | Tài liệu đọc repo tổng hợp (mục tiêu giữ lại theo yêu cầu) | không file nào tham chiếu, nhưng là root doc | **GIỮ** (đổi tên về `repo reading.md` nếu muốn đúng convention) |
| `package/evaluation/FINAL_SUMMARY.md` | Summary cuối phase evaluation, link tới 6 md kia | không ai tham chiếu | **GỘP vào repo reading** hoặc XÓA (nội dung lịch sử phase) |
| `package/evaluation/ARCHITECTURE.md` | Sơ đồ package evaluation (có lỗi: ghi `run_all.py` thay `_run_all.py`) | FINAL_SUMMARY.md | **GỘP** |
| `package/evaluation/CAMPAIGN.md` | Doc campaign | FINAL_SUMMARY.md | **GỘP** |
| `package/evaluation/EXECUTION.md` | Hướng dẫn chạy (gồm `python -m ..._run_all`) | FINAL_SUMMARY.md | **GỘP** |
| `package/evaluation/METRICS.md` | Doc metrics | FINAL_SUMMARY.md | **GỘP** |
| `package/evaluation/MULTI_TURN.md` | Doc multi-turn (tính năng chưa implement) | FINAL_SUMMARY.md | **GỘP** (kèm note chưa implement) |
| `package/evaluation/REQUEST_KINDS.md` | Doc request kinds | FINAL_SUMMARY.md | **GỘP** |
| `package/evaluation/campaign/README.md` | README campaign | không ai | **XÓA/GỘP** — trùng CAMPAIGN.md |
| `package/evaluation/component/README.md` | README component (có nhắc dummy_memory_dataset) | không ai | **GỘP** |
| `package/evaluation/component/benchmarks/planner_README.md` | README planner benchmark | không ai | **GỘP/XÓA** |
| `benchmarks/README.md` | README thư mục benchmarks/ | không ai | cần xem nội dung — nhiều khả năng **XÓA/GỘP** |
| `scripts/README.md` | README scripts | không ai | **GỘP** (mục lục scripts có thể nhập repo reading) |
| `tests/README.md`, `tests/tools/README.md` | README tests | không ai | **GỘP/XÓA** |

Lưu ý: không file .py/.yaml nào tham chiếu các md trên (đã grep); chuỗi tham chiếu duy nhất là FINAL_SUMMARY.md → 6 file evaluation md. Nếu giữ repo reading làm doc duy nhất thì toàn bộ md evaluation là ứng viên gộp/xóa — **không xóa trong audit này**.

**Code/file .py cũ, trùng hoặc mất tham chiếu phát hiện thêm:**

- `scripts/evaluation/evaluate_product_reply.py` — **import hỏng**: `from package.evaluation.evaluate_product_reply import evaluate_product_reply` (dòng 18) nhưng module đó không tồn tại (file thật ở `product_reply/`). Chạy sẽ ModuleNotFoundError → script chết. (Bản đúng: `package.evaluation.evaluate_product_reply` re-export qua `__init__.py:5`.)
- `package/demo/backend/__pycache__/mock_backend.*.pyc`, `offline_backend.*.pyc` — source `.py` đã xóa, chỉ còn bytecode mồ côi.
- `package/evaluation/component/create_traceback_tool.py`, `link_component_to_e2e.py` — chỉ được gọi bởi `scripts/evaluation/link_e2e_cli.py`; logic attribution/correlation là placeholder (xem 5.5).
- `package/evaluation/multi_turn/_run.py` — stub SystemExit.
- `dummy_memory_dataset.jsonl` (3 dòng) — chỉ được nhắc trong component/README.md + repo reading; không code nào load (cần xác minh thêm nếu định xóa).
- `experiments/` hiện untracked trong git (toàn bộ output dir) — có chủ đích hay không cần xác nhận với owner.

#### 5.5 Kiểm kê mock/fake/stub toàn repo

**Trong `package/` + `scripts/` (ngoài tests/):**

| File/vị trí | Bản chất | Nơi dùng | Có chạy runtime thật? | Mức cần thiết | Đề xuất |
|---|---|---|---|---|---|
| `memory_oracle.py:11-14`, `build_memory_correctness_dataset.py:18-20`, `memory_correctness_setup.py:20-22` | hàm `memory_oracle()`/tên module trả "memory_oracle" — "Dummy public symbol to satisfy package layout test" | chỉ để layout test | Không | Thấp (test convention) | Giữ hoặc gỡ nếu layout test đổi |
| `reporting/_visualizations.py:24-132` | 5 hàm `generate_*_chart` chỉ `write_text` markdown placeholder ("# ... (Placeholder)") | `generate_all_charts` trong reporting | Có — được gọi khi generate report, **ghi file chart giả** | Thấp | Thay bằng chart thật hoặc đổi tên/gate rõ ràng; hiện tại report có "chart" không phải chart |
| `layer1_outcome/score_layer1_outcome.py:58-59` | `target_in_pool=None`, `target_reachable=None` placeholder ("requires reverse mapping") | layer1 scoring | Một phần — metric bị None | Trung | Implement hoặc loại metric khỏi report |
| `component/create_traceback_tool.py:44-56` | attribution "placeholder": heuristic theo error_type, confidence 0.5/0.0, "Insufficient data" | `link_e2e_cli.py` | Có (khi chạy CLI) | Thấp | Ghi rõ là heuristic/experimental |
| `component/link_component_to_e2e.py:56` | correlation = note text "requires matching request IDs" — không tính gì | `link_e2e_cli.py` | Có — ghi file "analysis" không có analysis | Thấp | Tương tự trên |
| `scripts/evaluation/opik_poc.py:56` | `value = 0.95  # Placeholder` trong metric wrapper | chính script | Script không gọi Opik API | Thấp (PoC) | Đã ghi "placeholder" trong code; rủi ro nếu ai đọc output như metric thật |
| `package/api/openai_compatible_provider.py:9-15` | docstring "BLOCKED: chưa có endpoint LLM thật" — **docstring lỗi thời**: code là HTTP client thật hoàn chỉnh (urlopen → /chat/completions) | `build_llm_provider` | Có — runtime thật | — | Cập nhật docstring (code không bị block) |
| `package/evaluation/product_reply/evaluate_product_reply.py:339` | "placeholder; real implementation would use language detection" | `scripts/evaluation/evaluate_product_reply.py` (**script này import hỏng**) + export `__init__` | Rule-based judge thật, chỉ language detection là giả | Trung | Sửa import script hoặc xóa script |
| `grounding_benchmark.py:39-52,62-69,91-108` | synthetic answer + rule-based fallback = fake scorer trong benchmark | component benchmark | Có — đã cho PASS giả | **Cao** | Xem đề xuất Task 4 |
| `multi_turn_evaluator.py:187-190` và default 1.0 ở 165,184,256,269,271,278 | metric placeholder/default | multi_turn (chưa có runner) | Chưa | Trung | Implement trước khi dùng |

**Trong `tests/` (chỉ phân loại, không mặc định xấu):**

- `tests/agents/fakes/fake_tools.py`, `test_fake_contracts.py` — fake tool cho unit test agent contracts. Hợp lệ.
- `tests/demo/fakes/offline_backend.py` (`OfflineDemoBackend`, dữ liệu `_MOCK_ITEMS`) — chỉ test demo UI/backend (`test_demo_backend.py`, `test_gradio_ui.py`). Hợp lệ — demo offline là mục đích.
- `tests/evaluation/component/benchmarks/fakes/controlled_filter_tool.py`, `controlled_similar_tool.py` + `test_controlled_tools.py` — controlled tools để test benchmark harness. Hợp lệ.
- `tests/evaluation/test_jev_reliability.py` — mock `httpx.Client` để test JevProvider không gọi API thật. Hợp lệ.
- Lưu ý: `package/demo/backend/` chỉ còn `live_backend.py` (backend thật: PlanExecutor/Type1Agent + data thật); `OfflineDemoBackend` không còn trong package — chỉ trong tests. Không có fake backend nào ship trong runtime package.

**Trả lời trực tiếp 5 câu:**

1. **Có fake LLM/API/tool nào chạy ngoài benchmark không?** Không — mọi fake nằm trong `tests/`; `package/api` chỉ có provider HTTP thật; demo runtime dùng `LiveBackend` thật. NGOẠI LỆ mang tính benchmark: grounding benchmark có rule-based fallback scorer và synthetic answer (vẫn nằm trong benchmark, nhưng tạo PASS giả — xem trên).
2. **Script nào báo thành công mà không làm gì?** `opik_poc.py` (in "Would create...", metric 0.95); `generate_example_report.py` (report từ dữ liệu hardcode — tên đã nói "example" nhưng không cảnh báo trong output); `link_e2e_cli.py`/`create_traceback_tool.py`/`link_component_to_e2e.py` (ghi "analysis" placeholder); `_visualizations.py` (ghi "chart" là markdown placeholder); `_run_all.py` (exit 0 khi component fail); `scripts/evaluation/evaluate_product_reply.py` (import hỏng — fail chứ không fake success); `multi_turn/_run.py` (SystemExit rõ ràng — trung thực).
3. **Có dữ liệu hardcode nào thay dữ liệu thật không?** `grounding_benchmark` tự sinh answer từ evidence (circular); `integration_benchmark` validate chính input fixture; `memory_*` benchmarks dùng synthetic fixture corpus (có chủ đích, oracle độc lập — chấp nhận được nhưng không phải dữ liệu Amazon thật); `generate_example_report.py` hardcode metrics; `opik_poc.py` hardcode exp_002.

---

## 3. Đề xuất việc cần làm (xếp theo rủi ro)

| # | Việc | Rủi ro | Tốn LLM? |
|---|---|---|---|
| 1 | **[CAO] Sửa grounding benchmark**: bỏ rule-based fallback cho điểm số (Jev fail → case fail/`evaluation_state` propagate), không tự sinh answer từ evidence (dùng output inference thật hoặc đánh dấu benchmark là judge-only), đọc `evaluation_state`/`why` để phân biệt judge-error vs unsupported | Kết quả grounding hiện tại không có nghĩa | Có (Jev) khi chạy thật |
| 2 | **[CAO] Sửa `evaluate_product_reply_with_jev.py:298`**: Jev batch exception → trả `evaluation_state="provider_error"` cho toàn bộ claim đó thay vì verdict "unsupported" giả; tương tự cho `unsupported_count` | hallucination_rate bị phình bởi lỗi hạ tầng | Có (Jev) |
| 3 | **[CAO] Fix campaign_runner comparison_pairs**: truyền `comparison_pairs` local vào `_run_comparisons` (tham số hoặc gán `self.config.comparison_pairs`) + truyền campaign_id vào overlay/config exp | Auto-compare trong campaign.yaml hiện vô hiệu hoàn toàn | Không (chỉ khi chạy campaign mới tốn) |
| 4 | **[TRUNG] run_all exit code + executor**: `sys.exit(1)` khi có component failed; quyết định implement executor evaluator hoặc bỏ khỏi run_all + xóa `executor_dataset.jsonl`/config mồ côi | CI/script dùng run_all sẽ xanh giả | Không |
| 5 | **[TRUNG] multi_turn**: hoặc implement `_run.py` + `agent_runner` thật + bỏ placeholder 1.0, hoặc đánh dấu module "not implemented" rõ trong docs và loại khỏi mọi report | metric 1.0 mặc định nếu ai đó chạy evaluator trực tiếp | Có (khi implement) |
| 6 | **[TRUNG] integration benchmark**: viết lại để chạy boundary thật (planner→executor→inference trên fixture) thay vì validate dict input; tách `contract_valid`/`no_mismatch` đang trùng nhau | "integration PASS" hiện không đo gì | Tùy implementation (có thể cần LLM) |
| 7 | **[TRUNG] Sửa/xóa `scripts/evaluation/evaluate_product_reply.py`** (import hỏng) | script chết | Không |
| 8 | **[THẤP] Hygiene .md**: gộp 11 md evaluation/scripts/tests vào repo reading hoặc xóa; sửa docstring `run_campaign.py:10`; xóa `.pyc` mồ côi `package/demo/backend/__pycache__/`; xem lại `dummy_memory_dataset.jsonl`, `untracked experiments/` | nhiễu repo | Không |
| 9 | **[THẤP] Provenance component benchmark**: ghi provider/model/base_url hash + judge config hash vào result JSON | khó tái lập grounding/planner runs | Không |
| 10 | **[THẤP] `success_rate` default 1.0** trong `_run_all.aggregate_results:138` → đổi thành 0.0/None khi thiếu key | edge case fake-pass | Không |
| 11 | **[THẤP] Docstring lỗi thời** `openai_compatible_provider.py:9-15` ("BLOCKED") | gây hiểu nhầm provider chưa chạy được | Không |
| 12 | **[INFO] Opik**: quyết định Replace/Complement/Keep Current thành văn bản; nếu Complement thì cần phase docs + `@opik.track` instrumentation (1-2 tuần theo repo reading); opik_poc.py cần chạy thật với Opik server hoặc ghi rõ "dry-run only" | — | Không (trừ khi eval Opik) |
| 13 | **[INFO] statistics**: campaign nên dùng `statistics/_bootstrap.py` (đã có sẵn) cho CI trên comparison deltas; `statistical_settings` trong campaign.yaml đang là config chết | so sánh campaign không có ý nghĩa thống kê | Không |

---

## 4. Không xác minh được

| Hạng mục | Lý do |
|---|---|
| Planner benchmark chạy thật | Thiếu `LLM_BASE_URL`/`LLM_API_KEY` — `PlannerBenchmark.__init__` raise ValueError (planner_benchmark.py:62); run_agent_eval cũng `SystemExit` khi `llm.health_check()` fail (run_agent_eval.py:312). Không phải lỗi code. |
| Grounding benchmark với Jev thật | Thiếu `TYPESAFE_API_KEY` — `JevProvider.__init__` raise (jev_provider.py:30-34). Lần chạy thật ở trên đi qua rule-based fallback → kết quả 0.9062 **không** phản ánh Jev. |
| Campaign chạy đầu-cuối (`run_campaign.py`) | Cần LLM cho phần lớn experiment (inference_mode "llm", planner agents) + dataset `resource/` đã có nhưng campaign 12 experiments × runs sẽ rất lâu; chưa chạy. Phần so sánh (bug comparison_pairs) đã xác minh bằng đọc code, không cần chạy. |
| `metrics.json` thật cho `_load_experiment_metrics` | `experiments/agent_eval/` không có exp run nào (chỉ `component_benchmarks/`); cấu trúc được suy từ `save_experiment` + `trajectory/summarize.py` — khớp nhưng chưa verify trên file thật. |
| `opik_poc.py` chạy | Cần `experiments/agent_eval/exp_002` (không tồn tại) + Opik server nếu muốn log thật. |
| Multi-turn end-to-end | `_run.py` chưa implement — không có gì để chạy. |
| Audit dataset bias / scoring bias chuyên sâu | Không tìm thấy artifact audit riêng; chỉ xác minh được leakage guard + split protocol + reproducibility provenance. Phần "bias" ghi **chưa xác minh**. |
| `experiments/` có nên tracked không | `git status` cho thấy toàn bộ `experiments/` untracked — có thể cố ý (output artifacts) hoặc thiếu `.gitignore`; cần xác nhận owner. |

*Báo cáo kết thúc — không sửa/xóa/commit file nào ngoài file báo cáo này.*
