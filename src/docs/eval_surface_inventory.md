# Eval surface inventory — tuần 47

Câu hỏi gốc: "toàn bộ phương thức eval có nằm hết trong campaign không?"
Câu trả lời ngắn: **không**. Campaign bao phủ đủ 5 layer eval của agent-loop +
multi-turn, nhưng toàn bộ eval "ngoài agent-loop" (component benchmark cách ly,
Jev judge, recommender/retrieval offline, ablation statistics) chạy bằng entry
point riêng. Báo cáo này kiểm kê đầy đủ, kèm bằng chứng file#dòng.

Mọi số liệu dưới đây đọc từ code/config/artifact thật; không suy đoán.

---

## 1. Những gì campaign_001 THỰC SỰ chạy

`run_agent_eval.py` chấm **đủ 5 layer** cho mỗi trajectory qua
`score_trajectory` (`package/evaluation/trajectory/score_trajectory.py:47-51`):

| Layer | Module | Nội dung chính |
|---|---|---|
| L1 outcome | `layer1_outcome/` | recall@10, precision@10, mrr, ndcg, target_in_pool, retrieval funnel (`retrieved_by_sql/semantic/itemcf`), `stage_lost` |
| L2 interaction | `layer2_interaction/` | task_success v2 theo kind (ambiguous/exclusion/personalized/similar/unanswerable), exclusion_compliance, constraint_satisfaction |
| L3 grounding | `layer3_grounding/` | answer_status (ok/ask_user/no_result/tool_error), answer_grounded, answer_fallback |
| L4 process | `layer4_process/` | plan_valid, steps_ok_rate, tool_selection_ok, args_valid_rate, invented_ids, reflections, memory_profile_usage, semanticsearch_keyword_quality |
| L5 deployment | `layer5_deployment/` | tokens, latency (mean/p50/p95/p99), cost, provider_error, sql_time_budget_hits |

Bằng chứng artifact: `experiments/agent_eval/campaigns/campaign_001/exp_9_*/run_1/scored.jsonl`
có **87 cột** mỗi dòng (đếm bằng script); `metrics.json` tổng hợp theo kind.

Multi-turn **có** trong campaign: `agent_eval.multi_turn` → subprocess riêng qua
`run_multi_turn_for_eval` (`_eval_step.py:122-145`), artifact tại
`campaigns/campaign_001/multi_turn/<exp>_run<N>/multi_turn.json`, metrics trích
vào `campaign_result.json.multi_turn` (`campaign_runner.py:545-570`).

## 2. Những gì KHÔNG nằm trong campaign

| Eval | Entry point | Cần credential | Ghi chú |
|---|---|---|---|
| Component benchmarks (5) | `scripts/evaluation/run_component_benchmarks.py` → `package/evaluation/component/_run_all.py` | tuỳ component (bảng §3) | Dataset synthetic 18-item; Phase 2 vừa thêm case vào đây |
| Jev / product-reply judge | `scripts/evaluation/evaluate_with_jev.py`, `jev_smoke_test.py`, `jev_negative_control.py` | **Jev** | Chỉ grounding benchmark dùng Jev |
| Ablation statistics | `scripts/experiments/compare_experiments.py`, `package/evaluation/ablation/` | theo experiment được so | Campaign chỉ auto-compare 11 cặp vs exp_1 (confounded) |
| Recommender/retrieval offline | `package/evaluation/recommender/`, `ranking_eval.py`, `candidate_recall.py`, `tune_item_knn_hybrid.py`, `retrieval_loss_diagnostic.py`, `sparse_*` | không (offline) | Đánh giá tầng retrieval/recommender trực tiếp — **scope của effort khác** |
| Diagnostics | `package/evaluation/diagnostics/` (error_taxonomy, failure_rates, reflection_diagnostics) | không | Phân tích artifact, không phải benchmark |
| Reporting/viz, Opik | `package/evaluation/reporting/`, `scripts/evaluation/opik_poc.py` | tuỳ | Công cụ trình bày |

## 3. Component benchmarks — ai cần gì

Driver: `configs/eval/component_benchmarks.yaml` (`datasets` map 5 component,
`runs: 1`, `configs.grounding.use_jev: true`, memory có thresholds gate).
`_run_all.py:35-78` chạy từng component bằng subprocess
`python -m package.evaluation.component.run --component X --dataset Y`, sau đó
chạy thêm bước multi_turn (`_run_all.py:81-112`, skip `skipped_no_credentials`
nếu thiếu LLM) và viết `unified_report_<ts>.json/.md`.

| Component | Dataset (sau Phase 2) | LLM | Jev | Ghi chú |
|---|---|---|---|---|
| memory | memory_correctness_dataset.jsonl (29) | Không | Không | Oracle-based, deterministic; thresholds: all_fields_match≥0.95, success=1.0, leakage=0 |
| executor | executor_dataset.jsonl (**22**) | **Không** (`llm=None`, `_execute` only — `executor_benchmark.py:49-54`) | Không | exec_019-023 verify được ngay, không credential |
| integration | integration_dataset.jsonl (**13**) | Không ở `mode=template` (default); `mode=llm` cần provider | Không | int_013 verify được ngay |
| planner | planner_dataset.jsonl (**29**) | **Có** — `PlannerBenchmark.__init__` raise nếu thiếu `base_url` (`planner_benchmark.py:44-52`) | Không | planner_033-035 chỉ chấm khi có LLM |
| grounding | grounding_dataset.jsonl (35) | Không bắt buộc (`mode=template` default; `mode=llm` cần provider) | **Có** — `use_jev: true`; `run_component` raise nếu thiếu evidence/Jev (`grounding_benchmark.py:41-46`) | Phase 2 không thêm case vì không verify được |
| multi_turn (bước phụ) | conversations.jsonl (**13**) | **Có** — `RealAgentRunner` raise nếu thiếu LLM (`_agent_runner.py:33-38`) | Không | Skip `skipped_no_credentials` khi thiếu LLM |

### Backlog không bị chấm

`planner_dataset_backlog.jsonl` (6 case) **không nằm trong `datasets` map** →
không loader nào đọc nó trong `_run_all`. Không có cơ chế "skip backlog" — đơn
 giản là file riêng không được trỏ tới. Backlog chỉ là tài liệu cho case công cụ
chưa biểu đạt được (vd `categories_none` không có trong `FILTER_KEYS`,
`tools/_schema.py:8-20`).

### Regression CLI (riêng)

`component/run_regression_cli.py` + `_regression.py`: so 2 `BenchmarkSummary`
(baseline vs current), metric_threshold 5%, latency_threshold 10% →
`RegressionReport`. Đây là so **benchmark-qua-thời-gian**, không phải so với
campaign.

## 4. Hệ quả cho campaign đang chạy / các phase tới

- Exp 7/8/11/12 sắp rerun: **chỉ cần LLM** (`LLM_BASE_URL`/`LLM_API_KEY`), không
  cần Jev — Jev không xuất hiện trong `run_agent_eval.py`, `campaign_runner.py`,
  hay `multi_turn/` (grep `jev|Jev` = 0 kết quả trên 3 path đó).
- Component benchmark cases mới (Phase 2): executor/integration/memory chạy
  deterministic ngay; planner + multi_turn cần LLM; grounding cần Jev.
- Phase 5 ablation dùng `compare_experiments.py`/`ablation/` — nằm ngoài
  campaign, cần campaign_result/scored.jsonl đã hoàn chỉnh.
- Eval offline recommender/retrieval (Recall@K toàn dataset, candidate recall,
  tuning) là **scope effort khác** — không nằm trong báo cáo agent-layer này.

## 5. Câu hỏi mở

1. `unified_report` của component benchmarks và `campaign_result.json` là 2 hệ
   metric song song — có cần một chỗ tổng hợp duy nhất không, hay giữ tách
   (component = fixture nhỏ deterministic, campaign = data thật + LLM)?
2. Grounding benchmark đang `use_jev: true` — nếu không có Jev credential trong
   CI/môi trường thường, có nên cho phép `use_jev: false` → status
   `skipped_no_credentials` thay vì raise, giống multi_turn? (Hiện raise →
   cả `_run_all` ghi error cho component đó.)
