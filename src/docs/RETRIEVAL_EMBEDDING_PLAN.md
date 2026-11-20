# Kế hoạch Nâng cấp Tầng Retrieval: Tích hợp Hybrid Dense Embedding & RRF

> **Tài liệu Kế hoạch Kỹ thuật**  
> **Dự án**: Nghiên cứu và Ứng dụng Mô hình Agentic RAG trong Hệ thống Cá nhân hóa mua sắm trên nền tảng Thương mại Điện tử Việt Nam  
> **Mục tiêu**: Giải quyết điểm nghẽn (bottleneck) ở tầng Retrieval, nâng cao Candidate Recall và đa dạng hóa ứng viên cho khâu Reranking và Agent.

---

## 1. Bối cảnh & Chẩn đoán Điểm nghẽn Hiện tại

### 1.1. Hiện trạng triển khai
Trong kiến trúc hiện tại ([`package/tools/retrieval/search_tool.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/package/tools/retrieval/search_tool.py)):
- Công cụ tìm kiếm văn bản `SearchTool` được gọi là *"semantic"* nhưng thực chất **100% dựa trên SQLite FTS5 (Full-Text Search) + BM25** trên bảng `items_fts` (`title`, `store`, `main_category`, `categories`).
- Chưa có vector embedding thực tế cho sản phẩm cũng như truy vấn.
- Kỹ thuật tách từ và tạo query dựa vào `_tokenize()` và nối các token bằng toán tử `OR`:
  ```sql
  SELECT items.*, -bm25(items_fts) AS score 
  FROM items_fts JOIN items ON items.rowid = items_fts.rowid
  WHERE items_fts MATCH 'token1 OR token2 ...' AND <structured_filters>
  ORDER BY score DESC, items.rating_number DESC;
  ```

### 1.2. Các điểm nghẽn nghiêm trọng (Key Bottlenecks)

1. **72.21% người dùng là Cold-Start**:
   - Nhóm người dùng này không có lịch sử mua hàng, làm tê liệt mô hình Collaborative Filtering (`SimilarTool` / `ItemKNN`).
   - Gánh nặng gợi ý dồn toàn bộ lên `SearchTool` và `popularity`. Nếu `SearchTool` chỉ dùng từ khóa rời rạc, danh sách ứng viên trả về sẽ rất nông hoặc rỗng.

2. **Lệch pha Từ vựng (Vocabulary Mismatch) & Bất đồng Ngôn ngữ Việt – Anh**:
   - Dữ liệu sản phẩm Amazon 100% tiếng Anh. Người dùng Việt Nam đưa ra các truy vấn tự nhiên như: *"tai nghe gaming chống ồn tốt"*, *"chuột công thái học làm văn phòng"*.
   - Hệ thống hiện tại buộc LLM phải tự dịch sang từ khóa tiếng Anh. Nếu LLM trích xuất các từ quá chung (ví dụ: `"gaming"`, `"good"`), câu lệnh `OR` của SQLite sẽ lấy về hàng nghìn phụ kiện rác (dây cáp, ốp, miếng dán...) làm tràn ngân sách `limit`.

3. **Cơ chế nối `OR` làm tụt Precision**:
   - Khi truy vấn dài (4–6 từ), phép nối `OR` trong FTS5 làm cho các sản phẩm chỉ trùng 1 từ phổ biến vẫn được chọn, đẩy các sản phẩm thỏa mãn toàn bộ ngữ cảnh ra khỏi Top-K.

4. **Giới hạn trong Đánh giá Ngoại tuyến (`candidate_recall.py`)**:
   - Khi benchmark offline, query được sinh từ lịch sử (`history`: ghép title của các item vừa xem). BM25 chỉ tìm được những sản phẩm trùng từ khóa hoặc trùng model/thương hiệu, bỏ lỡ các sản phẩm thay thế (substitutes) có cùng phong cách hoặc công năng nhưng khác từ vựng.

---

## 2. Mục tiêu Cải tiến (Objectives & Target Metrics)

| Tiêu chí | Hiện trạng (BM25 FTS5 thuần) | Mục tiêu sau nâng cấp (Hybrid Retrieval) |
| :--- | :--- | :--- |
| **Bản chất Retrieval** | Khớp từ khóa cú pháp (Lexical Match) | Kết hợp Ngữ nghĩa sâu (Dense Vector) + Từ khóa chính xác (BM25) |
| **Truy vấn Đa ngôn ngữ** | Phụ thuộc hoàn toàn vào khâu LLM dịch từ | Hiểu trực tiếp câu hỏi Tiếng Việt -> map sang Vector sản phẩm Tiếng Anh |
| **Candidate Recall@100 (Cold/Sparse)** | Thấp, dễ bị rỗng khi query dài | Tăng tối thiểu **+15% - 25%** trên tập test validation |
| **Khả năng chịu lỗi** | Rỗng nếu không khớp chính xác từ | Trả về các sản phẩm gần nghĩa nhất nhờ Cosine Similarity |
| **Độ trễ (Latency)** | < 15ms (SQLite) | < 45ms (FAISS FlatIP / Vector Matrix song song SQLite) |
| **Hợp đồng hệ thống** | `SearchTool(query, filters, limit)` | **Giữ nguyên 100% Interface**, không làm sửa đổi Planner/Agents |

---

## 3. Kiến trúc Đề xuất: Hybrid Retrieval với Reciprocal Rank Fusion (RRF)

```
                            [User Query (VI / EN)]
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
          ┌────────────────────────┐      ┌────────────────────────┐
          │   Dense Vector Search  │      │   Lexical BM25 Search  │
          │ (Sentence-Transformers │      │   (SQLite FTS5 BM25)   │
          │  / BGE-M3 / FAISS)     │      │                        │
          └────────────┬───────────┘      └────────────┬───────────┘
                       │ Top-2N Dense                  │ Top-2N Lexical
                       └───────────────┬───────────────┘
                                       ▼
          ┌────────────────────────────────────────────────────────┐
          │     Reciprocal Rank Fusion (RRF_60) & SQL Filtering    │
          │  (Hợp nhất thứ hạng + Lọc cứng giá / category / domain)│
          └────────────────────────────┬───────────────────────────┘
                                       ▼
                            [Top-K Candidate Items]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   RankTool (CandidateScorer)  │
                       └───────────────────────────────┘
```

### Công thức Hợp nhất RRF_60 (Reciprocal Rank Fusion):
Hệ thống sử dụng công thức RRF đã được chuẩn hóa trong [`analyze_ranking_bottlenecks.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/scripts/evaluation/analyze_ranking_bottlenecks.py#L42-L48):
$$\text{Score}_{\text{RRF}}(d) = \sum_{m \in \{\text{dense}, \text{bm25}\}} \frac{1}{60 + \text{rank}_m(d)}$$

- **BM25**: Chịu trách nhiệm bắt chính xác model, thương hiệu, mã linh kiện (`RTX 4060`, `Keychron K2`, `Logitech`).
- **Dense Embedding**: Chịu trách nhiệm hiểu ngữ nghĩa, tính năng, nhu cầu trừu tượng (`êm ái`, `nhỏ gọn mang đi học`, `game bắn súng sinh tồn`).

---

## 4. Thiết kế Chi tiết các Module

### 4.1. Module Embedding & Vector Store (`src/package/embeddings/`)
Cấu trúc thư mục mới:
```
src/package/embeddings/
├── __init__.py
├── encoder.py              # Wrapper cho Text Encoder (hỗ trợ local SentenceTransformers & OpenAI API)
├── vector_store.py         # Quản lý ma trận vector (Numpy Cosine / FAISS FlatIP)
└── build_embeddings.py     # Script offline đọc SQLite ItemCorpus -> sinh item_embeddings.npz
```

1. **Lựa chọn Mô hình Encoding**:
   - **Lựa chọn 1 (Ưu tiên local CPU/GPU)**: `BAAI/bge-m3` hoặc `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Hỗ trợ cross-lingual (Việt - Anh) xuất sắc, kích thước nhỏ gọn.
   - **Lựa chọn 2 (API-based)**: Tích hợp qua [`package/api/openai_compatible_provider.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/package/api/openai_compatible_provider.py) tới endpoint `/v1/embeddings` (ví dụ: `text-embedding-3-small`).

2. **Quy chuẩn văn bản hóa sản phẩm (Item Text Representation)**:
   Để vector nắm bắt đầy đủ thông tin nhất, văn bản đầu vào cho mỗi item được tạo từ:
   ```python
   text = f"{title}. Category: {', '.join(categories)}. Store: {store}. Features: {features[:300]}"
   ```

3. **Lưu trữ & Cache**:
   - Lưu trữ ma trận vector tại `resource/corpus/<tag>/item_embeddings_<tag>.npy` hoặc `.npz`.
   - Lưu kèm bảng tra cứu index: `item_ids_<tag>.json` để ánh xạ giữa hàng ma trận và `item_id`.

### 4.2. Nâng cấp `SearchTool` (Backward-Compatible)
Sửa đổi [`package/tools/retrieval/search_tool.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/package/tools/retrieval/search_tool.py):
- Nhận thêm tham số tùy chọn `vector_store: VectorStore | None = None` trong `__init__`.
- **Nguyên tắc Graceful Fallback**:
  - Nếu `vector_store is not None` và đã nạp embedding: Thực hiện truy vấn Hybrid (Dense + BM25) rồi gộp RRF.
  - Nếu không có vector store: Tự động chạy BM25 FTS5 thuần như hiện tại (không làm ảnh hưởng tới bất kỳ test suite cũ nào).

### 4.3. Bổ sung User Embedding Retrieval (Tùy chọn cho Phase sau)
- Với người dùng có lịch sử mua sắm (`recent_items` từ `MemoryTool`), hệ thống có thể lấy trung bình có trọng số (exponential decay pooling) của các item embedding để đại diện cho User Profile Vector.
- Truy vấn trực tiếp các sản phẩm có cosine similarity cao nhất với User Profile, bổ sung thêm một nguồn candidate mạnh mẽ song song với `ItemCF`.

---

## 5. Lộ trình Triển khai Chi tiết (Actionable Roadmap)

### Giai đoạn 1: Xây dựng Module Mã hóa & Sinh Embedding (Offline Pipeline)
- [x] **Task 1.1**: Thêm `package/embeddings/text_encoder.py` với contract `TextEncoder` cho adapter encode float32. Model/tokenizer cụ thể vẫn được pin và chạy trong môi trường offline riêng.
- [x] **Task 1.2**: Thêm `package/embeddings/vector_store.py` hỗ trợ chuẩn hóa cosine, exact search, lưu/đọc `vectors.npy` + `item_ids.json` + manifest; chưa dùng FAISS để giữ runtime dependency-free.
- [ ] **Task 1.3**: Viết script CLI `scripts/data_pipeline/build_item_embeddings.py` đọc database `corpus_<tag>.sqlite`, encode toàn bộ catalog và lưu artifact `item_embeddings.npz`.

### Giai đoạn 2: Tích hợp Hybrid Search vào `SearchTool` & `ItemCorpus`
- [ ] **Task 2.1**: Mở rộng `ItemCorpus` để nhận diện và nạp song song `VectorStore` (nếu có file cache).
- [x] **Task 2.2**: Cập nhật phương thức `execute()` trong `SearchTool`:
  - Thực hiện BM25 lấy $N$ candidates từ FTS5.
  - Thực hiện Dense Search lấy $N$ candidates từ VectorStore (có áp dụng filter SQL trên tập rút gọn).
  - Áp dụng thuật toán `rrf_60` hợp nhất 2 danh sách, gán trường `score` và trả về kết quả.
- [x] **Task 2.3**: Viết unit/contract tests cho VectorStore, TextEncoder và Hybrid `SearchTool` trong `src/tests/tools/retrieval/`.

### Giai đoạn 3: Đánh giá Benchmark & Chẩn đoán Lợi ích (Evaluation)
- [ ] **Task 3.1**: Cập nhật [`scripts/evaluation/candidate_recall.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/scripts/evaluation/candidate_recall.py) để bổ sung nguồn `hybrid` bên cạnh `semantic` (BM25), `item_cf`, `popularity`.
- [ ] **Task 3.2**: Chạy đo lường so sánh Candidate Recall@50, Recall@100, Recall@200 trên 3 phân khúc user: `cold`, `sparse`, `warm`.
- [ ] **Task 3.3**: Chạy [`analyze_ranking_bottlenecks.py`](file:///d:/DACNTT/src/agentic-rag-for-rcm-sys/src/scripts/evaluation/analyze_ranking_bottlenecks.py) để kiểm chứng mức độ giảm thiểu mất mát ứng viên (retrieval loss) trước khi vào khâu `RankTool`.

---

## 6. Phân tích Rủi ro & Giải pháp Kiểm soát

| Rủi ro tiềm ẩn | Mức độ | Biện pháp kiểm soát & Phòng ngừa |
| :--- | :---: | :--- |
| **Kích thước catalog lớn gây tốn RAM** | Trung bình | Sử dụng vector chiều thấp (384-d thay vì 1536-d), lưu trữ float16 hoặc dùng FAISS IVF-PQ (Quantization) nếu catalog > 200,000 items. |
| **Tăng độ trễ truy vấn (Latency)** | Thấp | Dense search chỉ chạy dot-product ma trận numpy chuẩn hóa, thời gian thực thi với 50,000 items chỉ ~5-15ms, hoàn toàn nằm trong time budget 5s của tool. |
| **Gãy các bài Unit Test hiện có** | Cao | Áp dụng nguyên tắc Fallback: nếu môi trường test không có file vector cache, `SearchTool` tự động chạy BM25 mặc định như trước đây. |
| **Thiếu thư viện ngoài trong môi trường** | Thấp | Code viết hỗ trợ cả fallback thuần `numpy` (dot product) không bắt buộc phải cài đặt `faiss-cpu`. |

