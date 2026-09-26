# Research Review — PHASE 0

> Trạng thái: một số mục được xác nhận qua web search (abstract + cấu trúc), một số mục dựa trên kiến thức nền đã ổn định (kỹ thuật RecSys cổ điển). Mục nào **chưa đọc được full text / chưa chạy được code** sẽ được đánh dấu `BLOCKED`.

## 1. Hai paper nền tảng bắt buộc

### 1.1 "A Survey on LLM-powered Agents for Recommender Systems"
- **Tác giả:** Qiyao Peng, Hongtao Liu, Hua Huang, Jian Yang, Qing Yang, Minglai Shao.
- **Nơi công bố:** Findings of ACL: EMNLP 2025, tr. 11574–11583. Bản preprint: arXiv:2502.10050.
- **Problem formulation:** Recommender truyền thống yếu ở 3 điểm: (i) hiểu intent phức tạp của user, (ii) khả năng tương tác hạn chế (chủ yếu one-shot), (iii) thiếu khả năng giải thích. LLM-agent được đề xuất như một lớp bổ sung, không thay thế toàn bộ RecSys.
- **Taxonomy (architecture của paper):** chia phương pháp thành 3 paradigm:
  1. **Recommender-oriented** — agent tăng cường trực tiếp cơ chế ranking/retrieval cốt lõi (ví dụ AgentCF, RecMind).
  2. **Interaction-oriented** — agent hội thoại đa lượt để elicit preference, sinh gợi ý có giải thích.
  3. **Simulation-oriented** — multi-agent mô phỏng hành vi user–item để nghiên cứu dynamics hệ thống.
- **Module kiến trúc chung được xác nhận trong survey:** Profile, Memory, Planning, Action Execution — đúng như bốn module mà spec yêu cầu ở mục IV. Đây là bằng chứng trực tiếp cho quyết định thiết kế agent theo 4 module này (xem `decisions.md` D-002).
- **Dataset/evaluation (Table 3–4 của paper):** các benchmark phổ biến (Amazon, MovieLens, Yelp...) và metric chuẩn Recall@K, NDCG@K, HR@K — khớp với mục XVI của spec.
- **Repository:** đây là survey, không có repo chính thức; các phương pháp được khảo sát (AgentCF, RecMind, MACRec...) có repo riêng, xem mục 2.
- **Lý do áp dụng vào project:** dùng làm bản đồ để quyết định "agent nên làm gì" (planning/tool selection) và "agent không nên làm gì" (thay thế ranking model).
- **Giới hạn đã ghi nhận:** survey không cung cấp benchmark thống nhất giữa các phương pháp → project phải tự thiết kế experiment matrix (mục XVII), không thể copy số liệu từ paper.

### 1.2 "Autonomous Information Seeking: A Roadmap for Agentic Recommender Systems"
- **Tác giả:** Xinyu Lin, Yashar Deldjoo, Sunhao Dai, Honghui Bao, Xiaopeng Ye, Fatemeh Nazary, Wenjie Wang, Tommaso Di Noia, Jun Xu, Tat-Seng Chua.
- **Nơi công bố:** arXiv:2607.04433 (2026).
- **Taxonomy chính:** ba paradigm theo mức độ tự chủ (autonomy):
  1. **Agent-assisted recommendation** — agent hỗ trợ pipeline ranking hiện có (mức tự chủ thấp nhất, phù hợp làm baseline agentic đầu tiên của project).
  2. **Agent-as-recommender** — agent tự lập kế hoạch, gọi tool, tổng hợp kết quả thành recommendation cuối (đây là target chính của project — khớp mục XII).
  3. **Agent-as-user-simulator** — dùng agent để mô phỏng user (không nằm trong phạm vi phase đầu, chỉ ghi nhận cho roadmap tương lai).
- **Khung autonomy:** proactivity, context awareness, interaction flexibility, adaptivity — đúng 4 tiêu chí mở rộng được nêu ở mục IV của spec. → xác nhận mục IV không phải tự đặt ra mà bám theo roadmap thật.
- **Cảnh báo quan trọng về RAG (trích trực tiếp liên quan mục X, XI):** retrieval-augmented agent recommendation có thể fail vì (i) retrieval bias — pattern phổ biến/dễ retrieve chiếm ưu thế, (ii) context overload — evidence quan trọng bị "lost in the middle", (iii) spurious grounding — retrieved text tạo cảm giác đúng nhưng không liên quan nhân quả. → Đây là lý do trực tiếp cho nguyên tắc "không đưa toàn bộ dataset/memory vào prompt" (mục X, XI).
- **Evaluation methodology:** paper nhấn mạnh cần đánh giá ở mức trajectory (không chỉ output cuối), agent-contribution analysis (từng agent đóng góp gì) — khớp trực tiếp với mục XVI (agent metrics) và mục XVII (ablation).
- **Open challenges paper nêu:** lifelong user modeling, contextual abstraction, controllability, trustworthiness, privacy, scalability — dùng làm input cho `limitations.md` và roadmap sau Phase 14.
- **Repository:** survey, không có code chính thức.

## 2. Các công trình liên quan trực tiếp (đã tra cứu ở mức abstract/citation graph)

| Method | Vai trò trong taxonomy | Repo | License | Trạng thái đọc |
|---|---|---|---|---|
| **InteRecAgent / RecAI** (Huang et al., ACM TOIS 2023/2024, Microsoft Research) | **Recommender-oriented**, kiến trúc đúng nhất với project: LLM là "brain", recommender model truyền thống là "tool", có memory bus + plan-first task planning + reflection | `github.com/microsoft/RecAI` | **MIT — đã xác minh** | Abstract + core methodology đã đọc (tool selection, plan-first, memory bus). Đây là **reference architecture chính** cho Agent layer (thay vì chỉ tham khảo MACRec), vì spec gốc mục XII (workflow) và mục IV (tool list) gần như đồng nhất với thiết kế InteRecAgent |
| **MACRec** (Wang et al., SIGIR 2024) | Multi-agent: Manager, User/Item Analyst, Reflector, Searcher, Task Interpreter | `github.com/wzf2000/MACRec` | Chưa detect được license file qua search (GitHub licensee không trả kết quả rõ) → giữ `BLOCKED`, phải mở repo thật ở Phase 10 trước khi tái sử dụng bất kỳ dòng code nào | Abstract + framework figure đã đọc; dùng làm reference cho **multi-agent roles**, không dùng cho single-agent baseline |
| **AgentCF** (Zhang et al., WWW 2024) | **Simulation-oriented** (không phải recommender-oriented như review Phase 0 ghi nhận trước đó — đã sửa): mô phỏng user-agent và item-agent tương tác để học collaborative filtering ngầm | có code (gắn nhãn "Code" trong awesome-list agiresearch/AgentRecSys) | Chưa xác minh | Đã đọc abstract + conclusion đầy đủ. **Quyết định:** không dùng làm reference cho Phase 8 (mục tiêu khác — simulation, không phải serving thật); chỉ ghi nhận cho roadmap simulation-oriented tương lai |
| **RecMind** (Findings NAACL 2024) | Recommender-oriented, LLM-powered planning agent | Không có code công khai theo awesome-list | N/A | Chỉ có trích dẫn qua citation graph, chưa đọc full text — giữ `BLOCKED`, độ ưu tiên thấp vì đã có InteRecAgent làm reference chính |
| **ReAct** (Yao et al., ICLR 2023) | Nền tảng kỹ thuật cho Planning module (reasoning + acting xen kẽ) | `github.com/ysymyth/ReAct` | MIT (kiến thức nền ổn định) | Dùng làm base pattern cho Agent workflow (mục XII); InteRecAgent chính là ví dụ áp dụng ReAct-style pattern vào RecSys với cải tiến plan-first thay vì step-by-step ReAct thuần |

**Các hướng liên quan khác theo yêu cầu spec — trạng thái nghiên cứu:**
- *Sequential recommendation*: nền tảng kỹ thuật ổn định (SASRec — self-attentive sequential rec, BERT4Rec — bidirectional). Sẽ chọn cụ thể ở Phase 5 sau khi có EDA thật về độ dài sequence trong domain đã chọn — **chưa chọn model cụ thể ở Phase 0**, tránh vi phạm mục VIII ("không tự động chọn model chỉ vì phổ biến").
- *Retrieval-augmented recommendation*: xác nhận qua Lin et al. 2026 — 3 loại lỗi (bias, overload, spurious grounding) phải được kiểm soát bằng Top-N giới hạn cứng (mục IX, X).
- *LLM reranking*: khớp pattern "retrieval → Top-100 → deterministic filter → Top-20 → LLM rerank → Top-5/10" nêu ở mục XIV; đây là pattern phổ biến trong các hệ thống production-scale rerank (personalized re-ranking literature).
- *Memory-augmented recommendation*: bốn loại memory (Short-term, Long-term, Preference, Interaction) khớp với thiết kế memory trong cả hai survey nền tảng.
- *Multi-agent recommendation*: MACRec là reference architecture chính thức được spec chỉ định — sẽ nghiên cứu sâu ở Phase 10, KHÔNG implement ở Phase 8.
- *Cold-start / evolving-interest*: chưa có paper cụ thể được pin — sẽ bổ sung ở Phase 2 sau khi biết domain thật (mục XVIII).
- *Explainable recommendation*: yêu cầu evidence-grounded explanation (mục XV) khớp trực tiếp với cảnh báo "spurious grounding" của Lin et al. 2026.

## 3. Kết luận Phase 0 về research (đã cập nhật)

1. Hai survey nền tảng xác nhận kiến trúc 4-module (Profile/Memory/Planning/Action) và 3-paradigm autonomy là **có cơ sở học thuật**, không phải giả định tự đặt.
2. Cảnh báo về RAG failure modes (Lin et al. 2026) là lý do kỹ thuật trực tiếp cho các constraint cứng trong spec (không nhồi toàn bộ context, phải retrieval-limit).
3. **Thay đổi quan trọng so với báo cáo Phase 0 lần trước:** reference architecture chính cho Agent layer (Phase 8) không phải MACRec mà là **InteRecAgent/RecAI** (MIT license, đã xác minh) — vì nó đúng là "LLM = brain, recommender model = tool", khớp gần như 1:1 với mục IV và mục XII của spec gốc. MACRec chuyển vai trò sang reference cho multi-agent (Phase 10).
4. AgentCF đã được đọc kỹ hơn và **phân loại lại** từ "recommender-oriented" (nhận định sai ở báo cáo trước) sang đúng là "simulation-oriented" — không dùng cho Phase 8, chỉ ghi nhận cho roadmap sau này.
5. **BLOCKED còn lại:** license MACRec chưa xác minh được qua search (cần mở repo thật ở Phase 10); RecMind chưa có code công khai, độ ưu tiên đọc sâu được hạ xuống vì đã có InteRecAgent thay thế vai trò reference chính.
6. Domain sản phẩm cụ thể trong Amazon Reviews 2023 **chưa được chọn** — quyết định này thuộc Phase 2 (EDA), không thuộc Phase 0/1.
