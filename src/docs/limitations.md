# Known Limitations & Risks — PHASE 0

## 1. Hạn chế về research (đã cải thiện, còn một phần BLOCKED)
- **Đã giải quyết:** InteRecAgent/RecAI (reference chính cho Phase 8) — đã đọc abstract + methodology, **license MIT đã xác minh trực tiếp trên GitHub** (`microsoft/RecAI`). AgentCF đã đọc kỹ hơn (abstract + conclusion) và được phân loại lại đúng là simulation-oriented.
- **Còn BLOCKED:** chưa clone/chạy code thật của InteRecAgent, MACRec — chỉ ở mức đọc tài liệu, chưa chạy thử. License MACRec chưa detect được qua search (không có LICENSE file rõ ràng theo GitHub licensee) → phải mở repo thật để kiểm tra trước Phase 10, không tái sử dụng code MACRec cho đến khi xác minh xong.
- RecMind: không tìm thấy code công khai, độ ưu tiên đọc sâu được hạ xuống vì đã có InteRecAgent thay vai trò reference chính (mục XXVII vẫn yêu cầu tuân thủ nếu sau này quyết định dùng).

## 2. Hạn chế về dữ liệu
- **Đã giải quyết một phần (21/9):** người dùng đã upload `meta_Video_Games_jsonl.gz` thật (137,269 item, khớp số liệu công bố). Đã chạy EDA thật trên toàn bộ file (`src/data/metadata_eda.py`) — xem `data_specification.md` §1.3. Schema thật đã được xác nhận và sửa lại so với dự đoán ban đầu (không có field `brand` riêng, dùng `store`; `description` là list không phải string).
- **Đã giải quyết (22/9):** người dùng đã chạy `scripts/run_interaction_eda_local.py` local trên file `review_Video_Games.jsonl.gz` thật (không upload, chỉ paste report text) — có số liệu interaction thật: 2,766,656 user, 137,249 item, sparsity 99.9988%.
- **Phát hiện thật quan trọng — cold-start là trường hợp CHỦ ĐẠO, không phải edge case:** 72.21% user chỉ có 1 interaction; chỉ 4.26% user có ≥5 interaction (đủ cho sequential model). Sequential recommendation trong project này về bản chất chỉ áp dụng được cho một phần nhỏ (~4%) population thật — phải báo cáo rõ điều này trong mọi kết quả cuối, không để người đọc hiểu nhầm rằng sequential model đại diện cho toàn bộ user.
- Time span dữ liệu rất dài (1998-2023, ~24.8 năm) → rủi ro concept drift, chưa quyết định có cắt bớt dữ liệu cũ hay không (xem `decisions.md` D-008).
- Amazon Reviews 2023 không có user profile tường minh (tuổi, giới tính...) → user profile hoàn toàn derived từ hành vi, có thể kém chính xác với user sparse-history.
- **Phát hiện thật quan trọng:** 54.83% item Video_Games thiếu `price` — ảnh hưởng trực tiếp đến mọi kịch bản có budget constraint (xem `decisions.md` D-006). 37.69% thiếu description, 28.77% thiếu features — cần fallback khi `ExplanationTool` cần evidence nhưng metadata rỗng (không được bịa).

## 3. Hạn chế về kiến trúc agent (theo chính 2 survey nền tảng)
- RAG/retrieval-augmented agent có rủi ro retrieval bias, context overload, spurious grounding (Lin et al. 2026) — đã đưa vào constraint thiết kế (Top-K giới hạn cứng) nhưng không loại bỏ hoàn toàn rủi ro, chỉ giảm thiểu.
- Chưa có benchmark thống nhất giữa các phương pháp agentic recommendation trong literature → không thể so sánh trực tiếp số liệu project với số liệu paper khác, chỉ so sánh nội bộ qua ablation.
- Evaluation cho "trajectory-level" và "agent contribution" vẫn là open problem theo chính Lin et al. 2026 — project sẽ dùng metric tự thiết kế (mục XVI), không có ground truth chuẩn hoá ngành.

## 4. Hạn chế về tài nguyên/kỹ thuật (local-first)
- Chạy local (không bắt buộc Docker/cloud ở phase đầu) → giới hạn quy mô domain có thể chọn (phải đủ nhỏ để train sequential model + build FAISS index trên máy cá nhân).
- LLMProvider abstraction cần tương thích nhiều backend (local LLM, OpenAI-compatible, Ollama, vLLM) — chưa benchmark latency/cost thật của từng backend.

## 5. Rủi ro tiến độ
- Nguyên tắc "mỗi phase chỉ hoàn thành khi có code chạy được + test pass + experiment lưu thật" (mục XXVIII) có thể làm project chậm hơn cách làm demo thông thường — đây là trade-off chủ động để đạt chất lượng research-grade.

## 6. Cách xử lý các mục BLOCKED
Mọi mục đánh dấu `BLOCKED` trong các file docs khác phải được resolve theo format:
```
BLOCKED:
REASON:
REQUIRED ACTION:
```
trước khi phase liên quan được coi là hoàn thành.
