# REPORT — Khảo sát 7 repo single-agent recommender (read-only)

Ngày: 2026-11-25. Nguồn: `cloned_repos/` (xem `MANIFEST.md`). Mọi kết luận kèm `file:dòng` tương đối trong repo đã clone. Không chạy code, không suy đoán từ paper.

## 1. Tóm tắt (10 dòng)

1. Cả 7 URL đều đúng repo của paper tương ứng; không repo nào rỗng/stub.
2. Chỉ InteRecAgent (RecAI) hiện thực đúng kiến trúc "LLM planner + hard filter (SQL) + soft filter (similarity) + ranking model + candidate buffer + reflection" mà project đang hướng tới — và nó là repo hoàn chỉnh nhất để đối chiếu.
3. iAgent, MemRec, ItemRAG đều là **LLM re-ranker trên candidate set nhỏ có sẵn** (10 item hoặc ranked list từ dataset), không có retrieval tự do — giao thức eval của họ (1 target + N random negatives) **giống hệt** setup full-catalog-1-target của project về bản chất, nhưng candidate pool nhỏ hơn nhiều.
4. BiLLP/T-PRA là agent sequential-rec qua môi trường reward (ReAct loop `recommend[item]`), không phải single-shot retrieval; điểm đáng mượn là **grounding model map item bịa → item gần nhất bằng embedding** và penalty "quá giống history".
5. VibeMus không phải recommender — là demo tool-use cho music generation; gần như không có gì mượn được ngoài pattern tool-schema.
6. Không repo nào có cơ chế "query distill → structured spec" rõ ràng như `package/agents/distill.py` của project; MemRec có bước "Stage-R facet extraction" gần nhất về tinh thần.
7. Cơ chế chống hallucinated key/value trong InteRecAgent là **grounding layer**: fuzzy-match cột SQL, giá trị categorical, và title→id bằng SentenceTransformer (gte-base) — có thể chống được lỗi `categories_exclude` và `filters:{}` ở mức tool, nhưng **không** chống được filter rỗng (họ không có khái niệm structured filter).
8. Về lỗi "item thiếu category bị loại im lặng": InteRecAgent mắc **đúng cùng vấn đề** (SQL trên pandas, NULL không match) nhưng có Critic LLM đọc tool-track và bắt trường hợp "0 eligible items" để gợi ý nới điều kiện — tức họ phát hiện hậu kỳ thay vì ngăn từ đầu.
9. Eval literature (hit/NDCG/MRR trên 10–50 candidates, hoặc simulator multi-turn với target ẩn) khác xa giao thức full-catalog của project; không repo nào eval trên toàn catalog.
10. Đề xuất chính: mượn ý tưởng **fuzzy-grounding trước khi execute** (đã có sẵn trong `distill.py`/`compile_filters` một phần) và **critic/rechain hậu kỳ** từ InteRecAgent; bỏ qua phần nặng (UniRec checkpoint, memory graph của MemRec, DPO loop của T-PRA).

## 2. Bảng so sánh (câu 2–6 của Phase B)

| Repo | Query → cấu trúc | Retrieval | Ranking/fusion | Xử lý lỗi | Đánh giá |
|------|------------------|-----------|----------------|-----------|----------|
| iAgent | Instruction tự do → 2 call LLM: (a) sinh `knowledge` string (json_schema strict), (b) re-rank list id (json_schema `rerank_list: int[]`) — `model.py:96-174` | Không có — dùng `ranked_lists` precomputed trong dataset pkl (`main_iagent_mp.py:117`) | LLM tự sắp xếp lại thứ tự candidate; `pure_ranked_list` đưa vào prompt làm tham chiếu (`model.py:139`) | Parse fail → retry 3 lần; MRR=-1 → retry tới 3 lần với hint "list out of order" (`model.py:202-265`) | HIT@1/3/5, NDCG@3/5, MRR; held-out last item; candidate = ranked list dataset; script inline trong `main_iagent_mp.py:109-170` |
| MemRec | Instruction string nhúng verbatim vào reranker prompt ("User Profile"/"User's Current Request") — `reranker_llm.py:53-54,101-102`; Stage-R tách facets (JSON schema) từ **memory**, không phải từ query — `manager.py:25-128` | Graph láng giềng user-item (`graph.py`) + candidate list ngoài truyền vào | `LLMReranker`/`VectorReranker` chấm điểm từng candidate theo facets; sort desc — `memrec_agent.py:209-243` | Parse JSON fail → trả facets rỗng (`manager.py:~180`); reranker fallback | 1 target + (n−1) random negatives (`trainer_memrec.py:306-318,539-552`); Hit/NDCG/MRR @ [1,3,5,10] (`metrics.py`); `scripts/run_train.py` |
| ItemRAG | Không có query — pipeline offline per-item/per-user | Bước 2: co-purchase neighbors + neighbors của K=5 semantic-similar items (gte-large-en-v1.5 trên title), đếm tần suất, sample K=50 — `step2_do_retrieval.py:39-97` | 1 LLM call (gpt-4.1-mini) rank 10 candidates (1 target + 9 random) kèm title + co-purchase summary — `evaluation.py:93-119` | Parse fail → `continue` bỏ sample (`evaluation.py:174-177`) | HR/NDCG @1/3/5 trên 1000 users — `evaluation.py:163-197` |
| BiLLP | History + target → ReAct `Thought/Action/Finish`; action duy nhất `recommend[item]` — `Agents/agent_base.py:151-202` | Grounding model: LLaMA embedding nearest-neighbor trên toàn catalog (`env/steam.py:112-160` `get_topk_near_item`); FAISS cho reflection/Q-table memory (`agent_a2c.py:289-317`) | Sequential: reward từ `reward_mat`/`distance_mat`; không rank candidate set | Item bịa → map sang item gần nhất + Observation báo "can not be recommened, instead recommend[X]" (`agent_base.py:172-184`); action sai → "Invalid Action" (`agent_base.py:202`) | Reward tích lũy theo episode; `whether_to_leave` phạt −1000 khi item quá giống history (`env/steam.py:75-88`); tasks evaluate EM/F1 (khung QA) |
| T-PRA | Như BiLLP nhưng prompt proactive-rec: dẫn user tới target item — `Agents/agent_a2c.py:21-34` | Grounding giống BiLLP nhưng dùng LLaMA-3.1-8B làm cả agent lẫn embedder (`env/env.py:148-204`) | Reward = preference + step-length + forward-length (`env/steam.py:37+`); critic chấm −5..5 | Như BiLLP; thêm DPO training trên trajectory | `tpra_start.sh`: generation → combine → mlp.py → llamafactory DPO lặp 3 vòng → eval `--task_split test` |
| VibeMus | Yêu cầu tự do → qwen-agent function calling; tool `param_setter{name,value}` set tags/lyrics/title — `tools.py` (SetParam), `assistant.py` system prompt | Không có | Không có | Tool trả message "not generated yet"; json5 parse input | `experiments/evaluation.py`, `dialog_eval.py` — eval chất lượng audio/lyrics, không phải recsys |
| InteRecAgent | Request → plan-first: LLM xuất JSON plan `[{tool_name, input}]` cho ToolBox (`agent_plan_first_openai.py:75-88`); hard condition = SQL string, soft = list seed titles, ranking = JSON `{schema, prefer, unwanted}` | SQLSearchTool (pandasql trên item table, scope = candidate buffer), SimilarItemTool (item-item sim `.npy`, ngưỡng = top rec_num), QueryTool (SQL → records) | RecModelTool: schema popularity/similarity/preference; `unwanted` bị mask điểm −100000/1e-15 (`reco_model_tool.py:131-180`); buffer chỉ giữ ID + mảng similarity song song | ToolBox check tên tool tồn tại, plan parse fail → trả lỗi cho LLM (`agent_plan_first_openai.py:74-104`); fuzzy-grounding cột/giá trị/title; buffer rỗng → tool trả "stop execution"; Critic + rechain ≤3 (`agent.py:168-184`, `critic/base.py`) | Hit@title-match (rapidfuzz>80), AT, OAI cost, fail count — `eval/user_simulator.py:387-460`; one-turn `eval/one_turn_eval.py:205-229`; ranking eval có NDCG — `one_turn_eval_ranking.py:264-316` |

## 3. Ghi chú từng repo

### 3.1 iAgent / i²Agent — `cloned_repos/iAgent/`

- Paper ACL 2025 Findings "iAgent: LLM Agent as a Shield between User and Recommender Systems". Code: `main_iagent_mp.py` (harness) + `model.py` (2 agent class, ~700 dòng).
- Pipeline thực tế (`model.py:46-55, 83-271`): workflow 2 bước — LLM sinh "knowledge" mô tả loại item phù hợp instruction (bước 1), rồi re-rank candidate list (bước 2). i²Agent (`model.py:288+`) thêm: sinh profile từ 1 item dương + 1 negative sample, rồi tách `dynamic_interest`/`dynamic_profile` trước khi re-rank.
- **Query → cấu trúc**: không có structured slot; mọi trung gian là string tự do, chỉ output cuối ép schema (`rerank_list: array<int>`, `explanation: array<string>`) qua OpenAI `response_format json_schema strict` (`model.py:148-174`).
- **Retrieval**: không tồn tại — `ranked_lists` lấy từ cột của dataset pkl (`main_iagent_mp.py:101,117`); repo không chứa code sinh candidate.
- **Ranking/fusion**: LLM là ranker duy nhất; điểm số không được dùng — chỉ thứ tự id.
- **Lỗi**: hallucinated id không bị chặn (metric `list.index(answer)` trả −1 → retry prompt).
- **Eval**: HIT/NDCG/MRR trên InstructRec (4 domain); `main_iagent_mp.py:109` metrics. **Lưu ý bug trong code**: vòng `for i in range(len(instruction))` có `if i > 1: break` ở `main_iagent_mp.py:149-150` → mỗi chunk 1000 chỉ submit ~3 sample đầu; không rõ có chủ đích (debug) hay bug — "chưa xác minh".
- **Chạy được**: cần `OPENAI_API_KEY` + dataset InstructRec qua gdown; không GPU, không checkpoint.
- **Mượn được**: pattern 2-call "distill knowledge → re-rank với structured output" (`model.py:88-174`) — tương tự tinh thần `distill.py` nhưng output của họ là free-text knowledge chứ không phải Spec có validate; và retry-loop khi output vi phạm thứ tự candidate (`model.py:202-265`).

### 3.2 MemRec — `cloned_repos/memrec/`

- Paper ACL 2026 "MemRec: Collaborative Memory-Augmented Agentic Recommender System". Kiến trúc 3 stage: memory graph → Stage-R (facet extraction) → Stage-ReRank → Stage-W (write-back). `src/models/memrec_agent.py:22-32`.
- Pipeline: `rerank()` (`memrec_agent.py:138-264`): pruner chọn top-k láng giềng (`mix_min_users/items`) → packer nén context theo token budget → `manager.run_stage_r` → `reranker.rerank` chấm điểm candidates → sort desc.
- **Query → cấu trúc**: instruction chỉ là string nhúng vào prompt reranker (`reranker_llm.py:53-54` "User Profile", `:101-102` "User's Current Request"); Stage-R output facets theo JSON schema (`manager.py:81-128`) nhưng đó là distill **memory**, không phải distill query.
- **Retrieval**: không retrieve từ catalog — candidates do caller truyền (eval: 10 item). "Retrieval" của họ là chọn láng giềng trong user-item graph.
- **Ranking/fusion**: `LLMReranker` (LLM chấm từng candidate, `reranker_llm.py`) hoặc `VectorReranker` (`reranker_vector.py`); điểm → sort desc (`memrec_agent.py:241-243`).
- **Lỗi**: JSON parse fail → facets rỗng, pipeline vẫn chạy (`manager.py` ~dòng 180); không có cơ chế chống item bịa vì candidates là id nội bộ.
- **Eval**: `trainer_memrec.py:306-318,539-552` — 1 target + n−1 negatives (mặc định 10 candidates); metrics Hit/NDCG/MRR `src/train/metrics.py`; warmup rounds mô phỏng memory trước test (`configs/*.yaml`).
- **Chạy được**: cần LLM API (Azure/vLLM), PyTorch; dataset `.inter` ngoài; có sẵn eval-user sample JSON 1k trong `data/eval_user_samples/`.
- **Mượn được**: ý tưởng "distill → facets có confidence + supporting_neighbors" (`manager.py:67-94`) — facets có provenance, hữu ích nếu project mở rộng distill; và tách "retrieve context" khỏi "score candidates". Nặng nếu mượn cả memory graph.

### 3.3 ItemRAG — `cloned_repos/ItemRAG/`

- Paper SIGIR 2026 short "ItemRAG: Item-based RAG for LLM-based Recommendation". 4 bước offline hoàn toàn (`README.md` "Running code").
- Pipeline: step1 embed title toàn catalog bằng `gte-large-en-v1.5` → top-K=5 item tương tự mỗi item (`step1_get_similar_title_items.py:20-63`); step2 với mỗi user: co-purchase pairs + mở rộng qua semantic neighbors, đếm frequency, sample K=50 (`step2_do_retrieval.py:28-97`); step3 GPT-4.1-nano tóm tắt "co-purchased items" thành text per item (`step3_generate_summary.py:8-22,54-77`); step4 LLM rank (`evaluation.py`).
- **Query → cấu trúc**: không có — không có user query; "query" là user history.
- **Retrieval**: hybrid CF + semantic, nhưng **precompute offline per user**, không phải retrieval theo request.
- **Ranking/fusion**: frequency count = điểm implicit; LLM chỉ rank 10 ứng viên cuối.
- **Lỗi**: tối thiểu; parse fail → skip.
- **Eval**: 1000 users, 1 target + 9 random negatives, HR/NDCG@1/3/5 (`evaluation.py:101-119,163-197`).
- **Chạy được**: GPU cho step1 (hoặc CPU chậm), OpenAI key step3/4, dataset pickle Dropbox.
- **Mượn được**: ý tưởng "item-side enrichment text" — tóm tắt co-purchase neighborhood thành đoạn mô tả item để đưa vào context (`step3_generate_summary.py:10-22`); giống hướng enrich metadata cho LookupTool. Candidate pool nhỏ (10) nên kết quả không nói gì về full-catalog.

### 3.4 BiLLP — `cloned_repos/BiLLP/`

- Fork FireAct; task rec = môi trường `env/steam|amazon|movie` với `reward_mat` (user×item), `distance_mat` (item×item), `datamaps.json`. 4 agent: `agent_reflexion`, `agent_retrival` (Q-table + FAISS), `agent_revise`, `agent_a2c` (actor-critic, method chính theo `run_steam.sh`).
- Pipeline (`Agents/agent_base.py:100-202`): mỗi step LLM xuất `Action N: recommend[item]` → grounding model map sang item thật → env trả reward + Observation → lặp tới Max_Iteration=50.
- **Query → cấu trúc**: user history + target item → ReAct thought; action schema `recommend[item]` parse bằng regex (`agent_base.py:268`).
- **Retrieval**: grounding = nearest neighbor theo LLaMA embedding trên toàn catalog (`env/steam.py:112-160`); FAISS trên OpenAI embeddings cho reflection/Q-table (`agent_a2c.py:289-317`).
- **Ranking/fusion**: không rank — sequential rec, reward matrix quyết định; "fusion" là distance penalty khi item quá giống k item gần nhất (`env/steam.py:75-88`, `whether_to_leave`).
- **Lỗi**: item bịa → **đây là điểm mạnh**: map sang nearest real item + observation minh bạch (`agent_base.py:172-184`); action sai format → "Invalid Action" feedback (`agent_base.py:202`); episode kết thúc sớm nếu vi phạm diversity.
- **Eval**: reward tích lũy; tasks gốc QA dùng EM/F1 (`tasks/steam.py:21-44`).
- **Chạy được**: OpenAI API key (hoặc local LLaMA qua `models/llama.py`), SERPAPI cho task QA (không cần cho rec), LLaMA grounding weights + `steam_embedding_task.pt`, data npy ngoài.
- **Mượn được**: **grounding-by-embedding cho item bịa** — tương đương fuzzy_match của InteRecAgent nhưng dùng embedding item thay vì title-string; và cơ chế "nearest neighbor thay thế + thông báo cho LLM" thay vì reject cứng.

### 3.5 T-PRA — `cloned_repos/T-PRA/`

- Paper ACL 2025 "Tunable LLM-based Proactive Recommendation Agent". Cùng skeleton FireAct nhưng agent + grounding đều là LLaMA-3.1-8B local (`models/llama.py`, `env/env.py:148-204`); vòng lặp DPO: generate trajectories → `combine.py` → `mlp.py` sinh preference pairs → `llamafactory-cli train --stage dpo` → lặp 3 lần (`tpra_start.sh`).
- Pipeline: proactive rec — LLM đề xuất dãy `recommend[item]` dẫn user tới target; reward = preference score + step-length reward + forward-length reward (`Agents/agent_a2c.py:21-34` mô tả trong prompt).
- **Query → cấu trúc**: history + target → thought/action; critic LLM chấm −5..5.
- **Retrieval**: `Grounding_Model_LLAMA.get_top_near_item` — embed "The type of {item} is" bằng LLaMA, `torch.cdist` tới `task_embedding` precomputed, lấy nearest không thuộc history (`env/env.py:175-204`).
- **Ranking/fusion**: reward shaping nhiều thành phần; critic value.
- **Lỗi**: như BiLLP (cùng `agent_base.py` lineage); riêng T-PRA dùng MLP (`mlp.py`) trong vòng DPO data construction.
- **Eval**: `tpra_start.sh` phần Evaluation: `generation_rec_agents.py --task_split test` với các checkpoint DPO vòng 0/1/2/3.
- **Chạy được**: GPU + LLaMA weights + LLaMA-Factory clone + dataset zip ngoài — nặng nhất trong 7 repo.
- **Mượn được**: vòng đời "agent → trajectory → DPO → agent tốt hơn" nếu project muốn fine-tune planner sau này; reward shaping nhiều tín hiệu (step-length/forward-length) cho bài toán proactive. Không mượn được gì cho inference path hiện tại.

### 3.6 VibeMus — `cloned_repos/VibeMus/`

- Không phải recommender: demo "vibe music" — LLM (qwen-plus qua DashScope, `agent_llm_config.json`) trò chuyện → tool `param_setter` ghi tags/lyrics/title → ACE-Step pipeline sinh/chỉnh nhạc (`assistant.py`, `tools.py`, `pipeline.py`).
- **Query → cấu trúc**: qwen-agent function calling; `param_setter{name: "tags"|"lyrics"|"title", value}` (`tools.py` SetParam).
- **Retrieval/ranking**: không có.
- **Lỗi**: tool tự guard ("song is not generated yet" → `edit_song` return message, `tools.py` SongEdit.call); input parse bằng `json5.loads`.
- **Eval**: `experiments/` có `evaluation.py`, `dialog_eval.py`, `score_processing.py` — eval audio/lyrics quality, không liên quan recsys metrics.
- **Chạy được**: GPU + ACE-Step 3.5B (HF `ACE-Step/ACE-Step-v1-3.5B`, `checkpoint.py`) + DashScope key; `acestep` cài từ git URL trong `requirements.txt`.
- **Mượn được**: gần như không cho bài toán rec; chỉ pattern "LLM ghi state qua tool có schema hẹp" tương tự param_setter.

### 3.7 InteRecAgent (RecAI) — `cloned_repos/RecAI/InteRecAgent/`

Xem mục 4 (Phase C) để có phân tích đầy đủ.

## 4. Phase C — Đào sâu InteRecAgent

Thư mục con: **`cloned_repos/RecAI/InteRecAgent/`** (monorepo RecAI còn có Knowledge_Plugin, RecLM-emb/gen/uni/eval, RecExplainer — không liên quan trực tiếp; RecLM-gen/uni là nguồn checkpoint cho RankingTool).

Code chính: `llm4crs/` (~6k dòng). Hai agent implementation: `agent.py` (ReAct từng tool một, langchain `LLMSingleActionAgent`, `max_iterations=5` — `agent.py:77`) và `agent_plan_first_openai.py` (plan-first native OpenAI, **đây là bản eval dùng**: `eval/eval_single_turn.sh` chạy `--plan_first=1 --langchain=0`).

### C.1 Hard vs soft condition

- Phân biệt trong prompt: `prompt/system.py:27-29` (và bản plan-first `:119-121`): "Hard conditions … involve {item} properties like tags, price, release date. Soft conditions … involve similarity to specific seed {item}s. Separate hard and soft conditions."
- **HardFilterTool** (`retrieval/sql_tool.py` + desc `prompt/tool.py:38-47`): input = **một dòng SQL SELECT** do LLM viết; rules trong desc: cấm title làm điều kiện, LIKE cho cột string, 1 bảng, không LIMIT, ưu tiên OR, "use given related values for categorical columns".
- **SoftFilterTool** (`retrieval/itemcf_tool.py`): input = **Python list of seed item titles** (`literal_eval`, `itemcf_tool.py:29`); chấm similarity = mean của `item_sim[seed_ids][:, candidates]` (`:60`), giữ item có score > ngưỡng = score của top-`rec_num` item toàn catalog (`:62-66`).
- **Chống tool args sai/bịa**: `rewrite_sql` (`sql_tool.py:78-106`, giống hệt trong `query/query_tool.py:112-140`) — (a) ép `FROM <bất kỳ> WHERE` về đúng tên bảng; (b) extract cột trong WHERE, cột không tồn tại → `fuzzy_match` sang cột gần nhất (SentBERTEngine, `corups/base.py:80-85`); (c) mọi `col LIKE '%value%'` với cột categorical → thay value bằng giá trị gần nhất trong `categorical_col_values` (`sql_tool.py:94-105`). Title/seed items cũng qua `fuzzy_match(...,'title')` (`itemcf_tool.py:50`, `buffer/base.py:55`, `reco_model_tool.py:76-93`). Lưu ý: grounding **replace** chứ không reject — gõ sai tên cột sẽ lặng lẽ thành cột gần nghĩa.

### C.2 Candidate Bus

- `buffer/base.py:12-170` `CandidateBuffer`: `memory` = list **chỉ chứa item IDs** (`range(1, len(corpus))` lúc init — `:17`); `similarity` = mảng điểm **song song** chỉ do SimilarItemTool ghi (`save_similarity`, `:25-29`) và RecModelTool đọc khi `schema=="similarity"` (`reco_model_tool.py:107-110`). Không lưu score theo từng bước filter — buffer là "tap" thu hẹp dần, mỗi tool `push` ghi đè `memory` (`update`, `:86-107`).
- Ai ghi/đọc: mọi tool đọc `buffer.get()` và `push` kết quả; `track()` log (tool,input,output) cho Critic (`:32-38`).
- Bus rỗng: `SQLSearchTool.run` return sớm "There are 0 candidates … Stop execution" (`sql_tool.py:33-34`); `SimilarItemTool` tương tự (`itemcf_tool.py:43-46`); `RecModelTool` log stop nhưng vẫn chạy (`reco_model_tool.py:69-72`); `MapTool` trả "There is no suitable items." (`map_tool.py:45-48`).
- Ngoài ra `replan()` (`buffer/base.py:132-146`) clear buffer + lưu failed plan — cơ chế có sẵn nhưng **không thấy caller** trong code đã đọc (chưa xác minh có được dùng).

### C.3 Planning (plan-first) và Reflection/Rechain

- Plan-first: `SYSTEM_PROMPT_PLAN_FIRST` (`prompt/system.py:104-179`) — LLM xuất `Action: ToolExecutor` + `Action Input: [{"tool_name","input"}…]`; `ToolBox.run` parse JSON (fallback `literal_eval`), check tool name tồn tại (substring match, `agent_plan_first_openai.py:98-104`), tự **chèn MapTool nếu plan thiếu** (`_check_plan_legacy`, `:42-61,106-108`), rồi chạy tuần tự; chỉ LookUp/Map output được đưa lại cho LLM (`:133-134`).
- Tool order khuyến nghị trong prompt: BufferStore → LookUp → HardFilter → SoftFilter → Ranking → Map (`system.py:54-55`); plan-first thêm "Remember to use HardFilterTool before SoftFilterTool" (`system.py:133`).
- Reflection: `Critic` (`critic/base.py`) — LLM judge riêng đọc conversation + **tool using track** (`buffer.track_info`) + answer, trả "Yes" hoặc "No. … advice" (`prompt/critic.py:52-85` — 5 tiêu chí: input tool có đúng không, thiếu/thừa tool, đủ item không, input có khớp intent không, gợi ý nới SQL khi 0 kết quả). `parse_output` regex `No\. (.*)` (`critic/base.py:14-29`).
- Rechain: `agent.py:168-184` / `agent_plan_first_openai.py:449-471` — nếu `rechain=True` và `_reflection_cnt < reflection_limits` (default 3) → đệ quy `run()` lại với `reflection` text chèn vào slot `{{reflection}}` của prompt; reset counter sau khi thành công; vượt giới hạn → giữ response cũ. Mỗi vòng là 1 LLM call plan + 1 critic call.

### C.4 Exclusion / negative condition

- Hai đường: (a) RankingTool input `unwanted`: list item titles user không muốn → mask điểm = −100000 (accuracy) hoặc 0 trong diversity sampling (`reco_model_tool.py:85-93,164-172,191-226`); (b) ToolBox tự merge `profile["unwanted"]` (từ `UserProfileMemory`: disliked items + history) vào ranking input khi có profile (`agent_plan_first_openai.py:66-71,115-127`).
- Không có "exclude category" — exclusion ở mức item, không ở mức thuộc tính (khác FilterTool của project có `exclude_categories_any`).

### C.5 Thiếu metadata

- Item thiếu category/attribute: SQL chạy trên pandas qua `pandasql.sqldf` (`corups/base.py:92-108`); giá trị NULL/NaN đơn giản không match `LIKE`/`=` → **bị loại im lặng**, giống hệt vấn đề của project. Không có `IS NULL` handling đặc biệt.
- Giảm nhẹ duy nhất: prompt `info()` cảnh báo "categorical columns … must use related values to search otherwise no result would be returned" (`corups/base.py:139`) + Critic được chỉ dẫn kiểm tra trường hợp 0 eligible items và gợi ý nới điều kiện (`prompt/critic.py:69`).

### C.6 Ranking tool — SASRec/RecLM-gen

- `RecModelTool` (`ranking/reco_model_tool.py`): load checkpoint bất kỳ tương thích `unirec` (`general.load_model_freely`, `:34`) — README nói SASRec/RecLM-gen fine-tuned trên domain. `model.predict` chấm điểm candidates theo `prefer` history (`:147-180`); `schema` ∈ {popularity (log visited_num+1, `:191-197`), similarity (điểm từ SoftFilter), preference (model)}.
- **Không cần fine-tuned model?** Constructor **luôn** load checkpoint (`:34`) → bắt buộc có file ckpt kể cả khi chỉ dùng popularity/similarity. Tuy nhiên 2 nhánh đó không gọi `model.predict` → về mặt kỹ thuật có thể subclass/stub `predict` hoặc bỏ load để chạy popularity-only; "chưa xác minh" mức độ dễ vá vì phụ thuộc `unirec` API.
- `visited_num` (popularity) có sẵn trong item table → popularity ranking dùng được ngay không cần model inference.

### C.7 Evaluation/simulator

- `eval/one_turn_eval.py`: multi-turn simulator (`user_simulator.py`, LLM đóng user với target ẩn, tối đa `--max_turns`) → metric **Hit** (rapidfuzz `partial_ratio > 80` giữa answer và target title, `:387-391`), **AT** (avg turn to hit), OAI token cost, `failed_times` của ToolBox (`:430-460`). `eval_single_turn.sh` chạy plan-first + reflection + dynamic demos.
- `eval/one_turn_eval_ranking.py`: thêm `get_rank` → NDCG (`:264-316`).
- Data eval (`simulator_test_data.jsonl` per domain) và `resources/` **không có trong repo** — tải ngoài. `demonstration/` có seed jsonl + fixed cases + generator/tagger/filter scripts để tự tạo demo.
- Tái dùng cho request đơn lượt: **được** — `one_turn_eval.py` đọc jsonl `{context, target}` bất kỳ; hit_judge là fuzzy title match. Giao thức của họ là multi-turn goal-directed (user giấu target, agent phải hỏi/ recommend tới khi trúng) — khác bài toán single-request của project nhưng `one_turn_conversation_eval` (`one_turn_eval.py:214-229`) nhận `{context: chat_history, target}` cũng dùng được cho single-turn.

### C.8 Bảng ánh xạ sang repo của ta

Project paths: planner `package/agents/planner/` (`plan_executor.py`, `_schema.py`, prompts `configs/agent/prompts.yaml`); tools `package/tools/` (`sql/filter_tool.py`, `sql/lookup_tool.py`, `ranking/similar_tool.py`, `ranking/rank_tool.py`, `retrieval/search_tool.py`, `base/_validation.py`); corpus `package/corpus/`; distill `package/agents/distill.py`; session constraints `package/agents/session.py`.

| Thành phần InteRecAgent | Tương ứng trong repo ta | Khoảng cách | Mượn được? | Chi phí |
|---|---|---|---|---|
| Plan-first ToolBox executor (`agent_plan_first_openai.py:23-152`) | `planner/plan_executor.py` + `toolkit/validate_tool_names.py` | Gần — cả hai đều LLM→plan→execute tuần tự; họ có thêm check tool-name + auto-append MapTool | Có: auto-repair plan (chèn tool bắt buộc cuối) + trả lỗi plan về cho LLM thay vì fail cứng | S |
| HardFilterTool = SQL tự do + rewrite_sql grounding (`sql_tool.py:78-106`) | `FilterTool` structured filters (`tools/sql/filter_tool.py`, `compile_filters.py`) | Xa — họ dùng SQL text, ta dùng JSON schema có validate key | Một phần: ý tưởng **grounding giá trị/cột trước execute** (fuzzy-match → canonical) đã có một phần trong `distill.py` ("normalized against corpus, exact/case-insensitive only") — có thể mở rộng fuzzy suggestion | M |
| SoftFilterTool = seed titles → item-sim matrix + ngưỡng (`itemcf_tool.py`) | `SimilarTool` (`tools/ranking/similar_tool.py`) | Gần về chức năng; họ lưu similarity scores vào buffer cho ranker "similarity" dùng lại | Có: truyền retrieval score sang ranker như một schema ranking (ta đã có `fuse_candidates.py`, `scoring/*`) | S |
| CandidateBuffer (ID list + similarity sidecar + track log) (`buffer/base.py`) | Candidate flow qua `candidate_ids.py`/`candidate_results.py`, `$N.candidates` refs trong plan | Trung bình — họ là single mutable buffer, ta là step outputs | Có: `track()` log (tool,input,output) cho critic — tương đương trajectory log ta đã có trong experiments | S |
| RankingTool schemas popularity/similarity/preference + `unwanted` mask (`reco_model_tool.py`) | `RankTool` (`tools/ranking/rank_tool.py`) + `scoring/*` | Trung bình — họ có 3 schema explicit do LLM chọn; unwanted→mask điểm | Có: schema "unwanted/prefer" tách khỏi filter; mask điểm thay vì xoá ID (giữ candidate pool, tránh empty) | M |
| Critic + rechain ≤3 (`critic/base.py`, `agent.py:168-184`) | Reflect mechanism trong planner (`reflect_rounds` trong configs/experiments) | Gần — project đã có reflect; khác ở chỗ critic của họ đọc **tool-track** chứ không chỉ text | Có: cho critic xem tool inputs/outputs (đặc biệt "0 eligible items") thay vì chỉ final answer | S–M |
| Fuzzy grounding title→id, cột→schema, value→categorical (`corups/base.py:253-259`, `sql_tool.py:78-106`) | `distill.py` normalize + `filter_tool.py:75-77` unknown-key error | Gần — ta reject unknown key (tốt cho `categories_exclude`) nhưng planner cứ lặp lại vì prompt mâu thuẫn | Có: thay "reject" bằng "suggest canonical value + warn" để planner tự sửa ở lần sau; và sửa `prompts.yaml:36` mâu thuẫn | S |
| LookUpTool SQL + token-budget truncation (`query/query_tool.py:39-110`) | `LookupTool` (`tools/sql/lookup_tool.py`) | Trung bình — họ trả records đã cắt theo token budget | Có: token-budget truncation cho tool output (nếu ta chưa có) | S |
| Item table `info()` inject schema+dtypes+ranges+sampled categorical values (`corups/base.py:114-144`) | Tương đương schema/catalog info trong prompts | Gần | Có: đưa **giá trị categorical hợp lệ + range thống kê** vào prompt thay vì để planner đoán (trực tiếp chống `categories_exclude` và filters rỗng do không biết giá trị) | S |
| UserProfileMemory (`memory/memory.py`, optional) | `MemoryTool` + `session.py` constraints | Xa về độ phức tạp | Chưa cần | — |

### Đối chiếu 3 lỗi đã biết của project

1. **~70% FilterTool calls dùng `filters: {}`**: InteRecAgent **không có structured filter** nên không gặp lỗi này trực tiếp; bài học tương đương: (a) `info()` của họ inject danh sách giá trị hợp lệ + note "must use related values otherwise no result" (`corups/base.py:139`) → planner biết phải điền gì; (b) Critic check "user wants recommendation without valid preference → tell agent to chat instead of using tools" (`prompt/critic.py:70`) — tức họ **phạt việc gọi tool khi không có điều kiện**, đúng bản chất lỗi filters rỗng của ta. Ta đã có `ask_user` escape trong prompt (`prompts.yaml` "If required information is missing … return ask_user") — chưa xác minh tỉ lệ planner dùng nó.
2. **Planner bịa key `categories_exclude`** (prompt tự mâu thuẫn `prompts.yaml:36`): InteRecAgent chống bằng grounding layer — cột lạ → fuzzy-match sang cột gần nhất, giá trị lạ → canonical value (`sql_tool.py:78-106`). Ta đã chống bằng `filter_tool.py:75-77` raise `ToolInputError` — tốt hơn là reject, nhưng planner vẫn lặp vì prompt mâu thuẫn; nên sửa prompt + thêm "allowed keys" list vào tool desc (họ làm điều này: `HARD_FILTER_TOOL_DESC` liệt kê rules, `prompt/tool.py:40-46`).
3. **Filter category loại im lặng ~9% item không category**: InteRecAgent **mắc cùng lỗi** — không có NULL handling trong SQL path. Cơ chế "chữa" của họ là hậu kỳ: Critic đọc tool-track, thấy "0 eligible items" → khuyên nới điều kiện (`prompt/critic.py:63-69`), và `SQLSearchTool` trả về info string "There are N eligible items" cho LLM thấy (`sql_tool.py:49`). Bài học: ta nên (a) đưa count eligible items vào tool response cho planner thấy (nếu chưa có), (b) cân nhắc semantics `categories_any` = "có category X" vs "item không category thì tính là không match" — quyết định sản phẩm, không phải copy từ họ.

## 5. Chưa xác minh / URL sai / repo rỗng

- **URL sai**: không có — cả 7 URL tồn tại và README khớp paper.
- **Repo rỗng/stub**: không có.
- **Chưa xác minh**:
  - iAgent `main_iagent_mp.py:149-150` `if i > 1: break` — cố ý (debug) hay bug giới hạn eval; ảnh hưởng con số metric trong paper.
  - InteRecAgent `buffer.replan()` (`buffer/base.py:132`) — không tìm thấy caller trong `llm4crs/` + `eval/` đã đọc; có thể dead code hoặc gọi từ `app.py` (chưa đọc hết `app.py`).
  - RecModelTool có chạy được với checkpoint không phải unirec/SASRec (ví dụ CrossEncoder) — phụ thuộc `unirec` API, chưa đọc package `unirec` (không có trong repo).
  - T-PRA: mapping chính xác giữa `reward_func` (0/1) trong `tpra_start.sh` và các thành phần reward — chỉ đọc prompt mô tả, chưa trace hết `env/steam.py`.
  - BiLLP: paper gốc của repo (README không nêu title/arXiv; repo tự gọi "BiLLP") — giả định đúng theo URL brief; nội dung method (A2C + grounding + distance penalty) đọc từ code, không đối chiếu paper.
  - VibeMus `experiments/evaluation.py` — chỉ liệt kê tên file, chưa đọc nội dung (eval nhạc, ngoài phạm vi recsys).
  - MemRec: `pruner_llm_rules.py`/`pruner.py` chi tiết chưa đọc sâu (chỉ đủ để trả lời Phase B); Stage-W neighbor propagation có vẻ mạnh nhưng chưa đánh giá rủi ro.

## 6. Đề xuất `.gitignore`

`cloned_repos/` hiện **không** nằm trong `.gitignore` → `git status` sẽ thấy ~550MB repo ngoài. Đề xuất thêm (không tự thêm theo brief):

```gitignore
# Third-party reference repos cloned for survey (see cloned_repos/MANIFEST.md)
/cloned_repos/*/
!/cloned_repos/MANIFEST.md
!/cloned_repos/REPORT.md
```

Đặt ở root `.gitignore` (cùng cấp `src/`). Nếu muốn giữ khả năng `git add cloned_repos` có chọn lọc thì chỉ cần `/cloned_repos/*/`. Lưu ý: `MANIFEST.md`/`REPORT.md` là file ta tạo nên có thể cân nhắc commit hoặc cũng ignore tùy ý — đề xuất trên giữ 2 file report được track.
