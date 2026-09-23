# System & Agent Architecture — PHASE 0 Specification

> Đây là kiến trúc **đề xuất** dựa trên research_review.md. Kiến trúc này sẽ không thay đổi lớn giữa các phase mà không cập nhật file này (nguyên tắc mục II).

## 1. Nguyên tắc thiết kế trung tâm

LLM/Agent **không thay thế** ranking/retrieval model chuyên biệt. Pipeline là hybrid, có thể tắt agent layer và vẫn có một recommender hoạt động được (đây là điều kiện để đo contribution của agent một cách trung thực — mục XVII).

```
User interaction
  → User Profile / Representation
  → Candidate Retrieval (non-LLM)
  → Sequential / Collaborative / Content-based Recommendation
  → Candidate Pool
  → Agentic Reasoning / Filtering / Reranking (LLM)
  → Final Recommendation
  → Explanation + User Interaction
  → Memory Update
```

## 2. Kiến trúc tầng hệ thống (system layers)

| Tầng | Thành phần | Trách nhiệm | Phụ thuộc LLM? |
|---|---|---|---|
| **Data layer** | `src/data/*` | ingest, clean, temporal split, leakage check | Không |
| **Representation layer** | `src/features/*`, `src/embeddings/*` | user/item embedding, semantic representation | Không (embedding model có thể là encoder riêng, không phải LLM sinh) |
| **Retrieval layer** | `src/retrieval/*` | candidate generation (collaborative/embedding/hybrid), FAISS index | Không |
| **Recommendation layer** | `src/recommenders/*`, `src/sequential/*` | baseline models, sequential model | Không |
| **Ranking layer** | `src/ranking/*` | deterministic filter (constraint, business rule), initial scoring | Không |
| **Agent layer** | `src/agents/*`, `src/tools/*` | planning, tool orchestration, LLM reranking, explanation | Có (chỉ ở đây) |
| **Memory layer** | `src/memory/*` | short/long-term, preference, interaction memory | Không (LLM chỉ đọc/viết qua MemoryTool, không tự truy cập) |
| **Evaluation layer** | `src/evaluation/*` | recommendation metrics + agent metrics | Không |
| **Serving layer** | `src/api/*`, `src/inference/*` | FastAPI, Streamlit UI | Gọi agent layer qua interface |

Sơ đồ dưới minh họa cách các tầng này ánh xạ vào luồng dữ liệu thực tế.

## 3. Kiến trúc Agent (4 module bắt buộc)

Theo Peng et al. 2025, agent trong RecSys cần 4 module: **Profile, Memory, Planning, Action**.

- **Profile module**: biểu diễn user hiện tại (không phải embedding thô, mà là structured summary: preferred category, price sensitivity, recent constraint) — được đọc từ `UserProfileTool`, không tự sinh bằng LLM.
- **Memory module**: giao tiếp qua `MemoryTool` (read/write/update/forget/retrieve/summarize) — LLM không có quyền truy cập trực tiếp memory store.
- **Planning module**: LLM chỉ quyết định *cần tool nào, thứ tự nào, cần hỏi thêm gì* — không tự tính toán ranking.
- **Action module**: thực thi tool call thật (retrieval, ranking, rerank, memory write) và trả kết quả structured (JSON) về Planning.

### 3.1 Danh sách Tool (Action layer) — theo mục IV của spec

| Tool | Input | Output | Ghi chú |
|---|---|---|---|
| `UserProfileTool` | user_id, timestamp t | structured profile tại thời điểm ≤ t | Bắt buộc tuân leakage rule |
| `InteractionHistoryTool` | user_id, window | list interaction (item_id, ts, rating) | Chỉ trả dữ liệu ≤ t |
| `CandidateRetrievalTool` | user representation | Top-N candidate ids | Gọi retrieval layer, có cache |
| `SequentialRecommendationTool` | user sequence | ranked candidate ids + score | Gọi sequential model đã train |
| `SemanticSearchTool` | query text / profile embedding | relevant product ids + snippet | Giới hạn Top-K, không trả full corpus |
| `ProductMetadataTool` | item_id | title, category, price, brand, attributes | Đọc từ item store |
| `SimilarItemTool` | item_id | similar item ids | Dựa trên embedding hoặc co-purchase |
| `PopularityTool` | domain/category | top popular items | Baseline fallback (cold-start) |
| `RankingTool` | candidate set + features | scored list | Model chuyên biệt, không phải LLM |
| `RerankingTool` | Top-20 candidates + user context | Top-5/10 với structured JSON `{item_id, score, reasons}` | Đây là nơi duy nhất LLM "ranking", với input đã bị giới hạn cứng |
| `MemoryTool` | user_id, operation | memory record(s) | CRUD-like, có prune/forget |
| `ExplanationTool` | recommendation + evidence | explanation text có trích dẫn evidence | Không hallucinate spec sản phẩm |

### 3.2 Agent workflow (single-agent baseline — Phase 8)

```
User Request
  → Intent Understanding (extract constraints: budget, category, priority)
  → Profile Retrieval (UserProfileTool)
  → Memory Retrieval (MemoryTool.retrieve)
  → Candidate Retrieval (CandidateRetrievalTool / SequentialRecommendationTool)
  → Constraint Filtering (deterministic, không dùng LLM)
  → Candidate Analysis (ProductMetadataTool, SemanticSearchTool)
  → Reranking (RerankingTool, giới hạn Top-20 → Top-5/10)
  → Explanation (ExplanationTool, evidence-grounded)
  → Memory Update (MemoryTool.write)
```

Ví dụ minh họa (constraint-based query "laptop lập trình ~1000 USD, ưu tiên pin"):
1. Intent Understanding trích: `category=laptop, budget<=1000, priority=battery`.
2. Profile + Memory retrieval lấy lịch sử liên quan (nếu có).
3. Candidate retrieval trả Top-100 (non-LLM).
4. Deterministic filter theo budget → Top-20.
5. RerankingTool (LLM) chấm điểm Top-20 dựa trên priority=battery, trả JSON có `reasons`.
6. ExplanationTool build câu trả lời cuối, trích evidence từ `ProductMetadataTool`/review summary thật.
7. MemoryTool ghi lại constraint mới (budget, priority) vào PreferenceMemory.

### 3.3 Multi-agent (Phase 10 — nghiên cứu, KHÔNG mặc định bật)

Tham khảo có điều chỉnh từ MACRec (Manager / User Analyst / Item Analyst / Searcher / Reflector), nhưng mỗi agent phải được đánh giá riêng qua ablation trước khi đưa vào core pipeline (mục XIII). Câu hỏi bắt buộc trả lời trước khi thêm agent nào vào pipeline chính:
- Agent này giải quyết vấn đề gì mà single-agent không giải quyết được?
- Agent này thêm bao nhiêu latency/token cost?
- Agent này cải thiện metric nào, đo bằng ablation nào?

Nếu không chứng minh được lợi ích → không đưa vào core, chỉ ghi nhận vào `research_matrix.md` như một hướng đã thử.

## 4. Ràng buộc kỹ thuật bắt buộc

- LLM reranking chỉ nhận Top-20 (đã qua retrieval + deterministic filter), không bao giờ nhận toàn bộ catalog (mục XIV).
- Memory không được nhồi toàn bộ vào context — phải qua `MemoryTool.retrieve` có giới hạn (mục XI).
- Mọi tool call phải log được: `timestamp, agent, action, tool, input hash, output, latency` (mục XXIII).
- LLMProvider phải là abstraction thay thế được (local LLM / OpenAI-compatible / Ollama / vLLM) — business logic không phụ thuộc trực tiếp 1 provider (mục XXI).

## 5. Việc còn lại trước khi implement (Phase 1+)

- Chốt domain cụ thể trong Amazon Reviews 2023 (Phase 2).
- Chốt sequential model cụ thể dựa trên EDA thật (Phase 5), không quyết định ở đây.
- Chốt embedding model cho semantic retrieval (Phase 6).
- Thiết kế schema chi tiết cho memory record (đã có field tối thiểu ở mục XI của spec gốc, sẽ cụ thể hoá ở Phase 7).
