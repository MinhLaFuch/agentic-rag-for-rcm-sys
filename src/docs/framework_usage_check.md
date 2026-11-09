# Kiểm tra: repo có dùng framework agent (LangChain, LangGraph...) không?

Ngày: 2026-11-09. Phạm vi: CHỈ ĐỌC — không sửa code, không cài package.
Worktree: `opik-assess` (nhánh `docs/opik-assessment`, tách từ `tools-building` @ `58628a4`).
Mọi kết luận có bằng chứng (lệnh + output, hoặc `file:dòng`); thiếu ghi "chưa xác minh".

## 1. Dependencies khai báo

Nguồn: `pyproject.toml` (root repo), `src/ecom_agentic_recsys.egg-info/requires.txt`.

**Không có** `requirements*.txt`, `setup.cfg`, `setup.py`, `poetry.lock`, `uv.lock`, `Pipfile`.
**Không có** `Dockerfile` (đã `fd -i "dockerfile"` toàn repo → 0 kết quả).

`pyproject.toml:6-22` — TOÀN BỘ dependencies:

| Nhóm | Package |
|---|---|
| runtime | pandas, numpy, PyYAML, scipy, pyarrow, **httpx**, pydantic |
| dev | pytest |
| demo | gradio |

Không có langchain*, langgraph, llama-index, openai, anthropic, litellm, instructor,
pydantic-ai, dspy, smolagents, crewai, autogen, haystack, semantic-kernel, hay **opik**
trong khai báo. (`egg-info/requires.txt` khớp, chỉ thiếu pydantic do build cũ — file
egg-info là artifact sinh ra, không phải nguồn khai báo.)

## 2. Import thực tế trong *.py

Grep `^\s*(import|from)\s+(langchain|langgraph|llama_index|openai|anthropic|litellm|
instructor|pydantic_ai|dspy|smolagents|crewai|autogen|haystack|semantic_kernel|opik|
google.*, cohere, mistralai, ollama, ...)` toàn repo → **đúng 3 match, tất cả trong
một file**:

```
src/scripts/evaluation/opik_poc.py:31  import opik
src/scripts/evaluation/opik_poc.py:32  from opik.evaluation.metrics import BaseMetric
src/scripts/evaluation/opik_poc.py:33  from opik.evaluation.metrics import score_result
```

→ Không một import framework agent/LLM SDK nào trong `package/`, `scripts/`, `tests/`,
`benchmarks/`. Các tên framework chỉ xuất hiện trong **docstring/comment**
(`package/api/llm_provider.py:5-8` nhắc "openai, anthropic, ollama..." như ví dụ
nguyên tắc abstraction — không phải import).

HTTP client thực tế dùng trong code (grep `import httpx|urllib|requests|aiohttp`):

| File:dòng | Import | Dùng để |
|---|---|---|
| `package/api/openai_compatible_provider.py:19-20` | `urllib.error`, `urllib.request` | POST `/chat/completions` — **stdlib, không SDK** |
| `package/api/jev_provider.py:27` | `httpx` (import trong `__init__`) | `httpx.Client` POST `/v1/systemone` (Jev judge) |
| `tests/agents/test_phase1_smoke.py:12` | `urllib.request` | test |

## 3. Môi trường thực tế

- **System Python** (`python --version` → 3.12.10, `pip list`): có `openai 2.54.0`,
  `litellm 1.105.7`, `opik 2.2.143`, `gradio 6.30.0`, `httpx 0.28.1`...
  → Cài trong môi trường **nhưng KHÔNG khai báo trong pyproject** (không tái lập được;
  code không import chúng — xem §2).
- **`.venv` project** (`src/.venv`, `pip list`): `ecom-agentic-recsys 0.0.1` (editable),
  gradio, httpx 0.27.2, pydantic, pandas... — **không có** openai/litellm/opik.
  Đối chiếu: khớp khai báo pyproject.

## 4. Cách gọi LLM thực tế

Mọi LLM call đi qua abstraction tự viết `LLMProvider` (`package/api/llm_provider.py:17`)
với **đúng 1 implementation**: `OpenAICompatibleProvider`
(`package/api/openai_compatible_provider.py:26`), dùng `urllib.request.urlopen` POST
tới `{base_url}/chat/completions` (`:62-73`) — OpenAI Chat Completions API thuần,
config ở `configs/agent/llm.yaml` (`provider: openai_compatible`, `model: gpt-5.4`,
`base_url`/`api_key` từ env `LLM_BASE_URL`/`LLM_API_KEY`). Factory:
`build_llm_provider` (`package/api/build_llm_provider.py:17-41`) — chỉ hỗ trợ
`openai_compatible`, provider khác raise `ValueError`.

Kênh thứ hai (judge, evaluation only): `JevProvider`
(`package/api/jev_provider.py:14`) — `httpx.Client` POST `{base_url}/v1/systemone`
(TypeSafe AI Jev), factory `build_judgment_provider`
(`package/api/build_judgment_provider.py:16-37`), config `configs/eval/judge.yaml`.

**Mọi điểm gọi LLM / LLM-client:**

| Điểm gọi | file:dòng | Client đứng sau |
|---|---|---|
| `PlanExecutor._complete` → `llm.complete` | `package/agents/planner/plan_executor.py:91-92` | LLMProvider → urllib POST chat/completions |
| `compose_llm` → `llm.complete` | `package/inference/compose/compose_llm.py:44` | như trên |
| `JevProvider.evaluate` → `client.post` | `package/api/jev_provider.py:61-65` | httpx POST /v1/systemone |
| `jev.evaluate` (judge product reply) | `package/evaluation/product_reply/evaluate_product_reply_with_jev.py:303,380` | JevProvider |
| `provider.complete` (smoke check) | `scripts/tools/check_llm_provider.py:12` | OpenAICompatibleProvider |
| Điểm khởi tạo provider | `package/demo/backend/live_backend.py:191`, `scripts/evaluation/run_agent_eval.py:314`, `scripts/llm_agent/smoke_real_llm.py:64`, `package/evaluation/component/benchmarks/planner_benchmark.py:53`, `grounding_benchmark.py:64-67`, `integration_benchmark.py:55-58`, `package/evaluation/multi_turn/_agent_runner.py:39` | — |

`Type1Agent` (`package/agents/type1/type1_agent.py`) **không dùng LLM** (docstring :2).
Không có tool nào trong `package/tools/` gọi LLM (grep `llm|LLMProvider|complete(` → 0).

## 5. Agent loop: tự viết hay framework?

**Tự viết hoàn toàn**, không framework:

- `PlanExecutor` (`package/agents/planner/plan_executor.py:29`): `plan()` (:105) = 1 LLM
  call lấy toàn bộ JSON plan; `_execute` (:229-281) duyệt steps, resolve refs, gọi
  `tool(agent="planner", **args)` trực tiếp; `run()` (:146-191) vòng reflect thủ công
  (`REFLECT_NOTICE` :21-26, quality gate `_compute_execution_quality`/`_is_quality_improvement`
  trong `_helper.py`). Retry parse JSON thủ công (`RETRY_NOTICE` :16-19, `plan_retries`).
- Tools: `package/tools/{base,ranking,retrieval,scoring,sql}/` + `agents/toolkit/`
  (`agent_tools.py`, `build_tools.py:15-33`) — class `Tool` tự định nghĩa, không
  LangChain `BaseTool`/function-calling.
- Session: `package/agents/session.py:22` — dataclass tự viết (turns/shown_items/
  candidates/constraints), inject vào system prompt ở `plan_executor.py:108-117`.
- Inference/compose: `package/inference/compose/compose_llm.py` + `compose_answer.py`
  + `grounding/` (parse + check_grounding tự viết).
- Không có ReAct loop, graph, hay state machine của framework nào — mọi vòng lặp
  (plan retry, reflect, llm_retries trong compose) là `for/while` viết tay.

## 6. Opik

- `opik` **không** có trong `pyproject.toml` dependencies (§1). Chỉ cài ngoài:
  system Python `opik 2.2.143`; `.venv` project **không có**.
- Import opik ngoài `scripts/evaluation/opik_poc.py` (:31-33): **không có**
  (grep toàn repo, kể cả `package/`, `tests/`, `benchmarks/`).

## 7. Kết luận

**Tự viết hoàn toàn — không dùng framework agent/LLM SDK nào.** Mức chắc chắn: **cao**
(0 import framework trong toàn bộ *.py; deps không khai báo; HTTP call bằng
urllib/httpx stdlib-level; mọi abstraction `LLMProvider`/`JudgmentProvider`/`Tool`/
`Session`/`PlanExecutor` đều class tự định nghĩa).

Hệ quả: Opik **không có callback/integration sẵn** để gắn — integrations của Opik
(LangChain, LlamaIndex, v.v. — xem `docs/opik_assessment.md` §1, nguồn docs.opik.com
truy cập 2026-11-09) không áp dụng được vì không có framework tương ứng. Phải dùng
`@opik.track` thủ công (hoặc `opik.track` decorator / context manager).

## 8. Điểm nên gắn Opik (chỉ liệt kê, không viết code)

| Ưu tiên | Hàm/điểm | file:dòng | Ghi chú |
|---|---|---|---|
| 1 | `PlanExecutor.run` (plan → execute → reflect, 1 turn) | `package/agents/planner/plan_executor.py:146` | span cha của cả turn |
| 1 | `PlanExecutor.plan` | `package/agents/planner/plan_executor.py:105` | LLM call sinh plan |
| 1 | `PlanExecutor._execute` (vòng step/tool) | `package/agents/planner/plan_executor.py:229` | có thể tách span per tool step trong `entry` loop :231-280 |
| 1 | `OpenAICompatibleProvider.complete` | `package/api/openai_compatible_provider.py:41` | **chặn mọi LLM call** qua 1 điểm — bắt cả compose_llm lẫn planner |
| 2 | `compose_llm` | `package/inference/compose/compose_llm.py:16` | answer-composition call |
| 2 | `compose_answer` | `package/inference/compose/compose_answer.py:13` | dispatch llm/template |
| 3 | `JevProvider.evaluate` | `package/api/jev_provider.py:41` | judge calls (evaluation) |
| 3 | `Type1Agent.recommend` | `package/agents/type1/type1_agent.py:24` | agent không-LLM, trace tool chain |
| 3 | `RealAgentRunner.run_turn` | `package/evaluation/multi_turn/_agent_runner.py:49` | multi-turn eval entry |

Khuyến nghị kiến trúc chi tiết + thứ tự tích hợp đã có trong
`docs/opik_assessment.md` §5 ("Kiến trúc đề xuất", "Thứ tự tích hợp") — file này
chỉ xác nhận tiền đề "tự viết → cần @opik.track thủ công".
