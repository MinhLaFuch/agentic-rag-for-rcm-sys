# Architectural Decisions Log

Định dạng mỗi quyết định: WHAT / WHY / EVIDENCE / ALTERNATIVES REJECTED / RISK.

## D-001: Kiến trúc hệ thống là hybrid (non-LLM core + LLM agent layer mỏng)
- **WHAT:** LLM chỉ đảm nhận reranking (Top-20→Top-10), planning, explanation, memory orchestration — không đảm nhận retrieval/ranking gốc.
- **WHY:** LLM không hiệu quả và không đáng tin cậy khi phải chấm điểm/rank toàn bộ catalog lớn; chi phí và latency không khả thi; risk hallucination cao khi context quá lớn.
- **EVIDENCE:** Lin et al. 2026 — cảnh báo context overload, retrieval bias, spurious grounding khi RAG/agent xử lý corpus lớn không giới hạn.
- **ALTERNATIVES REJECTED:** LLM-as-full-ranker (loại vì không kiểm soát được cost/latency và không có cơ sở học thuật ủng hộ ở quy mô catalog lớn).
- **RISK:** nếu retrieval layer yếu, agent layer sẽ bị giới hạn bởi candidate pool kém — cần đo E4/E5 riêng để cô lập vấn đề này.

## D-002: Agent dùng đúng 4 module Profile/Memory/Planning/Action
- **WHAT:** kiến trúc agent theo 4 module.
- **WHY:** đây là cấu trúc được xác nhận trực tiếp trong Peng et al. 2025 (EMNLP Findings 2025), không phải tự đặt ra.
- **EVIDENCE:** research_review.md §1.1.
- **ALTERNATIVES REJECTED:** kiến trúc ReAct thuần (chỉ Reasoning+Acting, không tách Profile/Memory riêng) — bị loại vì thiếu khả năng kiểm soát leakage temporal (memory/profile cần tách riêng để audit theo mục VI).
- **RISK:** overhead thiết kế 4 module tách biệt cho phase đầu; chấp nhận vì đổi lại khả năng test riêng từng module.

## D-003b: Reference architecture cho Agent layer là InteRecAgent/RecAI, không phải MACRec
- **WHAT:** dùng InteRecAgent (Huang et al., ACM TOIS; Microsoft RecAI, MIT license) làm kiến trúc tham khảo chính cho Phase 8 single-agent.
- **WHY:** InteRecAgent có đúng pattern "LLM = brain, recommender model = tool" + memory bus + plan-first task planning + reflection — khớp gần như 1:1 với mục IV (tool list) và mục XII (workflow) của spec gốc, chặt hơn MACRec (thiết kế cho multi-agent, không phải single-agent).
- **EVIDENCE:** research_review.md §2 — abstract + core methodology đã đọc, license MIT đã xác minh trên GitHub.
- **ALTERNATIVES REJECTED:** dùng MACRec làm reference chính cho single-agent (loại vì MACRec vốn thiết kế cho multi-agent, áp vào single-agent sẽ phải bỏ bớt phần lớn kiến trúc, không hiệu quả).
- **RISK:** thấp — MIT license cho phép tái sử dụng pattern kiến trúc tự do, chỉ cần giữ credit khi có.

## D-006: Fallback strategy khi price null (54.83% item Video_Games thiếu price)
- **WHAT:** khi user có budget constraint cứng (ví dụ "≤1000 USD") nhưng candidate có `price=null`, `ConstraintFilteringTool` KHÔNG loại thẳng item mà chuyển sang trạng thái "unknown_price" — đưa vào một nhóm riêng, chỉ hiển thị nếu số candidate có price hợp lệ không đủ Top-N, và luôn gắn cờ `price_unknown=true` để `ExplanationTool` không bao giờ bịa giá.
- **WHY:** 54.83% item thiếu price là EDA thật (không phải ước lượng) — nếu loại thẳng sẽ mất hơn nửa catalog cho mọi query có budget constraint.
- **EVIDENCE:** `data_specification.md` §1.3 — EDA thật trên 137,269 item.
- **ALTERNATIVES REJECTED:** loại thẳng item thiếu price khỏi candidate pool ngay từ retrieval layer — bị loại vì làm mất quá nhiều candidate hợp lệ (nhiều item có rating_number cao nhưng price null).
- **RISK:** cần thêm logic UI/explanation để không gây hiểu lầm rằng hệ thống "biết" giá.

## D-007: Categories là multi-label taxonomy, không dùng so sánh bằng nhau tuyệt đối
- **WHAT:** `SimilarItemTool`/`PopularityTool` khi so khớp category phải dùng phép giao tập hợp (set intersection) trên `categories`, không so sánh string bằng nhau.
- **WHY:** EDA thật cho thấy mỗi item có nhiều category (ví dụ 1 item vừa thuộc "Video Games", "PC", "Games") — đây là taxonomy path, không phải nhãn đơn.
- **EVIDENCE:** `data_specification.md` §1.3 — top 15 category có tổng count > num_items nhiều lần, xác nhận multi-label.
- **RISK:** thấp — chỉ là thay đổi cách implement filter, không ảnh hưởng kiến trúc tổng thể.

## D-008: Sparse threshold = 3, chưa cắt bỏ dữ liệu quá cũ (giữ toàn bộ 1998–2023)
- **WHAT:** đặt `sparse_threshold=3` cho `segment_users()` (user có 2-3 interaction = sparse_history, khác với new=0 và warm=≥5... khoảng 4 interaction là vùng chuyển tiếp, tạm gộp vào sparse). Chưa cắt bỏ dữ liệu trước một năm nào đó dù time span 24.8 năm (1998-2023) có concept drift.
- **WHY:** dữ liệu thật cho median=1, p90=3 → threshold=3 tách đúng theo phân phối thật (không phải số tự chọn). Việc cắt bỏ dữ liệu cũ cần cân nhắc trade-off (giảm concept drift vs giảm thêm dữ liệu vốn đã cực sparse) — quyết định này cần thêm phân tích theo năm (số lượng interaction theo từng năm) trước khi cắt, nên **trì hoãn sang Phase 3** khi có thể phân tích timestamp distribution chi tiết hơn.
- **EVIDENCE:** `data_specification.md` §11 — EDA thật (median=1, p90=3, span 24.8 năm).
- **RISK:** nếu không cắt dữ liệu cũ, sequential model có thể học nhầm pattern lỗi thời (console/giá 1998-2005 không còn liên quan 2023) — cần theo dõi ở Phase 5 bằng cách so sánh model train full-history vs recent-only qua ablation.

## D-009: Temporal split là global-by-timestamp, không phải leave-one-out per-user
- **WHAT:** `temporal_split()` cắt theo 2 ngưỡng timestamp toàn cục (train/val/test theo tỷ lệ 80/10/10 trên toàn bộ interaction), không phải kiểu "leave-last-item-out" phổ biến trong literature sequential rec.
- **WHY:** mục VI của spec gốc chỉ định rõ "train < validation < test" ở cấp độ toàn cục — cách này an toàn hơn cho leakage audit (chỉ cần so 2 số cutoff), dù có nhược điểm: với dataset cực sparse (72% user chỉ 1 interaction), nhiều user sẽ "biến mất" hoàn toàn khỏi validation/test nếu interaction duy nhất của họ rơi vào train.
- **EVIDENCE:** `data_specification.md` §5 (nguyên tắc leakage), test thật `tests/test_temporal_split.py` + `tests/test_leakage_check.py` (45/45 pass).
- **ALTERNATIVES REJECTED:** leave-one-out per-user (loại vì khó audit leakage tập trung, và một số leave-one-out approach tính profile "toàn bộ trừ item cuối" — dễ vô tình rò rỉ nếu implement sai).
- **RISK đã xác nhận qua chạy thử:** với 1 chiều lọc k-core (min_user=5), số lượng "warm" user trong test set thực tế sẽ nhỏ hơn con số 117,742 ước tính ở `decisions.md`/`data_specification.md` §11 (con số đó chưa qua bước 2 chiều lẫn temporal split) — cần chạy pipeline thật (Phase 3) để có số liệu chính xác cuối cùng.

## D-010: Mở rộng multi-domain — thêm Toys_and_Games và Electronics
- **WHAT:** hệ thống hỗ trợ 3 domain: `Video_Games` (primary), `Toys_and_Games` (secondary, audience adjacency), `Electronics` (secondary, functional adjacency). Item id được namespace `"{domain}::{parent_asin}"`; `user_id` **giữ nguyên, không namespace** (Amazon user_id là global across category).
- **WHY:** (1) audience adjacency — người mua game và người mua đồ chơi/board game có tỷ lệ chồng lấp cao (gia đình, gift-buying); (2) functional adjacency — EDA thật ở Phase 2 đã cho thấy subcategory "Headsets" (7,222), "Controllers" (10,875), "Cases & Storage" (6,087) trong chính Video_Games — đây là loại accessory thường nằm trong Electronics, tín hiệu cross-sell trực tiếp; (3) **giảm cold-start**: user_id global nghĩa là khi gộp domain, user có 3 interaction ở Video_Games + 3 ở Toys_and_Games sẽ đạt ngưỡng warm (≥5) dù không đạt riêng lẻ ở domain nào — đã **verify bằng test end-to-end thật** (xem bên dưới), không phải suy luận lý thuyết.
- **EVIDENCE:** `tests/test_domain_registry.py` (8 test, bao gồm test chống ID collision `test_merge_domains_prevents_id_collision`); chạy thử `scripts/run_multidomain_pipeline_local.py` với dữ liệu giả 2 domain — kết quả thật: **0 user warm nếu tính riêng từng domain, 10 user warm sau khi gộp** (log: `per_domain_warm_users={'Video_Games': 0, 'Toys_and_Games': 0} combined_warm_users=10`).
- **ALTERNATIVES REJECTED:** namespace cả user_id theo domain (loại vì sẽ triệt tiêu chính lợi ích cross-domain — mất khả năng nhận ra "đây là cùng 1 user"); gộp domain nhưng bỏ qua namespacing item (loại vì rủi ro ID collision thật nếu 2 domain vô tình có parent_asin trùng — đã test chứng minh cần thiết).
- **RISK:** (1) k-core filtering trên dữ liệu đã gộp làm ngưỡng "warm" mang ý nghĩa khác so với single-domain (nay là tổng interaction across-domain, không phải per-domain) — phải luôn báo cáo rõ 2 con số riêng biệt (per-domain vs combined) để không gây hiểu nhầm, đã implement sẵn trong step `cold_start_mitigation_check`; (2) Electronics dự kiến có quy mô lớn hơn đáng kể so với Video_Games/Toys_and_Games — cần theo dõi thời gian xử lý thực tế khi người dùng chạy trên máy, có thể cần sampling nếu quá lớn cho local-first.
- **CHƯA LÀM (Phase tiếp theo):** áp dụng multi-domain vào Agent tool layer (`CandidateRetrievalTool`, `SimilarItemTool` cần tham số `domain` optional để lọc/mở rộng cross-domain candidate) — hiện tại D-010 chỉ giải quyết phần DATA pipeline, chưa đụng đến `architecture.md` Agent layer, sẽ cập nhật khi tới Phase 8.

## D-003: Không implement multi-agent ở Phase 8
- **WHAT:** single-agent baseline trước, multi-agent (MACRec-inspired) chỉ nghiên cứu ở Phase 10.
- **WHY:** mục XIII của spec gốc yêu cầu chứng minh lợi ích bằng ablation trước khi đưa multi-agent vào core.
- **EVIDENCE:** research_review.md §2 (MACRec).
- **RISK:** có thể phải re-architect một phần agent layer nếu multi-agent chứng minh có lợi — chấp nhận, ghi nhận trong roadmap.

## D-004: Domain và sequential model cụ thể CHƯA được chốt ở Phase 0
- **WHAT:** trì hoãn việc chọn domain (Amazon Reviews 2023 category) và model sequential cụ thể sang Phase 2/Phase 5.
- **WHY:** mục VIII spec gốc cấm "chọn model chỉ vì phổ biến" — cần EDA thật để quyết định có cơ sở.
- **RISK:** chậm tiến độ nhưng tránh phải revert quyết định lớn giữa project (đúng nguyên tắc mục II).
