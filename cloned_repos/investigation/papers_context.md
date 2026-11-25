# Papers Context — index & báo cáo liên quan

Ngày tạo: 2026-11-25. Thư mục này lưu **context/báo cáo tổng hợp về các paper** trong `cloned_repos/papers/` (38 PDF) và mối liên hệ với code repo đã clone trong `cloned_repos/`.

## 1. Reports hiện có (đọc trước file này)

| Report | Phạm vi | Vị trí |
|---|---|---|
| Khảo sát **code** 7 repo single-agent recommender (Phase A/B/C: pipeline, query→cấu trúc, retrieval, ranking, lỗi, eval, mapping sang `package/`) | iAgent, MemRec, ItemRAG, BiLLP, T-PRA, VibeMus, InteRecAgent (RecAI) | `cloned_repos/docs/REPORT.md` + `cloned_repos/docs/MANIFEST.md` |
| Review **paper** Type 1/Type 2 single cho DACNTT_2627 (26 paper đủ điều kiện: tier A/B/C, giao thức eval, sai lệch xlsx↔paper, ma trận Amazon category) | 26 paper trong brief §1 — chi tiết từng paper ở §6–7 | `cloned_repos/investigations/framework_review/REPORT.md` (kèm `survey_papers.txt`, `texts/` đã trích) |

## 2. Repo đã clone trong `cloned_repos/`

`AgentCFpp`, `BiLLP`, `ECPO`, `ItemRAG`, `RAH`, `RecAI` (chứa InteRecAgent), `RecMind` (**rỗng — chỉ README**, tác giả ghi không open-source), `T-PRA`, `ToolRec`, `VibeMus`, `iAgent`, `memrec`.

→ **12 repo**, trong đó 11 có code thật; chỉ RecMind là stub. 7 repo đầu (iAgent→RecAI) đã được khảo sát code chi tiết trong `docs/REPORT.md`; 5 repo còn lại (AgentCFpp, ECPO, RAH, RecMind, ToolRec) mới chỉ có đánh giá paper-level trong `framework_review/REPORT.md`.

## 3. Index 38 PDFs trong `papers/`

Cột "Report": `code` = có trong `docs/REPORT.md`; `paper` = có trong `framework_review/REPORT.md`; `—` = chưa có báo cáo chuyên sâu.

### 3.1 Paper có repo đã clone

| PDF (`papers/`) | Paper / framework | Repo | Report |
|---|---|---|---|
| ItemRAG - Retrieval-Augmented Recommendation with Item-Side Knowledge.pdf | ItemRAG (SIGIR'26 short) | `ItemRAG/` | code + paper (Tier A) |
| MemRec Collaborative Memory-Augmented.pdf | MemRec (ACL 2026) | `memrec/` | code + paper (Tier A) |
| RecAI Leveraging Large Language Models for Next-Generation Recommender Systems.pdf | RecAI toolkit paper (gốc của InteRecAgent/RecLM/…) | `RecAI/` | paper (Tier B) — code InteRecAgent đã khảo sát trong docs/REPORT |
| Large Language Models are Learnable Planners for Long-Term Recommendation.pdf | **BiLLP** (SIGIR 2024) | `BiLLP/` | code + paper (Tier A) |
| VibeMus Proactive Agentic System for Music Personalization.pdf | VibeMus (không phải recsys) | `VibeMus/` | code + paper (Tier B) |
| Expectation Confirmation Preference Optimization for Multi-Turn Conversational Recommendation Agent.pdf | **ECPO** (arXiv 2506.14302) | `ECPO/` | paper (Tier A) — chưa khảo sát code |
| AgentCF Collaborative Learning with Autonomous Language.pdf | AgentCF (WWW 2024) | `AgentCFpp/` (repo là AgentCF++) | paper (Tier A, của AgentCF++) — code chưa khảo sát |
| AgentCF++ - Memory-Enhanced LLM-Based Agents for Popularity-Aware Cross-Domain Recommendations.pdf | AgentCF++ (SIGIR 2025) | `AgentCFpp/` | paper (Tier A) — code chưa khảo sát |

### 3.2 Paper trong survey 26-paper nhưng chưa clone repo (hoặc repo không có trong đợt này)

| PDF | Paper | Report (framework_review) |
|---|---|---|
| DRDT Dynamic Reflection with Divergent Thinking …Sequential Recommendation.pdf | DRDT (2023) | Tier C — không có code |
| Intelligent Agents with Adaptive Knowledge Fusion for Personalized Recommendation.pdf | AKF-Agent (2025) | Tier C — không có code |
| MoRE A Mixture of Reflectors Framework …Sequential Recommendation.pdf | MoRE (2025) | Tier C — không có code |
| R4EC A Reasoning, Reflection, and Refinement Framework for Recommendation Systems.pdf | R4EC (2025) | Tier C — không có code |
| Re2LLM Reflective Reinforcement LLM for Session-Based Recommendation.pdf | Re2LLM (2025) | Tier C — không có code |
| RuleAgent Discovering Rules for Recommendation Denoising …Agents.pdf | RuleAgent (2025) | Tier C — không có code |
| SRLF An Agent-Driven Set-Wise Reflective Learning Framework …Sequential Recommendation.pdf | SRLF (2025) | Tier C — không có code |

### 3.3 Paper trong `papers/` ngoài phạm vi 26-paper của framework_review (survey/benchmark/mới)

Chưa có báo cáo chuyên sâu; chỉ ghi nhận tồn tại. Venue/year "chưa xác minh" trừ khi ghi rõ.

| PDF | Ghi chú |
|---|---|
| A survey of foundation model-powered recommender systems - From feature-based, generative to agentic paradigms..pdf | Survey |
| A survey on LLM-powered agents for recommender systems..pdf | Survey |
| Recommender Systems Meet Large Language Model Agents A Survey.pdf | Survey |
| Large language models for generative recommendation - A survey and visionary discussions..pdf | Survey (LREC-COLING 2024) |
| The Future is Agentic Definitions, Perspectives, and Open Challenges of Multi-Agent Recommender Systems.pdf | Survey/position, multi-agent |
| Autonomous Information Seeking A Roadmap for Agentic Recommender Systems.pdf | Roadmap paper |
| AgentRecBench Benchmarking LLM Agent-Based Personalized Recommender Systems.pdf | Benchmark |
| AlignUser Human-Aligned LLM Agents via World Models for Recommender System Evaluation.pdf | User simulator / eval (trong xlsx là Evaluation & Benchmark) |
| Agentic Feedback Loop Modeling Improves Recommendation and User Simulation.pdf | Feedback loop / user sim |
| Interactive Recommendation Agent with Active User Commands.pdf | Chưa xác minh nội dung |
| Thought-Augmented Planning for LLM-Powered Interactive Recommender Agent.pdf | Chưa xác minh nội dung |
| Get the Agents Drunk Memory Perturbations in Autonomous Agent-based Recommender Systems.pdf | Robustness/memory perturbation |
| Stealthy LLM-Driven Data Poisoning Attacks against Embedding-Based Retrieval-Augmented Recommender Systems.pdf | Security/attack paper |
| Bridging Language and Items for Retrieval and Recommendation Benchmarking LLMs as Semantic Encoders.pdf | Retrieval benchmark |
| Large Language Models Empowered Personalized Web Agents.pdf | = paper PUMA/PersonalWAB (WWW'25) trong survey — web agent, không phải recsys top-k |
| Constraint-Aware Route Recommendation from Natural Language via Hierarchical LLM Agents.pdf | Domain khác (route rec), ngoài scope |
| AdaptJobRec - Enhancing Conversational Career Recommendation through an LLM-Powered Agentic System.pdf | Domain khác (career rec) |
| MADREC A Multi-Aspect Driven LLM Agent for Explainable and Adaptive Recommendation.pdf | Chưa xác minh |
| MAP Multi-User Personalization with Collaborative LLM-Powered Agents.pdf | Multi-user/collaborative agents |
| Multi-Agent Collaborative Filtering Orchestrating Users and Items for Agentic Recommendations.pdf | Multi-agent |
| Cloud-Device Collaborative Agents for Sequential Recommendation.pdf | Chưa xác minh (= CDA4Rec? cần đối chiếu) |
| Large Language Models are Learnable Planners for Long-Term Recommendation.pdf | (đã liệt kê ở §3.1 — là paper của BiLLP) |

> Lưu ý: mapping tên PDF ↔ tên framework trong bảng trên dựa trên tiêu đề; các mục "chưa xác minh" cần đọc PDF/xlsx để chốt. Một số paper có thể trùng lặp khái niệm với framework trong survey nhưng không nằm trong 26 paper được review.

## 4. Paper có repo nhưng **không có PDF local** trong `papers/`

| Repo | Paper | Report |
|---|---|---|
| `iAgent/` | iAgent / i²Agent — ACL 2025 Findings | code (docs/REPORT) + paper Tier A (text trích trong framework_review/texts) |
| `T-PRA/` | T-PRA — ACL 2025 | code (docs/REPORT) + paper Tier A |
| `ToolRec/` | Tool-Rec — SIGIR 2024 | paper Tier A — code chưa khảo sát |
| `RAH/` | RAH — 2024 IEEE TCSS | paper Tier A — code chưa khảo sát |
| `RecMind/` | RecMind — NAACL 2024 Findings | paper Tier A — **repo rỗng** |

## 5. Cách dùng thư mục này

- Cần đối chiếu **code thực tế** → `docs/REPORT.md` (7 repo đã đọc sâu) trước, rồi `framework_review/REPORT.md` §6–7 cho paper-level.
- Cần biết paper nào đã/ chưa được review → bảng §3–4 ở trên.
- Muốn mở rộng khảo sát code cho 5 repo còn lại (AgentCFpp, ECPO, RAH, ToolRec; RecMind bỏ qua vì rỗng) → theo cùng format Phase B/C trong `docs/REPORT.md`.
