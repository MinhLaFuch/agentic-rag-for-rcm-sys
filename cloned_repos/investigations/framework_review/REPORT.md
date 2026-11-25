# REPORT — Review paper Type 1 / Type 2 single (DACNTT_2627) cho agentic-rag-for-rcm-sys

Ngày: 2026-11-25 (tiếp nối đợt trước). Phạm vi: 26 paper đủ điều kiện trong brief §1. Nguồn paper: `papers/` local → arXiv/ACL Anthology (text đã trích trong `investigations/framework_review/texts/`). Repo clone nông trong `cloned_repos/` (không commit). Mọi số liệu kèm nguồn; chỗ không đọc được nguồn ghi `chưa xác minh`.

## 1. Tóm tắt (10 dòng)

1. **Không paper nào eval đúng giao thức của project** (full-catalog + 1 held-out target, single request). Gần nhất: InteRecAgent one-turn *retrieval* task (Recall@5 trên toàn catalog) và AgentDR (full-ranking thật trên catalog vài nghìn–vài chục nghìn item).
2. **Đáng mượn nhất**: InteRecAgent (RecAI) — plan-first tool pipeline, hard/soft filter tách biệt, Candidate Bus, Critic+rechain; ItemRAG — item-side enrichment (co-purchase + semantic neighbors → text) và "latest Amazon Reviews 2023"; AgentDR — ủy quyền full-ranking cho ID-based tools + LLM chỉ fuse/rerank/replace-complement.
3. **RecMind** chứng minh LLM-agent thua xa model trained (P5/ENMF/SASRec) khi candidate pool lớn (100 item) — positional bias; hữu ích như baseline "agent thuần không retrieval".
4. **Nhiều paper "Amazon" thực ra không phải Amazon Reviews 2023**: đa số là Amazon 2014 (Ni et al. 2010) hoặc 2018 (Ni et al. 2019). Chỉ **ECPO** (AmazonReviews2023: Game/Book), **ItemRAG** ("latest Amazon Reviews"), và **CDA4Rec/PUMA** cần kiểm tra kỹ — CDA4Rec chưa rõ version.
5. **Pattern chung có thể mượn**: (a) LLM không tự rank catalog — luôn có retrieval tool/model bên dưới (InteRecAgent SASRec, AgentDR LightGCN/SASRec/SimpleX, ToolRec attribute tools, OptiRAG GCN); (b) grounding item bịa → nearest-neighbor/ID-map (BiLLP/T-PRA/InteRecAgent fuzzy-match); (c) memory/profile tách khỏi ranking (MemRec, RAH personality, AgentCF++ dual-layer).
6. **Metric paper đa dạng, không so trực tiếp được**: top-k trên pool 10–100 (đa số), full-catalog R@5/N@20 (InteRecAgent retrieval), CTR AUC/LogLoss (OptiRAG-Rec, R4EC — không phải top-k), success-rate multi-turn simulator (ECPO, InteRecAgent H@5/AT), custom Len/Reach/Rtraj (BiLLP/T-PRA).
7. **Tier C chủ yếu là sequential/session rec trên pool nhỏ** (10–50 candidates) với LLM làm reranker/reflection — ý tưởng reflection đáng mượn (DRDT, MoRE, SRLF, Re2LLM, R4EC) nhưng eval không liên quan full-catalog.
8. **Cảnh báo**: RAH thừa nhận random-assistant cũng cải thiện RS (data leakage); AgenticRAG gain chỉ +0.4% NDCG@10 (trong nhiễu); AgentCF++ "consistently outperforms" không đúng trên Cross-2 (thua SASRec).
9. **Repo rỗng duy nhất**: RecMind (README-only, tác giả ghi "cannot be open-sourced"). 11 repo còn lại có code thật; ECPO/ToolRec nặng (~76–104MB, kèm recbole/LLaMA-Factory).
10. **Không dùng được**: VibeMus (demo sinh nhạc, không phải recsys); RecAI toolkit paper (mô tả framework, không có eval độc lập — số liệu nằm ở InteRecAgent/RecLlama/RecLM papers riêng).

## 2. Bảng chỉ mục

| Tier | Framework | Type (xlsx) | Năm/Venue | Repo | Amazon version | Amazon categories (đã xác minh) | Metric chính | Giao thức |
|---|---|---|---|---|---|---|---|---|
| A | RecMind | Type 2 single | 2023, Findings NAACL 2024 | Có link nhưng **repo rỗng** | 2018 (Ni et al. 2019) | Beauty, Sports&Outdoors, Toys&Games (+Yelp) | RMSE/MAE, HR@5/10, NDCG@5/10 | Pool 100 (direct), full catalog sinh title (seq) |
| A | RAH | Type 1 | 2023 arXiv / 2024 IEEE TCSS | Có code | 2018 | Movies, Books, Video Games | NDCG@10, Recall@10 (proxy-feedback → downstream RS) | Không phải top-k rec trực tiếp |
| A | BiLLP | Type 2 single | 2024, SIGIR | Có code | ~2014 (amazon_v2) | Books | Len, Reach, Rtraj | Sequential env, không pool |
| A | InteRecAgent | Type 2 single | 2024, arXiv 2308.16505 | Có code (RecAI) | ~2014 (amazon_v2 link) | Beauty | H@5/AT (sim), R@5, N@20 | Retrieval = full catalog; ranking = pool 20 |
| A | Tool-Rec | Type 2 single | 2024, SIGIR | Có code | 2014 | Books | Recall@10, NDCG@10 | Full catalog qua attribute tools |
| A | AgentCF++ | Type 1 | 2025, SIGIR | Có code | 2014 (Ni et al. 2010) | Books, CDs&Vinyl, Movies, Video Games | MRR, NDCG (pool 10) | Pool 10 |
| A | ItemRAG | Type 1 | 2025 (SIGIR'26 short?) | Có code | **2023** ("latest") | Beauty, Toys&Games, Sports&Outdoors, Arts&Crafts | HR@1/3/5, NDCG@3/5 | Pool 10 |
| A | iAgent | Type 1 | 2025, ACL Findings | Có code | chưa xác minh (InstructRec) | Books (Amazon Book), +Movietv/Goodreads/Yelp | HR@1/3, NDCG@3, MRR | Candidate list từ dataset (chưa xác minh cỡ) |
| A | ECPO | Type 1 | 2025, arXiv 2506.14302 | Có code | **2023** (AmazonReviews2023) | Video Games, Books (+Yelp) | SR, Recall rate, WR | Multi-turn sim, 100 test tasks |
| A | T-PRA | Type 2 single | 2025, ACL | Có code | ~2014 (amazon_v2) | Books | Acce, IoR, Coh | Sequential env, target ẩn |
| A | MemRec | Type 2 single | 2026, ACL | Có code | chưa xác minh (InstructRec) | Books (+Goodreads, MovieTV, Yelp) | H@1/3/5, NDCG@1/3/5 | Pool 10 |
| B | RecAI (toolkit paper) | Type 2 single | 2024, arXiv | Có code | — | — (xlsx: None) | NDCG/Recall retrieval; pairwise explainer | Nhiều task, không thống nhất |
| B | VibeMus | Type 2 single | 2025 | Có code | — | — | Rubric score 0–10 (LLM judge) | Không phải recsys |
| C | DRDT | Type 2 single | 2023, arXiv | Không | chưa xác minh ("Amazon Review") | Video Games, Beauty (Luxury Beauty) | Recall@10/20, NDCG@10/20 | Pool 20 |
| C | CoRAL | Type 1 | 2024, arXiv 2403.06447 | Không | 2018 (chưa xác minh) | Appliances, Gift Cards, Software, Prime Pantry | AUC, F1 (long-tail) | Item classification, không top-k |
| C | CDA4Rec | Type 1 | 2025 | Không | chưa xác minh | Sports | HR/NDCG@5/10 | Full catalog |
| C | AKF-Agent | Type 1 | 2025 | Không | chưa xác minh | chưa xác minh (col H có Amazon) | HR@1/3/5 | chưa xác minh |
| C | OptiRAG-Rec | Type 1 | 2025, arXiv 2501.02173 | Không | 2018 (Ni et al. 2019) | Beauty, Video Games, Movies&TV | AUC, LogLoss, RPS | CTR pointwise, không top-k |
| C | AgenticRAG | Type 1 | 2025, arXiv 2510.02668 | Không | chưa xác minh | Electronics | NDCG@5/10, HR@10, MRR | chưa xác minh |
| C | MoRE | Type 2 single | 2025 | Không | 2018 (chưa xác minh) | Arts&Crafts, Video Games, Musical Instruments | HR, NDCG | Pool 50 |
| C | Re2LLM | Type 2 single | 2025 | Không | chưa xác minh | Video Games | chưa xác minh | Session-based, pool nhỏ |
| C | SRLF | Type 2 single | 2025 | Không | chưa xác minh | CD&Vinyl | NDCG | Pool 10 (1+9) |
| C | R4EC | Type 2 single | 2025 | Không | chưa xác minh | Books | AUC, LogLoss (CTR) | Pointwise, không top-k |
| C | RuleAgent | Type 2 single | 2025 | Không | chưa xác minh | Beauty (+Yelp, Gowalla) | R@10/20, N@10/20 | Pool nhỏ (chưa xác minh) |
| C | PUMA | Type 2 single | 2025, WWW | Không | chưa xác minh | Electronic, Home&Kitchen, Grocery, Clothing, Health&Household | Function/Result/Outcome accuracy | Web-agent tasks |
| C | AgentDR | Type 2 single | 2026, arXiv 2510.05598 | Không | Không phải Amazon Reviews — XMarket/Instacart | (xlsx ghi Electronic, Sports — thực chất XMarket) | Recall@10/20, NDCG@10/20, VDCG | **Full catalog** |

## 3. Bảng sai lệch xlsx ↔ paper

| Paper | Trường | xlsx | Paper/nguồn thực tế | Nguồn |
|---|---|---|---|---|
| RecMind | Model link | github.com/XMHZZ2018/RecMind | Repo tồn tại nhưng **chỉ có README**, ghi rõ không thể open-source | `cloned_repos/RecMind/README.md` |
| InteRecAgent | Dataset (H) | chỉ Beauty | Paper eval 3 domain: Steam, MovieLens-10M, Amazon Beauty | 2308.16505.txt §4.1 |
| AgentDR | Dataset (H/I) | "Amazon" Electronic, Sports | Thực chất **Instacart + XMarket** (Electronics, Sports — tập con sản phẩm Amazon, không phải Amazon Reviews) | 2510.05598.txt §4.1.1 |
| ItemRAG | Amazon categories (I) | Beauty, Toys&Games, Sports, Arts&Crafts | Khớp paper (4 domain Amazon Reviews mới nhất) | ItemRAG txt §4.1 |
| AKF-Agent | Amazon categories (I) | None | Cột H có Amazon → paper có dùng Amazon, category cụ thể chưa xác minh | paper txt |
| PUMA | Tên | "PUMA" | Framework PUMA trong paper "Large Language Models Empowered Personalized Web Agents" (PersonalWAB benchmark), WWW'25 | PersonalWAB txt |
| BiLLP | Dataset (H) | Books | Đúng Amazon-Book, nhưng là **amazon_v2** (~2014), filter ≥90 interactions — subset rất đặc | BiLLP txt §5.1 |
| OptiRAG-Rec | Type | Type 1 | Paper là bài toán **CTR prediction** (AUC/LogLoss/RPS), không phải top-k rec — "Type 1" theo nghĩa agentic nhưng giao thức khác hẳn | 2501.02173.txt |
| ECPO | Amazon version | — | Dùng **AmazonReviews2023** (GitHub hyp1231/AmazonReviews2023): Game + Book | ECPO txt §3.1 footnote 2 |
| AgentCF++ | Type | Type 1 | Paper tự mô tả là mô phỏng user/item agents để **cải thiện recommender**, không phải recommender agent trực tiếp | AgentCF++ txt §1 |
| RAH | Đánh giá | — | Không eval top-k trực tiếp; đo cải thiện downstream RS qua proxy feedback | 2308.09904.txt Table 5 |

(Ghi chú: các lệch nhỏ về tên viết tắt — "CD & Vinyls" vs "CDs", "Movies" vs "Movie&TV" — không liệt kê.)

## 4. Ma trận Amazon category × paper

Version quan trọng: project dùng **Amazon Reviews 2023**.

| Category | 2014 | 2018 | 2023 | Chưa rõ version |
|---|---|---|---|---|
| Beauty | BiLLP? (Books) — | RecMind, OptiRAG-Rec, DRDT(Luxury Beauty), MoRE?, RuleAgent | — | iAgent? |
| Sports & Outdoors | — | RecMind | — | — |
| Toys & Games | — | RecMind | — | — |
| Books | BiLLP, InteRecAgent?, T-PRA, Tool-Rec | RAH | ECPO, ItemRAG? no—ItemRAG không có Books | MemRec, R4EC |
| Movies / Movie&TV | AgentCF++ | RAH, OptiRAG-Rec | — | — |
| Video Games | AgentCF++ | RAH, OptiRAG-Rec | ECPO (Game) | DRDT(Games), MoRE, Re2LLM |
| CDs & Vinyl | AgentCF++ | — | — | SRLF |
| Arts & Crafts & Sewing | — | — | ItemRAG | MoRE |
| Musical Instruments | — | — | — | MoRE |
| Appliances / Gift Cards / Software / Prime Pantry | — | CoRAL | — | — |
| Electronics | — | — | — | AgenticRAG, PUMA, AgentDR(XMarket) |
| Home & Kitchen / Grocery / Clothing / Health&Household | — | — | — | PUMA |

**Chỉ ECPO xác nhận dùng Amazon Reviews 2023** (Game, Book). ItemRAG ghi "latest Amazon Reviews dataset" — rất có thể 2023 nhưng chưa trích được citation [3] để khẳng định (`chưa xác minh` — kiểm tra reference trong paper). CDA4Rec/PUMA/AKF-agent/MemRec/iAgent/R4EC/RuleAgent/Re2LLM/MoRE/SRLF/CoRAL/DRDT/AgenticRAG: version `chưa xác minh` (đa số paper cũ → nhiều khả năng 2014/2018).

## 5. Nhóm paper theo giao thức đánh giá

| Nhóm | Papers | So được với project (full catalog + 1 held-out)? |
|---|---|---|
| **Full catalog / near-full** | InteRecAgent (one-turn retrieval R@5 toàn catalog), AgentDR (full-ranking Instacart/XMarket), CDA4Rec (full ranking), Tool-Rec (attribute tools duyệt catalog), OptiRAG-Rec (CTR trên mọi item?), PUMA search task | **Gần nhất**: InteRecAgent retrieval task và AgentDR — cùng triết lý "LLM không tự rank catalog" |
| **Pool 100** | RecMind (direct rec) | Có — nhưng cho thấy LLM-agent yếu ở pool lớn |
| **Pool ~20–50** | DRDT (20), MoRE (50), AgentCF++/iAgent/MemRec/ItemRAG/SRLF (~10) | Không trực tiếp; hữu ích để so sánh reranker |
| **Pool 10** | AgentCF++, ItemRAG, MemRec, iAgent?, SRLF | Không — quá nhỏ so với full catalog |
| **Multi-turn simulator** | InteRecAgent (H@5/AT), ECPO (SR/R/WR), T-PRA/BiLLP (sequential env), RAH (proxy feedback) | Khác bài toán — nhưng ECPO/AILO simulator đáng tham khảo cho eval |
| **Không phải top-k** | OptiRAG-Rec & R4EC (AUC/LogLoss CTR), CoRAL (AUC/F1), RecAI (pairwise), VibeMus (rubric), BiLLP/T-PRA (Len/Reach/Rtraj) | Không |

---

## 6. Chi tiết từng paper — Tier A

### RecMind — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "RecMind: Large Language Model Powered Agent for Recommendation", Yancheng Wang, Ziyan Jiang và cộng sự (ASU + Amazon Alexa AI), Findings of NAACL 2024, tr. 4351–4364, arXiv:2308.14296 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo (link xlsx) + Amazon |
| Repo | github.com/XMHZZ2018/RecMind — **repo rỗng** (chỉ README, ghi "cannot be open-sourced"). License/commit: không có. |
| Backbone LLM / embedding | gpt-3.5-turbo-16k (ChatGPT API); text summarization qua HuggingFace Hub |

**1. Vấn đề và đóng góp.** LLM-agent zero/few-shot cho nhiều task rec (rating prediction, sequential, direct, explanation, conversational) với planning (ReAct-CoT, ToT BFS/DFS, Self-Inspiring), memory (personalized + world knowledge), tools (SQL database, web search, text summarization). Đóng góp chính: Self-Inspiring planning cải thiện khả năng dùng lịch sử trong planning.

**2. Kiến trúc chi tiết.**
- Pipeline: user query/task → LLM planner sinh `Thought / Action / Observation` → Action gọi tool (SQL→MySQL chứa review+metadata; Search→web API; Summarization→HF model) → lặp tới khi trả kết quả.
- Tools: Database Tool (NL→SQL trên MySQL: bảng product meta + bảng interaction), Search Tool (thông tin real-time, vd "product category of X"), Text Summarization Tool (tóm tắt review thành insight).
- Planning variants: RecMind-CoT (ReAct), RecMind-ToT (BFS/DFS), RecMind-SI (Self-Inspiring — tự "nghĩ lại" các state đã explore trước khi plan bước tiếp).
- Không có retrieval index/embedding; "retrieval" là SQL query trên DB. Không có ranker riêng — LLM tự chọn top-10 từ candidate list.
- Request → prompt tự nhiên + item names; không structured schema. Direct rec: prompt "choose the top 10 items to recommend … Candidates: [Item List]".
- Xử lý lỗi: không nêu cơ chế chống item bịa/SQL sai — paper ghi nhận **positional bias** (LLM thiên vị item đầu candidate list) là hạn chế chính.

**3. Dữ liệu.** Amazon Reviews (Ni et al. 2019 → bản **2018**), domains Sports&Outdoors, Beauty, Toys&Games; thêm Yelp cho một số task. Kết quả chi tiết chủ yếu report trên Beauty + Yelp (Table 1–3). Chia dữ liệu theo P5 protocol; `chưa xác minh` chi tiết k-core/LOO. Direct rec: pool = **100 candidates** (1 positive + 99 random negatives), mỗi test case một lần. Sequential: predict next item title.

**4. Metric và kết quả** (nguồn: Table 1–3, §4.3):

| Dataset / Task | Metric | k | RecMind (best variant) | Baseline mạnh nhất | Ghi chú |
|---|---|---|---|---|---|
| Beauty rating pred | RMSE | — | 1.0756 (SI few-shot) | AFM 1.1097 | Table 1 |
| Beauty rating pred | MAE | — | 0.6892 (SI few-shot) | AFM 0.8474 | Table 1 |
| Beauty direct rec | HR@5 | 5 | 0.0915 (SI few-shot) | ENMF 0.1537 | Table 2 — **thua** |
| Beauty direct rec | HR@10 | 10 | 0.1559 (SI few-shot) | P5 0.2159 | Table 2 — thua |
| Beauty direct rec | NDCG@10 | 10 | 0.1063 (SI few-shot) | P5 0.1289 | Table 2 — thua |
| Yelp direct rec | HR@10 | 10 | 0.2451 (SI few-shot) | P5 0.3182 | Table 2 — thua |
| Beauty sequential | HR@5/10, NDCG@5/10 | — | RecMind variants ~0.03–0.06 | P5 tốt hơn hầu hết | Table 3; paper: "fully-trained models such as P5 usually perform better" |
| Explanation/summarization | BLEU-n, ROUGE-n | — | `chưa xác minh` giá trị | — | §4.3–4.4 |

**5. Điểm đáng mượn.** Ý tưởng Self-Inspiring (xem lại các nhánh reasoning đã explore trước khi plan) — tinh thần giống reflect/replan của project; pattern "DB tool = SQL trên bảng interaction+metadata" giống LookupTool/FilterTool; web-search tool cho real-time info.

**6. Hạn chế / cờ kiểm tra.** Repo rỗng → không đối chiếu code được. Kết quả direct/seq rec **thua model trained** — paper tự giải thích bằng positional bias trên pool 100 và context length. Rating prediction "thắng" MF/MLP/AFM nhưng thua/hòa P5 tùy variant — cần đọc kỹ bảng. Amazon version 2018, không phải 2023.

---

### RAH — Type 1 — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "RAH! RecSys-Assistant-Human: A Human-Centered Recommendation Framework with LLM Agents", Yubo Shu và cộng sự, arXiv 2308.09904; bản ACM (IEEE TCSS 2024 theo citation trong AgentCF++) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/TheRepoForRAH/RAH — có code (clone thành công, ~code Python gọi OpenAI API) |
| Backbone LLM / embedding | GPT-4-0613 cho tất cả experiments |

**1. Vấn đề và đóng góp.** Đặt LLM-assistant vào giữa user và recommender system: assistant học "personality" (likes/dislikes) của user qua Learn-Act-Critic loop + reflection, rồi đóng vai proxy user tạo feedback để (a) giảm user burden/cold-start, (b) giảm popularity bias, (c) tăng user control/privacy.

**2. Kiến trúc chi tiết.**
- 5 agents: **Perceive** (diễn giải item features + user feedback), **Learn** (trích likes/dislikes từ interaction, trả lời "why might some like/dislike"), **Act** (dự đoán action Like/Dislike cho item mới dựa trên personality, CoT 4 bước), **Critic** (so prediction vs ground truth, phân tích lý do sai + gợi ý sửa → Learn học lại), **Reflect** (định kỳ rà soát personality library: merge duplicates, tách conflicts).
- Learn-Act-Critic loop: Learn sinh candidate personality → Act dự đoán ngược action của user → Critic chấm → sai thì feedback cho Learn → lặp tới khi khớp.
- Reflection mechanism: sau mỗi đợt học, Reflect agent merge/split/resolve conflicts trong preference & dispreference lists.
- Assistant "act" thay user trên các RS khác nhau: proxy feedback (like/dislike/comment) được đưa vào RS để fine-tune/rerank — RAH không tự recommend mà **điều khiển RS bên dưới**.
- Không có retrieval/ranking tool riêng; item info lấy qua Perceive.

**3. Dữ liệu.** Amazon Reviews (Ni et al. 2019 → **2018**): Movies, Books, Video Games. Filter ≥5 interactions; giữ user cross-domain; chia 2 tập **Cross1k** (1,045 users/domain-ish, Tables 3) và **Cross221k** (221,861 Movie users / 94,407 Book / 7,149 Game — Table 4). Proxy set cho eval. `chưa xác minh` chi tiết split train/test.

**4. Metric và kết quả.** Không eval top-k của chính agent; đo **cải thiện downstream RS** sau khi thêm proxy feedback (Table 5, NDCG@10 / Recall@10, 7 RS × 4 domains Movie/Book/Game/Mixed). Ví dụ:

| Dataset | RS | NDCG@10 base → +Assistant | Recall@10 base → +Assistant |
|---|---|---|---|
| Movie | LightGCN | 0.5202 → 0.5524 (+0.0322) | 0.5341 → (xem bảng; Recall cột theo cặp) |
| Book | ItemKNN | 0.0694 → 0.1171 (+0.0477) | — |
| Game | NeuMF | 0.2704 → 0.4086 Recall (+0.1382) | — |

(Lưu ý: Table 5 dump theo cặp NDCG/Recall trên mỗi dòng method×domain — các giá trị trên trích từ dump; một số ô `chưa xác minh` do text 2 cột.) Tác giả tự thừa nhận: **random-assistant cũng cải thiện hầu hết experiments** → rủi ro data distribution leakage (Table 5 có dòng "-Random").

**5. Điểm đáng mượn.** Pattern "agent học personality tường minh (likes/dislikes lists) rồi act thay user" — gần với user-profile memory của project; Critic phân tích *lý do* sai chứ không chỉ "sai" (giàu tín hiệu hơn reward scalar); ý tưởng proxy feedback để augment training data.

**6. Hạn chế / cờ kiểm tra.** Không có top-k eval chuẩn → khó so sánh trực tiếp; self-reported leakage; repo code cần OpenAI API; chưa đọc sâu toàn bộ code (chỉ xác nhận tồn tại + mô tả theo README/paper).

---

### BiLLP — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "Large Language Models are Learnable Planners for Long-Term Recommendation", Wentao Shi, Xiangnan He và cộng sự, SIGIR 2024 (tr. 1893–1903); arXiv 2403.00843 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/jizhi-zhang/BiLLP — fork FireAct, **code thật** (~agent env + training). Phân tích code chi tiết ở `cloned_repos/docs/REPORT.md` §3.4 |
| Backbone LLM / embedding | LLM planner (OpenAI API hoặc local LLaMA); grounding = LLaMA embedding nearest-neighbor trên catalog |

**1. Vấn đề và đóng góp.** Biến LLM thành **learnable planner** cho long-term/interactive recommendation: agent sinh ReAct trajectory `recommend[item]` qua nhiều round trong môi trường mô phỏng user, được train bằng A2C với macro/micro reflection.

**2. Kiến trúc chi tiết.** (Chi tiết code: docs/REPORT.md §3.4)
- Mỗi step: LLM xuất `Thought / Action N: recommend[item]` → **grounding model** map item (kể cả bịa) sang item thật gần nhất bằng cosine trên LLaMA embedding → env trả reward + Observation → lặp tới Max_Iteration=50.
- Memory: reflection store trên FAISS (OpenAI embeddings); agent variants: agent_reflexion, agent_retrival (Q-table+FAISS), agent_revise, agent_a2c (chính).
- Reward: `reward_mat` (user×item) + distance penalty khi item quá giống k item history gần nhất (`whether_to_leave` phạt −1000).
- Không có candidate pool — "retrieval" là embedding-NN grounding trên toàn catalog.

**3. Dữ liệu.** Steam (games, rating=5 nếu chơi >3h else 2; filter ≥5) + **Amazon-Book** (amazon_v2 ~2014; title+genre; filter ≥**90** interactions → subset rất đặc). Train/test environments tách biệt mô phỏng online; target items sampled.

**4. Metric và kết quả** (Table 3, trung bình ± std; Len=trajectory length, Reach=avg reward/round, Rtraj=cumulative reward — **không phải top-k**):

| Dataset | Method | Len | Reach | Rtraj |
|---|---|---|---|---|
| Amazon | BiLLP | 9.413±0.190 | 4.507±0.012 | **42.443±0.817** |
| Amazon | Reflexion | 8.700±0.535 | 4.670±0.073 | 40.670±2.954 |
| Amazon | ReAct | 7.733±0.450 | 4.603±0.033 | 35.603±1.806 |
| Amazon | CQL (RL baseline tốt nhất) | 2.280±0.185 | 4.497±0.039 | 21.907±0.299 |
| Steam | BiLLP | 15.367±0.119 | 4.503±0.069 | **69.193±1.590** |
| Steam | Reflexion | 12.690±1.976 | 4.523±0.026 | 57.423±8.734 |

(Nguồn: Table 3. Lưu ý Reach của BiLLP không cao nhất — DQN 4.500/CQL 4.497 tương đương; điểm mạnh là Len+Rtraj.)

**5. Điểm đáng mượn.** **Grounding-by-embedding cho item bịa**: map output LLM → nearest real item + Observation báo lại cho LLM ("can not be recommended, instead recommend[X]") — trực tiếp chống hallucinated item; distance-penalty chống lặp item; tách train/test environment mô phỏng drift.

**6. Hạn chế / cờ kiểm tra.** Metric custom (Len/Reach/Rtraj) không chuẩn top-k → không so được với project; Amazon subset ≥90 interactions cực kỳ dense, không đại diện; paper không nêu rõ LLM backbone size trong phần đọc được (`chưa xác minh` — repo cho phép cả GPT lẫn local LLaMA); env-based sequential rec khác bài toán single-request.

---

### InteRecAgent — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "Recommender AI Agent: Integrating Large Language Models for Interactive Recommendations", Xu Huang, Jianxun Lian, Yuxuan Lei, Jing Yao, Defu Lian, Xing Xie; arXiv 2308.16505 (2023/2024) |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo (microsoft/RecAI) + Amazon |
| Repo | github.com/microsoft/RecAI → `InteRecAgent/` subdir — code thật ~6k dòng (`llm4crs/`). Phân tích code chi tiết: docs/REPORT.md §3.7 + §4 |
| Backbone LLM / embedding | GPT-4 (brain); tools: SQLite/pandasql, ItemCF `.npy`, SASRec-no-pos-emb ranking; sentence-transformers + ChromaDB cho dynamic demos |

**1. Vấn đề và đóng góp.** LLM-agent điều khiển **expert recommender tools** (SQL query, hard/soft filter, ranking model) qua plan-first execution + Candidate Bus + Critic/rechain — tách "hiểu intent" (LLM) khỏi "rank" (model truyền thống).

**2. Kiến trúc chi tiết.** (Chi tiết đầy đủ docs/REPORT.md §4 — tóm tắt)
- Plan-first: LLM xuất 1 lần `Action: ToolExecutor` + JSON plan `[{tool_name, input}]`; ToolBox chạy tuần tự (2 API calls thay vì N+1 của ReAct), chỉ LookUp/Map output trả lại LLM.
- Tools: **LookUpTool** (SQL tự do trên item table, token-budget truncation), **HardFilterTool** (SQL do LLM viết + `rewrite_sql` grounding: ép bảng, fuzzy-match cột, canonical hóa giá trị categorical), **SoftFilterTool** (seed item titles → item-sim matrix, giữ top có score > ngưỡng = top-rec_num toàn catalog), **RankingTool** (RecModelTool: schema popularity/similarity/preference; `unwanted` → mask điểm −100000), **MapTool** (format output), Memory init tool.
- Candidate Bus: list item IDs + mảng similarity song song (chỉ SimilarItemTool ghi, RecModelTool đọc schema "similarity"); buffer rỗng → tool trả "0 eligible items, stop".
- Critic: LLM judge đọc conversation + tool-track → "Yes"/"No + advice"; rechain ≤3 lần, chèn reflection vào prompt.
- Item table `info()` inject schema+dtypes+ranges+sampled categorical values vào prompt.

**3. Dữ liệu.** LOO split; tools train trên train+val. 3 datasets: **Steam**, **MovieLens-10M**, **Amazon Beauty** (link amazon_v2 → bản cũ ~2014; footnote http://jmcauley.ucsd.edu/data/amazon/links.html). Eval: 1000 instances user-simulator, 500 one-turn, 100 lifelong (LONG-CHAT ≤50 turns / LONG-CONTEXT). Candidate: hard filter cap 1000; soft filter top 5%; ranking pool 20 (1 pos + 19 neg) cho N@20.

**4. Metric và kết quả** (Tables 2,3,5 — nguồn 2308.16505.txt):

| Task / Dataset | Metric | k | InteRecAgent | Baseline mạnh nhất | Ghi chú |
|---|---|---|---|---|---|
| Session-wise sim | Hit@5 | 5 | Steam 0.87, MovieLens 0.85, Beauty 0.54 | GPT-4: 0.78 / 0.79 / 0.15 | Table 2; Beauty gap lớn nhất |
| Session-wise sim | AT@5 | — | Steam 2.86, Movie 3.15, Beauty 3.99 | GPT-4: 3.34 / 3.70 / 5.59 | Table 2 |
| One-turn retrieval | Recall@5 | 5 | Steam 65.05, Movie 52.02, Beauty 30.28 (% ) | GPT-4: 56.77 / 47.78 / 12.80 | Table 5 — **full catalog** |
| One-turn ranking | NDCG@20 | 20 | Steam 60.28, Movie 63.86, Beauty 40.05 | GPT-4: 57.29 / 55.78 / 33.28 | Table 5; pool=20 |
| Lifelong +LT Mem | Hit@50 | 50 | cải thiện trên mọi dataset | GPT-4 base | Tables 3–4 |

**5. Điểm đáng mượn.** Rất nhiều — xem bảng ánh xạ docs/REPORT.md §C.8 và §4 dưới. Ngắn gọn: plan-first 2-API-call; hard/soft filter tách; grounding layer (fuzzy cột/giá trị/title→id); `info()` inject schema+giá trị categorical hợp lệ; Critic đọc tool-track; `unwanted` mask điểm thay vì xoá ID; popularity/visited_num ranking không cần model.

**6. Hạn chế / cờ kiểm tra.** Multi-turn simulator (user giấu target) khác bài toán single-request; Amazon Beauty dùng bản cũ; ranking eval chỉ pool 20; RecModelTool bắt buộc checkpoint unirec-format kể cả khi chỉ dùng popularity (docs §C.6); code dính LangChain + pandasql + OpenAI — nặng để port.

---

### Tool-Rec — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "Let Me Do It For You: Towards LLM-Empowered Recommendation via Tool Learning", Yuyue Zhao và cộng sự, SIGIR '24 (Washington DC), arXiv 2405.15114 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/Go0day/ToolRec-Code — clone `cloned_repos/ToolRec/` (~76MB, kèm recbole fork + dataset). Code thật; cần OpenAI API key cho ChatGPT; recbole tools cần train |
| Backbone LLM / embedding | gpt-3.5-turbo-16k (ChatGPT); attribute tools trên SASRec/BERT4Rec + GloVe word embeddings |

**1. Vấn đề và đóng góp.** LLM đóng vai **surrogate user**: mô phỏng quá trình user khám phá sở thích qua nhiều round, gọi attribute-oriented tools (retrieval + rank) để thu hẹp item pool, tối đa 8 rounds.

**2. Kiến trúc chi tiết.**
- User decision simulation: CoT prompting — LLM nhận observation → thought → action `T[attribute, $]` (chọn attribute + số item) → tool trả kết quả → lặp; dừng khi "satisfied" → xuất final item set.
- **Attribute-oriented retrieval tools**: sequential model (SASRec/BERT4Rec pretrained) + attribute-specific encoder fine-tune trên attribute sequence của user (price, sales rank, genre, year...); đóng băng backbone, chỉ train attr encoder.
- **Attribute-oriented rank tools**: LLM rank candidate items theo attribute pattern + user history (zero/few-shot instruction).
- Memory strategy: validate item do tool trả về có trong item-pool directory; sai → re-run tool kèm chi tiết sai; ghi item + tool annotation để các call sau dùng.
- Retrieval score KHÔNG truyền trực tiếp cho LLM ranker — LLM đọc item list + attribute; không có fusion điểm số.

**3. Dữ liệu.** ML-1M (genre+year), **Amazon-Book** (Amazon.com, category Book, attributes = Price + Sales rank, **10-core**, ni-jianmo link → bản **2014**), Yelp2018 (categories/city/stars, 10-core). LOO theo timestamp; tools train trên train+val; test = **200 users sampled × 3 trials** (trung bình ± std). Metrics Recall@10/NDCG@10. `chưa xác minh` tổng số user/item sau lọc (Table 1 stats có trong paper nhưng dump chưa đọc đủ).

**4. Metric và kết quả** (Table 2, mean±std):

| Dataset | Method | Recall@10 | NDCG@10 |
|---|---|---|---|
| Amazon-Book | ToolRec (SASRec-tools) | 0.053±0.013 | 0.0259±0.005 |
| Amazon-Book | ToolRec (BERT4Rec-tools) | 0.043±0.013 | 0.0223±0.008 |
| Amazon-Book | LLMRank (baseline mạnh nhất recall) | 0.047±0.013 | 0.0246±0.004 |
| Amazon-Book | SASRec | 0.045±0.023 | 0.0233±0.012 |
| Amazon-Book | P5 | 0.006±0.003 | 0.0026±0.002 |
| ML-1M | ToolRec | 0.215±0.044 | 0.1171±0.018 (vs SASRec 0.203/0.1017) |
| Yelp2018 | ToolRec | 0.028±0.003 | 0.0159±0.001 (**thua** SASRec 0.033/0.0218) |

Paper báo improvement row: ML-1M +3.36%/+15.10% (Recall/NDCG?), Amazon-Book +14.28%/+5.14%, Yelp **−29.16%/−27.32%** (thua rõ). `chưa xác minh` mapping chính xác cột improvement.

**5. Điểm đáng mượn.** (a) Validation "item tồn tại trong catalog directory" trước khi chấp nhận tool output — chống hallucinated item ở mức tool; (b) attribute-oriented tools = cách biến filter thành "attribute pattern" có model support; (c) memory ghi tool-annotation cho từng candidate (provenance); (d) surrogate-user CoT simulation để explore — ý tưởng giống user-simulator eval.

**6. Hạn chế / cờ kiểm tra.** Eval chỉ 200 users ×3 — sample nhỏ; Amazon-Book bản 2014 10-core; "full catalog" claim cần kiểm chứng (tools trả subset theo attribute — thực tế là exploration có giới hạn, không phải rank toàn catalog); Yelp cho thấy LLM-agent **thua rõ** ở domain LLM không rành; repo kèm recbole → nặng.

---

### AgentCF++ — Type 1 — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "AgentCF++: Memory-enhanced LLM-based Agents for Popularity-aware Cross-domain Recommendations", Jiahao Liu và cộng sự, SIGIR '25 (Padua), DOI 10.1145/3726302.3730161 |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/jhliu0807/AgentCF-plus → `cloned_repos/AgentCFpp/` (~4.2MB, code thật). LLM backbone: `chưa xác minh` trong phần đọc được (paper nhấn "minimize API call expenses" → nhiều khả năng GPT-series; repo config chưa đọc kỹ) |
| Backbone LLM / embedding | LLM-based user+item agents (paper kế thừa AgentCF); `chưa xác minh` model cụ thể |

**1. Vấn đề và đóng vấn đề.** Nâng cấp AgentCF: dual-layer memory (domain-separated + domain-fused với two-step fusion kiểu attention) + interest groups & group-shared memory để mô phỏng popularity effect trong cross-domain user-behavior simulation.

**2. Kiến trúc chi tiết.**
- User agents + item agents tự interact, so action với real data, update memory bằng reflection (kế thừa AgentCF).
- Memory update 3 bước: (1) user agent update domain-separated memory theo domain; (2) **two-step fusion**: extract preferences liên quan target domain từ các domain khác → integrate vào domain-fused memory; (3) item agents update item memory từ domain-fused memory của user.
- Interest groups: user chia nhóm theo interest (không phải full history); group-shared memory truyền popularity effect chỉ trong nhóm → tránh lan sang user không liên quan.
- Không phải recommender trực tiếp — là framework **mô phỏng user để cải thiện RS**.

**3. Dữ liệu.** Amazon review dataset (Ni et al. 2010 → **2014**): Books, CDs&Vinyl, Movies, Video Games. Cross-1…Cross-5 = tổ hợp 3–4 domains; rating ≥4; timestamps Oct 2021–Mar 2022; chỉ user multi-domain & ≥10 interactions; **random sample 100 users**; split 8:1:1 theo thời gian.

**4. Metric và kết quả** (Table 1 — chỉ MRR trong paper; NDCG "available in repository"; pool = 1 target + 9 random same-domain negatives = **10 candidates**; avg 5 runs):

| Dataset | BPR-MF | SASRec | LLMRank | AgentCF | **AgentCF++** |
|---|---|---|---|---|---|
| Cross-1 | 0.2949 | 0.3463 | 0.3268 | 0.3284 | **0.3488** |
| Cross-2 | 0.2959 | **0.3154** | 0.2730 | 0.2681 | 0.2777 ⚠ |
| Cross-3 | 0.3114 | 0.3828 | 0.3106 | 0.3114 | **0.3989** |
| Cross-4 | 0.3012 | 0.3118 | 0.2970 | 0.3032 | **0.3147** |
| Cross-5 | 0.3127 | 0.3687 | 0.3308 | 0.3480 | **0.3837** |

⚠ Cross-2: AgentCF++ (0.2777) **thua SASRec (0.3154)** và chỉ hơn LLMRank nhẹ — claim "consistently outperforms all baselines" không đúng tuyệt đối.

**5. Điểm đáng mượn.** Dual-layer memory tách domain-specific vs fused — ý tưởng nếu project mở rộng multi-category Amazon; "extract relevant preferences trước khi fuse" giống attention-gating; group-shared memory cho popularity/context effect.

**6. Hạn chế / cờ kiểm tra.** Chỉ 100 users → kết quả noise cao (5-run avg nhưng user sample nhỏ); MRR-only trong paper; không phải rec agent end-to-end; LLM backbone không nêu rõ trong phần đọc được.

---

### ItemRAG — Type 1 — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "ItemRAG: Item-based Retrieval-Augmented Generation for LLM-based Recommendation" (title trong repo: "ItemRAG - Retrieval-Augmented Recommendation with Item-Side Knowledge"), KSWoo và cộng sự; arXiv/SIGIR'26 short (venue `chưa xác minh` chính xác) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/kswoo97/ItemRAG → `cloned_repos/ItemRAG/` — code thật, 4 bước offline (xem docs/REPORT.md §3.3) |
| Backbone LLM / embedding | GPT-4.1-mini (LLM ranker); gte-large-en-v1.5 (item title embeddings) |

**1. Vấn đề và đóng góp.** Đổi hướng RAG: thay vì retrieve purchase-history của user tương tự (user-based, noisy), retrieve **item-level** — với mỗi item trong history/candidate set, augment mô tả bằng items liên quan qua **co-purchase + semantic similarity** kết hợp.

**2. Kiến trúc chi tiết.** (Offline pipeline — docs §3.3)
- Step1: embed title toàn catalog (gte-large-en-v1.5) → top-5 similar items mỗi item.
- Step2: per user — co-purchase pairs + mở rộng qua semantic neighbors của K=5 similar items, đếm frequency, sample K=50.
- Step3: GPT-4.1-nano tóm tắt co-purchase neighborhood thành text per item ("item-side enrichment").
- Step4: LLM rank **10 candidates** (1 target + 9 random) kèm title + summary.
- Không query-time retrieval — mọi thứ precompute per user; không có score truyền cho LLM (chỉ frequency ngầm trong context).

**3. Dữ liệu.** **"latest Amazon Reviews dataset"** (citation [3] `chưa xác minh` số hiệu — nhiều khả năng 2023): Sports&Outdoors, Toys&Games, Beauty&PersonalCare, ArtsCrafts&Sewing — khớp xlsx. LOO (last purchase held out); 1000 users eval; 3 runs; Wilcoxon test; cold-start variant (remove target item khỏi train+retrieval DB).

**4. Metric và kết quả** (Table 1, ×100; H@K/N@K trên pool 10):

| Dataset | ItemRAG H@1 | Best LLM baseline H@1 | Best overall baseline H@1 |
|---|---|---|---|
| Beauty | **49.1** | CoRAL ~48.5* | LightGCN++ 38.3 |
| Toys | **49.5** | CoRAL ~52.4? | LightGCN 40.9 |
| Sports | **51.6** | — | LightGCN 45.3 |
| Arts&Crafts | **57.8** | — | LightGCN++ 53.0 |

(*mapping baseline rows bị jumbled trong text dump — `chưa xác minh` từng baseline H@1; kết luận chắc: ItemRAG best trong 18/20 settings, +11% H@1 Toys vs CoRAL, +42% H@1 Beauty vs zero-shot LLM.) Table 2: cold-start ItemRAG thắng mọi case (`chưa xác minh` số).

**5. Điểm đáng mượn.** **Item-side knowledge enrichment**: tóm tắt neighborhood (co-purchase + semantic) thành đoạn text gắn vào item — trực tiếp áp dụng cho LookupTool/SearchTool metadata của project; kết hợp CF signal + semantic cho retrieval; cold-start robustness.

**6. Hạn chế / cờ kiểm tra.** Eval pool=10 quá nhỏ so với full catalog; toàn bộ pipeline offline per-user → chi phí precompute lớn khi scale; "latest Amazon Reviews" chưa xác nhận version; không có online latency analysis trong phần đọc được (có trong appendix).

---

### iAgent — Type 1 — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "iAgent: LLM Agent as a Shield between User and Recommender Systems", Wujiang Xu và cộng sự, ACL 2025 Findings; arXiv 2502.14662 |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/agiresearch/iAgent → `cloned_repos/iAgent/` — code thật (`main_iagent_mp.py` + `model.py` ~700 dòng). Cần OPENAI_API_KEY + dataset InstructRec |
| Backbone LLM / embedding | OpenAI LLM (GPT-series; `chưa xác minh` exact model trong paper); structured output qua OpenAI json_schema strict |

**1. Vấn đề và đóng góp.** LLM agent "shield" giữa user instruction và RS: hiểu instruction tự do → distill "knowledge" → re-rank candidate list; i²Agent thêm profile từ pos/neg sample + tách dynamic_interest/dynamic_profile.

**2. Kiến trúc chi tiết.** (docs §3.1)
- Workflow 2 LLM calls: (a) sinh knowledge string mô tả loại item phù hợp; (b) re-rank `rerank_list: int[]` theo json_schema strict.
- **Không retrieval** — dùng `ranked_lists` precomputed trong dataset pkl.
- LLM là ranker duy nhất; chỉ thứ tự id, không điểm số.
- Lỗi: parse fail → retry 3 lần; MRR=−1 → retry với hint; hallucinated id không bị chặn (metric −1 → retry).

**3. Dữ liệu.** InstructRec benchmarks: **Amazon Book**, Amazon Movietv, Goodreads, Yelp (paper Table 3; xlsx chỉ ghi Books — đúng nhưng thiếu 3 domain kia). Held-out last item; `chưa xác minh` cỡ candidate list (InstructRec cung cấp ranked list — không rõ độ dài, có thể toàn catalog top-N).

**4. Metric và kết quả** (Table 2/3, %):

| Dataset | Model | HR@1 | HR@3 | NDCG@3 | MRR |
|---|---|---|---|---|---|
| Amazon Book | i2Agent | **35.11** | 53.51 | 45.64 | 50.28 |
| Amazon Book | iAgent | 31.89 | 48.99 | 41.69 | 47.23 |
| Amazon Book | AgentCF | 14.24 | 34.16 | 25.55 | 32.77 |
| Amazon Book | BGE-Rerank | 25.36 | 45.90 | 37.11 | 42.84 |
| Amazon Movietv | i2Agent | **46.43** | 65.77 | 57.67 | 60.43 |
| Amazon Movietv | iAgent | 38.19 | 56.87 | 48.93 | 53.04 |
| Goodreads/Yelp | i2Agent > iAgent > baselines | `chưa xác minh` từng số | | | |

(Nguồn: iagent_tbl.txt — dump từ paper HTML/PDF.)

**5. Điểm đáng mượn.** Pattern 2-call "distill knowledge (free-text) → re-rank với strict json_schema" + retry-loop khi output vi phạm; i²Agent tách static/dynamic profile — gần tinh thần session constraints của project.

**6. Hạn chế / cờ kiểm tra.** Không retrieval → không đánh giá được khả năng tìm item trong catalog; code có `if i > 1: break` đáng ngờ giới hạn eval (docs §5); candidate list nguồn ngoài repo.

---

### ECPO — Type 1 — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "Expectation Confirmation Preference Optimization for Multi-Turn Conversational Recommendation Agent", Xueyang Feng và cộng sự, arXiv 2506.14302v1 (17 Jun 2025) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/XueyangFeng/ECPO → `cloned_repos/ECPO/` (~104MB: crs/tools, user_simulator/AILO, backward/, config/, LLaMA-Factory). Cần OpenAI-like API + GPU cho LLaMA-Factory DPO |
| Backbone LLM / embedding | CRA backbone **Llama-3.1-8B-Instruct** (SFT+DPO); GPT-4o mini làm reference/expert; user simulator + persona gen = GPT-4o |

**1. Vấn đề và đóng góp.** Multi-turn conversational RA: thay vì ước lượng reward sau khi xong cả hội thoại (trajectory-level MTPO), ECPO dùng **Expectation Confirmation Theory** — mỗi turn chấm satisfaction (flexibility/coherence/user-guidance, max 5) → turn không đạt thì "backward expectation derivation" sinh rewritten response → DPO trên turn-level preference pairs. Kèm simulator mới **AILO** (Activities/Interests/Language/Orientations personas từ review thật).

**2. Kiến trúc chi tiết.**
- CRA (ActCRS): 1 call sinh strategy + response mỗi turn; tool = retrieval queries (M ≤ N).
- Training: simulation-guided SFT (GPT-4o-mini CRA + AILO user → Dsft ~1000 tasks/dataset) → ECPO: EC scoring (LLM đóng user monologue) → Rewriter (slow-thinking) sinh p̃ → DPO với explanation CONF_t.
- AILO: persona 4 chiều infer từ review datasets bằng GPT-4o; diversity đo bằng max ROUGE-L giữa personas.
- `#Calls` = O(M+N) — hiệu quả hơn MACRS O(M+4N).

**3. Dữ liệu.** **AmazonReviews2023** (github.com/hyp1231/AmazonReviews2023 — footnote 2): Amazon-Game + Amazon-Book; +Yelp. ~3000 tasks/dataset → 1000 SFT + 500 DPO-pre + **100 test tasks**. Target = ground-truth item mỗi user (iEvalLM setting).

**4. Metric và kết quả** (Table 1: SR=Success Rate, R=Recall Rate, WR=Win Rate vs expert CRA):

| Dataset | Method | SR | R | WR |
|---|---|---|---|---|
| Book | Llama-3.1 ActCRS+ECPO | 0.56 | 0.58 | 0.57 |
| Book | GPT-4o mini ActCRS | 0.53 | 0.56 | 0.50 |
| Game | Llama-3.1 ActCRS+ECPO | 0.41 | 0.61 | 0.56 |
| Game | GPT-4o mini ActCRS | 0.43 | 0.68 | 0.50 |
| Yelp | Llama-3.1 ActCRS+ECPO | 0.45 | 0.47 | 0.63 |
| Yelp | GPT-4o mini ActCRS | 0.37 | 0.43 | 0.50 |

(Nguồn: Table 1. Llama+ECPO thắng WR rõ (0.56–0.63 vs ≤0.50); SR/R ngang GPT-4o mini.)

**5. Điểm đáng mượn.** Turn-level preference construction **không cần self-sampling** — EC process chấm từng turn + natural-language reason (CONF_t) → DPO; AILO persona-from-reviews; "rewrite unsatisfactory response" như một dạng critique-targeted regeneration.

**6. Hạn chế / cờ kiểm tra.** Multi-turn CRA khác single-request; SR/R định nghĩa theo simulator (ground-truth item ẩn) — chưa xác minh công thức chính xác; chỉ 100 test tasks/dataset; repo cần LLaMA-Factory + GPU.

---

### T-PRA — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "Tunable LLM-based Proactive Recommendation Agent", ACL 2025 (long); arXiv/ACL Anthology 2025.acl-long.944 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/gnaWeinrE/T-PRA → `cloned_repos/T-PRA/` — code thật (FireAct fork; agent+grounding = LLaMA-3.1-8B local). Nặng nhất: cần GPU + LLaMA-Factory + dataset zip ngoài |
| Backbone LLM / embedding | LLaMA-3.1-8B-instruct (agent + item grounding embedder) |

**1. Vấn đề và đóng góp.** Proactive sequential recommendation: LLM agent đề xuất dãy item dẫn user tới **target item ẩn** trong môi trường mô phỏng; tune bằng DPO trên trajectory với rule-based reward (preference + step-length + forward-length) + Critic.

**2. Kiến trúc chi tiết.** (docs §3.5)
- ReAct loop `recommend[item]`; grounding = LLaMA embed "The type of {item} is" → cosine tới `task_embedding` precomputed → nearest item không thuộc history.
- Vòng đời: generate trajectories → `combine.py` → `mlp.py` sinh preference pairs → `llamafactory-cli train --stage dpo` → lặp 3 vòng → eval.
- Critic module chấm action; reward nhiều thành phần.

**3. Dữ liệu.** Steam (190,365 users × 6,012 games; seq ≥20 → 18,523 sequences) + **Amazon-Book** (3,109 users × 13,864 books → 3,374 sequences; amazon_v2 → ~2014). Target item = random item trong dataset; split 80/20.

**4. Metric và kết quả** (Table 1: Acce=accuracy tới target?, IoR, Coh — **không phải top-k**; giá trị Amazon-book rải 0.42–0.65 Acce qua các DPO rounds — `chưa xác minh` mapping cột chính xác do dump jumbled):

| Dataset | Quan sát chính |
|---|---|
| Amazon-Book | Acce ~0.42–0.65 tùy method/round; T-PRA DPO cải thiện dần qua vòng (`chưa xác minh` số từng vòng) |
| Steam | Acce 0.38–0.65; Len/Reach-style metrics tương tự BiLLP |

**5. Điểm đáng mượn.** Grounding-by-embedding (như BiLLP nhưng cùng 1 LLM local); vòng đời trajectory→DPO nếu project muốn fine-tune planner; multi-component reward shaping.

**6. Hạn chế / cờ kiểm tra.** Env-based sequential khác bài toán; metric custom; cần GPU + LLaMA-Factory; paper table parse khó → nhiều số `chưa xác minh`.

---

### MemRec — Type 2 single — Tier A

| Trường | Giá trị |
|---|---|
| Paper | "MemRec: Collaborative Memory-Augmented Agentic Recommender System", ACL 2026 (theo docs/REPORT.md); arXiv txt trong investigations |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo + Amazon |
| Repo | github.com/rutgerswiselab/memrec → `cloned_repos/memrec/` — code thật (`src/models/memrec_agent.py`, `reranker_llm.py`, `manager.py`). Cần LLM API (Azure/vLLM) + PyTorch |
| Backbone LLM / embedding | gpt-4o-mini (LLMRec + LMMem); variants: Standard/Cloud-OSS (open-weights Azure), Vector reranker, Local Qwen-2.5-7B |

**1. Vấn đề và đóng góp.** Tách "quản lý memory" khỏi "reasoning/ranking": LMMem duy trì collaborative memory graph + sinh domain-adaptive curation rules; Stage-R trích facets từ memory; Stage-ReRank chấm candidates; Stage-W write-back. Curate-then-synthesize context.

**2. Kiến trúc chi tiết.** (docs §3.2)
- `rerank()`: pruner chọn top-k láng giềng (mix_min_users/items) → packer nén context theo token budget → `manager.run_stage_r` (facet extraction, JSON schema, có confidence + supporting_neighbors) → `reranker.rerank` chấm điểm từng candidate → sort desc.
- LLMRec reranker nhận instruction + "User Profile"/"User's Current Request" string; VectorReranker thay LLM bằng vector similarity (sub-ms latency).
- Memory graph: user-item collaborative graph, neighbor propagation Stage-W; curation rules do LMMem tự sinh per-domain (vd Books: content similarity boost 2.5x nếu metadata_overlap>0.6, CF 1.8x nếu co_interaction>3).
- Không retrieve từ catalog — candidates do caller truyền (eval: N=10).

**3. Dữ liệu.** InstructRec splits (cùng Xu et al. 2025b): **Amazon Books**, Amazon Goodreads, MovieTV, Yelp — `chưa xác minh` Amazon version (InstructRec pipeline; nhiều khả năng 2023 nhưng chưa trích citation). k=16 neighbors, Nf=7 facets, N=10 candidates; 1000-user subset cho analysis; warmup rounds mô phỏng memory trước test.

**4. Metric và kết quả** (Tables 2–3: H@1/3/5, NDCG@1/3/5, ×100? — `chưa xác minh` scale; relative gains có trong text):

| Dataset | Metric | MemRec vs best baseline |
|---|---|---|
| Goodreads | H@1 | **+28.98%** vs i2Agent (SOTA) |
| Yelp | H@1 / N@5 | +15.77% / +7.59% |
| Books | H@1 | +34% vs Naive Agent (single-stage) — Figure 6 |
| Books/Goodreads/MovieTV/Yelp | H@K, N@K | "SOTA across all reported metrics", p<0.05 |

(Nguồn: §Experiments + Tables 2–3. Số tuyệt đối `chưa xác minh` do table dump chưa parse.)

**5. Điểm đáng mượn.** Facets có **provenance** (confidence + supporting_neighbors) — hữu ích nếu distill của project cần giải thích; tách memory-management LLM khỏi ranking LLM → có thể thay ranker bằng vector search (sub-ms) — pattern "cheap path + LLM path"; domain-adaptive curation rules tự sinh.

**6. Hạn chế / cờ kiểm tra.:** Phức tạp nhất trong các repo đã đọc (graph + 2 LLM stages + write-back); eval pool=10; cần LLM API cho cả offline lẫn online; memory warmup có thể leak nếu không cẩn thận.

---

## 7. Chi tiết từng paper — Tier B

### RecAI (paper toolkit) — Type 2 single — Tier B

| Trường | Giá trị |
|---|---|
| Paper | "RecAI: Leveraging Large Language Models for Next-Generation Recommender Systems", Microsoft Research, 2024, arXiv (trong texts/) |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo (cùng microsoft/RecAI với InteRecAgent) |
| Repo | github.com/microsoft/RecAI — monorepo: InteRecAgent, Knowledge_Plugin, RecLM-emb/gen/uni/eval, RecExplainer |
| Backbone LLM / embedding | GPT-4/GPT-3.5; RecLlama = Llama-7B fine-tuned; RecLM-emb = embedding model fine-tuned cho item retrieval |

**1. Vấn đề và đóng góp.** Toolkit paper mô tả tầm nhìn "next-gen RS với LLM" qua 5 pillars: Recommender AI Agent (InteRecAgent), Recommendation-oriented Language Models (RecLlama, RecLM-emb/gen/uni/eval), Knowledge Plugin (DOKE), RecExplainer, Evaluator. Không phải method paper có eval độc lập.

**2. Kiến trúc chi tiết.** Mô tả khái niệm các pillar; chi tiết implement nằm ở từng sub-project. Điểm đáng chú ý: RecLlama distill tool-execution plans từ GPT-4 → SLM 7B làm "brain" (outperform GPT-3.5-turbo/Text-davinci-003 trong InteRecAgent); RecLM-emb fine-tune cho item retrieval zero-shot; fuzzy matching cho generative rec (item name sai dấu câu vẫn match).

**3. Dữ liệu.** `không nêu` dataset riêng cho toolkit paper — trỏ về các paper con (InteRecAgent: Steam/MovieLens/Beauty; RecLlama data 16,183 samples từ Steam+MovieLens).

**4. Metric và kết quả.** Evaluator module: NDCG + Recall cho 3 chiều đầu (gợi ý item, giải thích, hội thoại?), pairwise comparison cho Explanation & Chit-Chat. `chưa xác minh` số liệu cụ thể — paper là survey/toolkit.

**5. Điểm đáng mượn.** Ý tưởng **distill planner từ GPT-4 → SLM 7B** (RecLlama) nếu project muốn giảm chi phí; fuzzy name-matching cho validation item; RecLM-emb cho semantic item retrieval.

**6. Hạn chế / cờ kiểm tra.** Không có bảng kết quả đầy đủ trong phần đọc được; giá trị thực tế nằm ở các paper con (InteRecAgent đã review riêng).

---

### VibeMus — Type 2 single — Tier B

| Trường | Giá trị |
|---|---|
| Paper | "VibeMus: Proactive Agentic System for Music Personalization", tuteng0915 và cộng sự, 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | repo |
| Repo | github.com/tuteng0915/VibeMus → `cloned_repos/VibeMus/` — code thật (qwen-agent + ACE-Step pipeline + DashScope API; cần GPU + API key) |
| Backbone LLM / embedding | qwen-plus qua DashScope (function calling); judge = LLM rubric |

**1. Vấn đề và đóng góp.** **Không phải recommender** — hệ thống "vibe music": LLM trò chuyện nhiều turn để làm rõ latent preferences (genre, era, story/lyric, vocals, composition) rồi generate/edit nhạc. Proactive clarification mechanism.

**2. Kiến trúc chi tiết.** qwen-agent function calling; tool `param_setter{name: tags|lyrics|title, value}` ghi state; ACE-Step 3.5B sinh nhạc; `edit_song` guard "chưa generate".

**3. Dữ liệu.** ToT (Tip-of-the-Tongue) song-finding dataset — transform request tìm bài hát → yêu cầu sinh nhạc; mỗi request = tập atomic elements thuộc 5 aspects.

**4. Metric và kết quả.** LLM-judge chấm lyrics+tags 0–10 theo rubric; đếm element occurrence theo dialog round (Table 1). Proactive dialog > single-shot, tiệm cận full-intent input. `chưa xác minh` điểm số cụ thể.

**5. Điểm đáng mượn.** Proactive clarification (hỏi làm rõ trước khi hành động) — tương tự `ask_user` escape của project; tool-schema hẹp `param_setter` pattern.

**6. Hạn chế / cờ kiểm tra.** Ngoài phạm vi recsys; eval bằng LLM-judge rubric — không so được với top-k metrics.

---

## 8. Chi tiết từng paper — Tier C

### DRDT — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "DRDT: Dynamic Reflection with Divergent Thinking for LLM-Based Sequential Recommendation", 2023, arXiv (venue `chưa xác minh`) |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | 6 open LLMs: Vicuna-7b/13b-16k, Openchat-7b, Longchat-7b/13b-16k, YarnMistral-7b-128k + GPT-Turbo-3.5; FastChat serve |

**1. Vấn đề và đóng góp.** Reasoning strategy cho sequential rec: retriever-reranker framework — collaborative ICL retriever chọn sequences tương tự làm in-context examples; divergent thinking trừu tượng hóa user preferences theo nhiều "aspects" (genre/actor/...); dynamic reflection (probe→critique→reflect) phân tích preference theo thời gian.

**2. Kiến trúc chi tiết.** Retriever: collaborative signal (co-occurrence patterns) thay vì semantic similarity thuần — chọn in-context examples "hành vi mua tương tự". Reranker: LLM đọc examples + history → sinh aspect-level preference analysis → rank candidates. Không train/fine-tune.

**3. Dữ liệu.** ML-1M + **Amazon Games** + **Amazon Luxury Beauty** ("Amazon Review dataset" — version `chưa xác minh`, nhiều khả năng 2018). 200 users/dataset sampled; **pool = target + 19 random = 20 candidates** (randomize vị trí target chống shortcut).

**4. Metric và kết quả.** Recall@10/20, NDCG@10/20 (Table 2 — số từng ô `chưa xác minh` do dump chưa parse; kết luận định tính chắc): DRDT thắng plain-text/ICL/COT trên mọi dataset×model; Openchat-7b+DRDT vượt GPT-3.5 plain-text trên Recall@10/NDCG@10/NDCG@20; Mistral-7b cải thiện tới **+209.38%** trên Luxury.

**5. Điểm đáng mượn.** Collaborative-retrieval cho in-context examples (chọn demo theo hành vi thay vì similarity); aspect-level preference abstraction chống noise trong raw sequence; dynamic reflection theo thời gian.

**6. Hạn chế / cờ kiểm tra.** Pool 20 nhỏ; LLM-as-reranker trên text items — không đánh giá catalog-scale; version Amazon chưa rõ; venue chưa rõ.

---

### CoRAL — Type 1 — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "CoRAL: Collaborative Retrieval-Augmented Large Language Models Improve Long-tail Recommendation", Junda Wu và cộng sự, arXiv 2403.06447 (2024) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | GPT-4 làm reward model trong RL (DDPG); LLM khác `chưa xác minh` |

**1. Vấn đề và đóng góp.** RL-trained **retrieval policy**: LLM agent học cách retrieve items phù hợp (collaborative signals) cho long-tail recommendation; reward từ GPT-4 đánh giá chất lượng retrieval.

**2. Kiến trúc chi tiết.** Policy = retrieval agent (DDPG); LLM sinh query/retrieve; GPT-4 chấm reward; tập trung long-tail items. `chưa xác minh` chi tiết state/action space (cần đọc sâu hơn — text đã trích nhưng chưa phân tích hết).

**3. Dữ liệu.** 4 Amazon categories (theo xlsx: Appliances, Gift Cards, Software, Prime Pantry — `chưa xác minh` khớp paper; nhiều khả năng Amazon 2018). Long-tail focus.

**4. Metric và kết quả.** AUC, F1 cho long-tail recommendation (theo notes đợt trước). **Không phải top-k** → không so trực tiếp. `chưa xác minh` số liệu cụ thể.

**5. Điểm đáng mượn.** RL-train retrieval policy với LLM-reward — nếu project muốn học filter/retrieval policy; focus long-tail items (Amazon 2023 có nhiều item ít interaction).

**6. Hạn chế / cờ kiểm tra.** Metric không phải top-k; không repo → không kiểm chứng; chi tiết kiến trúc `chưa xác minh` đầy đủ.

---

### CDA4Rec — Type 1 — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "Cloud-Device Collaborative Agents for Sequential Recommendation", 2025 (txt trong texts/) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | LLaMA-3.1-8B (cloud) + model 1B (device) |

**1. Vấn đề và đóng góp.** Cloud-device collaborative: LLM lớn trên cloud + model nhỏ trên device cùng làm sequential recommendation; device-side lọc/rank nhanh, cloud-side reasoning sâu.

**2. Kiến trúc chi tiết.** Hai tầng agent: cloud LLaMA-3.1-8B xử lý complex reasoning; device 1B model xử lý lightweight tasks. `chưa xác minh` chi tiết phân chia trách nhiệm (Table II jumbled trong dump).

**3. Dữ liệu.** 4 datasets gồm **Amazon Sports** + 3 datasets khác (titles `chưa xác minh`). Full-catalog ranking.

**4. Metric và kết quả.** HR@5/10, NDCG@5/10 (Table II — CDA4Rec best on all datasets; số ô Sports `chưa xác minh` do PDF text jumbled). **Full catalog** → cùng nhóm giao thức gần project nhất trong Tier C.

**5. Điểm đáng mượn.** Cloud-device split: ý tưởng "cheap local model lọc trước, LLM reasoning sau" — giống pattern cascade của project; full-catalog eval hiếm có.

**6. Hạn chế / cờ kiểm tra.** Số liệu Table II không parse được tin cậy; Amazon version `chưa xác minh`; không repo.

---

### AKF-Agent — Type 1 — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "Intelligent Agents with Adaptive Knowledge Fusion for Personalized Recommendation", 2025 (txt: "Intelligent Agents with Adaptive Knowledge Fusion for Personalized Recommendation.txt") |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | cột H có Amazon (col I=None — đã xác minh paper có Amazon) |
| Repo | Không có |
| Backbone LLM / embedding | Qwen-72B (`chưa xác minh` — notes đợt trước) |

**1. Vấn đề và đóng góp.** Adaptive knowledge fusion: memory + CoT + knowledge fusion qua 2 stage prerank → ensemble.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: memory mechanism + chain-of-thought + knowledge fusion cho preranking và ensemble stage.

**3. Dữ liệu.** Amazon (categories `chưa xác minh`), Yelp, GoodReads.

**4. Metric và kết quả.** HR@1/3/5. `chưa xác minh` số liệu cụ thể và giao thức pool.

**5. Điểm đáng mượn.** Knowledge fusion đa nguồn cho rerank — ý tưởng chung; cần đọc lại paper nếu muốn chi tiết.

**6. Hạn chế / cờ kiểm tra.** Nhiều trường `chưa xác minh` — paper chưa được phân tích sâu trong đợt này.

---

### OptiRAG-Rec — Type 1 — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "The Efficiency vs. Accuracy Trade-off: Optimizing RAG-Enhanced LLM Recommender Systems Using Multi-Head Early Exit", arXiv 2501.02173v2 (Jun 2026) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | LLM-based CTR model; GCN-based retriever; multi-head early exit |

**1. Vấn đề và đóng góp.** CTR prediction (không phải top-k): GCN retrieval tìm similar users' interactions + LLM xử lý; multi-head early exit để giảm inference cost — accuracy-efficiency trade-off.

**2. Kiến trúc chi tiết.** GCN retriever (graph user-item) lấy similar users' interactions → prompt cho LLM (similar users' interactions + target user history, Table 6–8 prompt examples) → multi-head early exit quyết định dừng sớm khi đủ confident. So với SparseGPT/TinyLLaMA compression.

**3. Dữ liệu.** BookCrossing + **Amazon Beauty, Video Games, Movies&TV — bản 2018** (Ni et al. 2019 citation) + Yelp. ≥3 past interactions filter; ≤15 interactions trước target; binarize rating ≥3; split 8:1:1.

**4. Metric và kết quả** (AUC/LogLoss/RPS — **không phải top-k**): Beauty AUC 96.37, RPS 4.960 với multi-head early exit (vs 94.50/4.680 single-head; vs SparseGPT 92.78); Video Games RPS +28.9% khi combine retrieval+early exit; Movies&TV AUC 98.46. (Nguồn: §Q2/Q5 + Tables 3–5.)

**5. Điểm đáng mượn.** GCN-retriever cho similar-user context (nếu project cần CF signal trong prompt); multi-head early exit = pattern "exit sớm khi đủ tin" cho agent loop.

**6. Hạn chế / cờ kiểm tra.** CTR pointwise khác bài toán top-k ranking; AUC ~96–98 trên binary task — không nói gì về ranking quality; Amazon 2018.

---

### AgenticRAG — Type 1 — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "AgenticRAG: Tool-Augmented Foundation Models for Zero-Shot Explainable Recommender Systems", Peking University, arXiv 2510.02668 (2025) |
| Type theo xlsx | Type 1 |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | Foundation model + tools (tool invocation system); `chưa xác minh` model cụ thể |

**1. Vấn đề và đóng góp.** Zero-shot explainable rec: LLM agent gọi tools (search, filter, evaluate) + CoT reasoning để recommend kèm giải thích; claim improvements trên Amazon Electronics/MovieLens/Yelp.

**2. Kiến trúc chi tiết.** Tool invocation → candidate evaluation → CoT reasoning → recommendation với explanation. Latency 2.3s/user; tool caching + parallel tool invocation.

**3. Dữ liệu.** Amazon Electronics + MovieLens + Yelp (`chưa xác minh` version/split). 

**4. Metric và kết quả** (Table I/III: NDCG@5/10, HR@10, MRR): Amazon Electronics NDCG@10 = **0.272** vs AgentCF 0.271 (**+0.4%**); Table IV ablation: RAG component +0.4%, tool invocation +0.2%, CoT +0.1%. (Nguồn: §Results + Table III.)

**5. Điểm đáng mượn.** Tool caching + parallel invocation cho latency; ablation cho thấy mỗi component đóng góp nhỏ — bài học "đừng kỳ vọng nhiều".

**6. Hạn chế / cờ kiểm tra.** ⚠ Gain +0.4% NDCG@10 rất nhỏ — có thể trong noise; paper quality đáng ngờ (2025 arXiv, Peking Univ); `chưa xác minh` nhiều chi tiết; không repo.

---

### MoRE — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "MoRE: A Mixture of Reflectors Framework for Large Language Model-Based Sequential Recommendation", 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | LLaMA-3-8B |

**1. Vấn đề và đóng góp.** Mixture of Reflectors: nhiều reflector chuyên biệt (different aspects) phản hồi cho sequential rec — chọn reflector phù hợp theo context.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: mixture-of-reflectors framework, LLaMA-3-8B, candidate pool 50.

**3. Dữ liệu.** Amazon Arts&Crafts & Sewing, Video Games, Musical Instruments (2018 `chưa xác minh`). Pool = **50 candidates**.

**4. Metric và kết quả.** HR, NDCG (`chưa xác minh` k và số liệu cụ thể).

**5. Điểm đáng mượn.** Multi-reflector specialization — ý tưởng nếu reflection của project cần nhiều "góc nhìn".

**6. Hạn chế / cờ kiểm tra.** `chưa xác minh` nhiều — cần đọc lại paper nếu muốn dùng.

---

### Re2LLM — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "Re2LLM: Reflective Reinforcement Large Language Model for Session-Based Recommendation", 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | `chưa xác minh` |

**1. Vấn đề và đóng góp.** Reflective exploration knowledge base + RL-trained retrieval agent cho session-based rec.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: reflective exploration KB + retrieval agent RL.

**3. Dữ liệu.** Amazon Video Games (`chưa xác minh` version). Session-based.

**4. Metric và kết quả.** `chưa xác minh`.

**5. Điểm đáng mượn.** `chưa xác minh`.

**6. Hạn chế / cờ kiểm tra.** Paper chưa phân tích sâu — `chưa xác minh` hầu hết.

---

### SRLF — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "SRLF: An Agent-Driven Set-Wise Reflective Learning Framework for Sequential Recommendation", 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | `chưa xác minh` |

**1. Vấn đề và đóng góp.** Set-wise reflective learning: reflect trên **tập** candidates (không chỉ từng item) cho sequential rec.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: set-wise reflection, agent-driven.

**3. Dữ liệu.** Amazon CDs&Vinyl + MovieLens. Pool = 1 target + 9 negatives = **10 candidates**.

**4. Metric và kết quả.** NDCG (`chưa xác minh` số liệu cụ thể).

**5. Điểm đáng mượn.** Set-wise reflection — reflect trên cả candidate set thay vì item đơn lẻ.

**6. Hạn chế / cờ kiểm tra.** `chưa xác minh` nhiều.

---

### R4EC — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "R4EC: A Reasoning, Reflection, and Refinement Framework for Recommendation Systems", 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | Qwen-2.5-7B (SFT) |

**1. Vấn đề và đóng góp.** Reasoning→Reflection→Refinement cho CTR prediction: LLM sinh reasoning, reflect, refine → SFT.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: actor+reflection SFT'd Qwen-2.5-7B.

**3. Dữ liệu.** Amazon Books (`chưa xác minh` version).

**4. Metric và kết quả.** AUC, LogLoss cho CTR (**không phải top-k**). `chưa xác minh` số liệu.

**5. Điểm đáng mượn.** `chưa xác minh`.

**6. Hạn chế / cờ kiểm tra.** `chưa xác minh` nhiều; CTR pointwise khác top-k.

---

### RuleAgent — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "RuleAgent: Discovering Rules for Recommendation Denoising with Autonomous Language Agents", 2025 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có |
| Backbone LLM / embedding | `chưa xác minh` |

**1. Vấn đề và đóng góp.** Denoising rules discovery: LLM agent tự khám phá rules để lọc nhiễu trong recommendation data.

**2. Kiến trúc chi tiết.** `chưa xác minh` đầy đủ — notes: denoising rules agent.

**3. Dữ liệu.** Amazon Beauty + Yelp + Gowalla (small). 

**4. Metric và kết quả.** R@10/20, N@10/20 (`chưa xác minh` số liệu và pool size).

**5. Điểm đáng mượn.** Rule discovery cho data cleaning — nếu project cần lọc nhiễu Amazon 2023.

**6. Hạn chế / cờ kiểm tra.** `chưa xác minh` nhiều.

---

### PUMA — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "Large Language Models Empowered Personalized Web Agents" (framework **PUMA** + benchmark **PersonalWAB**), Hongru Cai và cộng sự, **WWW '25** (Sydney), DOI 10.1145/3696410.3714842 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon (không repo) |
| Repo | Không có (paper nói "release code and data at PersonalWAB github repository" — link `chưa xác minh`) |
| Backbone LLM / embedding | LLM Web agent; memory bank + task-specific retrieval; SFT + DPO alignment |

**1. Vấn đề và đóng góp.** Personalized Web agents: LLM + personalized user data (profiles + Web behaviors) cho personalized search/recommendation/review trên Web; benchmark PersonalWAB (1000 users từ Amazon review dataset).

**2. Kiến trúc chi tiết.** PUMA: memory bank lưu long-term Web behaviors → task-specific retrieval filter relevant → kết hợp với instruction → gọi Web functions + generate function parameters → SFT với pseudo-labels + DPO pair-wise optimization.

**3. Dữ liệu.** **Amazon review dataset** [15] — version `chưa xác minh`; 5 categories theo xlsx: Electronic, Home&Kitchen, Grocery&GourmetFood, Clothing, Health&Household. 1000 simulated users.

**4. Metric và kết quả.** Function accuracy, result accuracy, outcome accuracy cho 3 tasks (search, recommendation, review generation); single-turn + multi-turn LLM-simulator eval. `chưa xác minh` số liệu cụ thể.

**5. Điểm đáng mượn.** Memory bank + task-specific retrieval cho personalized context; pseudo-label SFT + DPO cho function-parameter generation; benchmark construction methodology.

**6. Hạn chế / cờ kiểm tra.** Web-agent task khác recsys thuần; `chưa xác minh` nhiều số liệu; version Amazon chưa rõ.

---

### AgentDR — Type 2 single — Tier C

| Trường | Giá trị |
|---|---|
| Paper | "AgentDR: Bridging LLM Reasoning with Scalable Recommendation Tools" (title đầy đủ `chưa xác minh` — arXiv 2510.05598), Amazon authors, 2026 |
| Type theo xlsx | Type 2 single |
| Lý do đủ điều kiện | Amazon-sounding nhưng **không phải Amazon Reviews** — Instacart + XMarket |
| Repo | Không có |
| Backbone LLM / embedding | LLM agents + recommendation tools: LightGCN, SASRec, SimpleX |

**1. Vấn đề và đóng vấn đề.** Full-ranking recommendation: LLM agents ủy quyền ranking cho ID-based tools (tránh hallucination + token limit); LLM làm (i) tool comparison/fusion cá nhân hóa, (ii) substitute/complement reasoning trên user history, (iii) rerank theo semantic similarity.

**2. Kiến trúc chi tiết.**
- 3 rec tools (LightGCN graph, SASRec sequential, SimpleX MF) pretrained trên s[:-t] → full-ranking score lists.
- User profile summarization bằng LLM từ item descriptions.
- Substitute/complement generation: LLM sinh substitutes+complements cho recent interests → refine top items từ tools (tránh O(|I|²) LLM calls bằng chỉ refine top-ranked).
- Tool comparison module: LLM chọn best tool per user dựa trên recommended results vs ground-truth preference; RecTool memory update.
- General reranking: semantic similarity giữa candidates và user profile.
- Hallucination filtering mechanism (Sec 3.6).

**3. Dữ liệu.** **Instacart** (6,987 users × 2,108 items × 5.1M interactions, density 34.7%), **XMarket Electronics** (4,966 × 14,635 × 91,819), **XMarket Sports** (10,873 × 4,306 × 55,990). `chưa xác minh` split protocol.

**4. Metric và kết quả** (Table 3 — **full catalog**, Recall@10/20, NDCG@10/20 + VDCG mới):

| Dataset | AgentDR R@10 | Best baseline R@10 | AgentDR N@10 | Best baseline N@10 |
|---|---|---|---|---|
| Instacart | 0.1563 | DiffRec? ~0.1188 | 0.0907 | ~0.0806 |
| Electronics | 0.1688 | ~0.1562 | 0.1260 | ~0.0981 |
| Sports | 0.1750 | ~0.1625 | 0.1326 | ~0.1187 |

Paper claim: +33.5% recall / +28.4% NDCG vs underlying tools on average; "twofold improvement" trên một số so sánh. (Nguồn: Table 3 + §5.1 — mapping baseline columns `chưa xác minh` từng ô do dump jumbled; các giá trị trên trích conservative.)

**5. Điểm đáng mượn.** **Đúng triết lý project nhất trong Tier C**: LLM không rank catalog — tools rank full catalog, LLM fuse/rerank/refine; substitute/complement reasoning grounded trên user history; tool-comparison cá nhân hóa; hallucination filtering; VDCG metric mới (semantic vicinity) — thú vị cho eval.

**6. Hạn chế / cờ kiểm tra.** ⚠ Dataset **không phải Amazon Reviews** — XMarket là Amazon product metadata (titles/descriptions), Instacart là grocery transactions; xlsx ghi "Amazon" gây hiểu nhầm; paper 2026 rất mới, venue `chưa xác minh`; baseline pool-free full-ranking nhưng catalog nhỏ (2K–15K items) so với Amazon 2023 (hàng triệu).

---

## 9. §4 — Đào sâu InteRecAgent (trả lời 5 câu hỏi, đối chiếu lỗi project)

(Nguồn code: `cloned_repos/RecAI/InteRecAgent/llm4crs/`; phân tích đầy đủ: `cloned_repos/docs/REPORT.md` §4.)

**(1) Hard vs soft condition truyền thế nào.** Prompt system (`prompt/system.py:27-29`) yêu cầu LLM "Separate hard and soft conditions". Hard → **SQL string** do LLM viết, chạy qua `rewrite_sql` (`retrieval/sql_tool.py:78-106`): ép `FROM <bảng>` đúng tên, fuzzy-match cột lạ → cột gần nhất (SentBERT), mọi `col LIKE '%v%'` trên cột categorical → thay `v` bằng giá trị gần nhất trong `categorical_col_values`. Soft → **Python list of seed item titles** (`literal_eval`, `itemcf_tool.py:29`), title→id qua `fuzzy_match`, chấm similarity = mean trên `item_sim[seed_ids][:, candidates]`, giữ item score > ngưỡng = điểm của top-`rec_num` toàn catalog. Tức: hard đi qua **text-to-SQL có grounding**, soft đi qua **item-to-item similarity matrix** — hai cơ chế hoàn toàn khác nhau.

**(2) Candidate Bus có giữ điểm không?** Chỉ giữ **item IDs** (`buffer/base.py:12-170`). Điểm chỉ tồn tại dưới dạng sidecar `similarity` array do SimilarItemTool ghi và RecModelTool đọc khi `schema=="similarity"` — không phải score tổng quát theo từng bước filter. Mỗi tool `push` ghi đè `memory`; buffer rỗng → các tool trả "0 eligible items … Stop execution".

**(3) Điều kiện kích hoạt Reflection/Rechain.** `Critic` (LLM judge riêng) đọc conversation + `buffer.track_info` (tool,input,output) + answer → trả "Yes" hoặc "No. …advice" theo 5 tiêu chí (`prompt/critic.py:52-85`). Rechain chỉ chạy khi `rechain=True` và `_reflection_cnt < reflection_limits` (default **3**) — `agent.py:168-184` / `agent_plan_first_openai.py:449-471`; reflection text chèn vào slot `{{reflection}}` của prompt cho vòng plan tiếp theo; reset counter khi thành công.

**(4) Xử lý "không muốn X".** Hai đường, đều ở mức **item** chứ không phải attribute: (a) RankingTool input `unwanted` = list item titles → mask điểm = −100000 (accuracy) hoặc 0 trong diversity sampling (`reco_model_tool.py:85-93,164-172`); (b) ToolBox tự merge `profile["unwanted"]` từ UserProfileMemory vào ranking input (`agent_plan_first_openai.py:66-71`). **Không có "exclude category/attribute"** — khác FilterTool của project (có `exclude_categories_any`).

**(5) Item thiếu metadata.** Bị **loại im lặng** — giống hệt project: pandasql `sqldf` trên item table; NULL/NaN không match `LIKE`/`=` → item rơi khỏi kết quả mà không báo. Giảm nhẹ duy nhất: prompt `info()` cảnh báo "categorical columns … must use related values … otherwise no result" + Critic được chỉ dẫn kiểm tra "0 eligible items" và gợi ý nới điều kiện (`prompt/critic.py:69`). Tức họ **phát hiện hậu kỳ** chứ không ngăn từ đầu.

**Đối chiếu 3 lỗi đã biết của project** (chi tiết: docs/REPORT.md §"Đối chiếu 3 lỗi"):
- `filters: {}` ~70%: InteRecAgent không có structured filter; bài học = `info()` inject giá trị hợp lệ + Critic phạt "gọi tool khi không có preference".
- `categories_exclude` bịa key: họ chống bằng **grounding-replace** (fuzzy→canonical, không reject); project đang reject cứng → planner lặp lại vì prompt mâu thuẫn (`prompts.yaml:36`).
- Category filter loại im lặng ~9%: **họ mắc cùng lỗi** — NULL không match; chỉ có Critic hậu kỳ + "N eligible items" trong tool response cho LLM thấy.

---

## 10. Phần cuối

### 10.1 Tám paper đã loại (không repo + không Amazon)

RecByGen, Agent0, RouteLLM, LLMRecAgent, GRS, SmartEats, AdaptJobRec, VRAgent-R1 — theo brief §1; không review.

### 10.2 Danh sách `chưa xác minh` gộp

- **Amazon version** chưa xác minh: iAgent, MemRec, AKF-Agent, CoRAL, CDA4Rec, MoRE, Re2LLM, SRLF, R4EC, RuleAgent, PUMA, AgenticRAG, DRDT, BiLLP/T-PRA/InteRecAgent/Tool-Rec/AgentCF++ (xác nhận bản cũ 2014/2018, không phải 2023).
- **Số liệu cụ thể** `chưa xác minh`: MemRec Tables 2–3 (absolute), T-PRA Table 1 (mapping cột), CoRAL (AUC/F1), CDA4Rec Table II (ô Sports), AKF-Agent (toàn bộ), MoRE/Re2LLM/SRLF/R4EC/RuleAgent/PUMA (hầu hết), DRDT Table 2 (từng ô), ItemRAG Table 2 cold-start, RecMind Table 3 sequential (mapping cột), RAH Table 5 (một số ô), AgenticRAG dataset details.
- **Kiến trúc/code** `chưa xác minh`: CoRAL state/action space, CDA4Rec cloud-device split, AKF-Agent fusion mechanism, MoRE reflector types, Re2LLM KB+RL, SRLF set-wise mechanism, R4EC pipeline, RuleAgent rules, iAgent candidate pool size, AgentCF++ LLM backbone, ECPO SR/R formulas.
- **Repo**: RecMind rỗng; RAH code chưa đọc sâu; VibeMus eval chưa đọc; RecAI paper con chưa đọc (RecLlama/RecLM-emb papers riêng).

### 10.3 Repo rỗng / không truy cập được

- **RecMind** (github.com/XMHZZ2018/RecMind): README-only, tác giả ghi "cannot be open-sourced" — không có gì để đọc.
- Không repo nào khác bị lỗi truy cập; 14/15 repo link đều clone được code thật.

### 10.4 Việc người dùng cần quyết

1. **Ưu tiên đọc lại** các paper `chưa xác minh` nhiều nhất nếu muốn dùng: CoRAL (RL retrieval), CDA4Rec (full-catalog + cloud-device), AKF-Agent (knowledge fusion), AgentDR (đã có số liệu chính — chỉ cần verify baseline mapping).
2. **Xác nhận Amazon 2023**: chỉ ECPO chắc chắn dùng AmazonReviews2023; ItemRAG "latest" rất có thể 2023 — nên kiểm tra citation [3] trong paper để khẳng định.
3. **Quyết định hướng mượn**: gợi ý top-3 đáng đào sâu cho project — (a) InteRecAgent plan-first + grounding layer + Critic (đã phân tích sâu trong docs/REPORT.md §4); (b) AgentDR ủy quyền full-ranking cho tools + LLM fuse/rerank; (c) ItemRAG item-side enrichment cho metadata.
4. **Không nên mượn**: RecMind (repo rỗng + kết quả yếu), VibeMus (ngoài phạm vi), RAH (không top-k eval + self-reported leakage), AgentCF++/iAgent/MemRec (pool 10 quá nhỏ so với full catalog).

