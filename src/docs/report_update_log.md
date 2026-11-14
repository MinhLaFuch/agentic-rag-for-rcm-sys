# Report Update Log: 52300145_52300150.docx v2

**Update Date**: 2026-11-12
**Branch**: tools-building
**Commit**: 880bf5c
**Source Document**: 52300145_52300150.docx (6 chapters)
**Target Document**: 52300145_52300150_v2.docx (copy)

---

## 1. Chương/Mục | Cũ | Mới | Căn cứ

## 1. Chương/Mục | Cũ | Mới | Căn cứ

### Chương 3: PHƯƠNG PHÁP ĐỀ XUẤT VÀ THIẾT KẾ HỆ THỐNG

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.1.4 / 3.3 / 3.4 | package/agents/plan_executor.py | package/agents/planner/plan_executor.py | src/package/agents/planner/plan_executor.py exists |
| 3.1.4 / 3.3 / 3.4 | package/agents/type1_agent.py | package/agents/type1/type1_agent.py | src/package/agents/type1/type1_agent.py exists |
| 3.1.2 / Table 3.1 | tools/{corpus,recommenders,score,sql_query,evaluation} | package/tools/{retrieval,ranking,scoring,sql,base} + package/utils/ | Get-ChildItem src/package/tools/ |
| 3.2.1 Body text | Pipeline gồm **ba giai đoạn** | Pipeline gồm **bốn giai đoạn** | scripts/data_pipeline/run_pipeline.py lines 14-17 |
| Fig 3.2 Caption | Pipeline xử lý dữ liệu **ba giai đoạn** | Pipeline xử lý dữ liệu **bốn giai đoạn** | 4 stages in code |
| Table 3.2 Caption | Bảng 3.2. **Ba giai đoạn** của pipeline dữ liệu | Bảng 3.2. **Bốn giai đoạn** của pipeline dữ liệu | 4 stages in code |
| Table-of-figures (Bảng 3.3) | Bảng 3.3. **Ba giai đoạn** | Bảng 3.3. **Bốn giai đoạn** | 4 stages in code |
| 3.3.1 Recommender | mô hình gợi ý (vague) | Phân biệt runtime vs evaluation-only | src/package/recommenders/ |
| 3.3.2 CandidateScorer | CandidateScorer là giao diện chuẩn giữa RecoModelTool... | CandidateScorer là giao diện chuẩn (Protocol), định nghĩa tại package/tools/scoring/candidate_scorer.py | src/package/tools/scoring/candidate_scorer.py |
| 3.3.2 BaselineScorer | bọc các mô hình Popularity và ItemKNN | bọc các mô hình runtime Popularity và ItemKNN, tại package/tools/scoring/baseline_scorer.py | src/package/tools/scoring/baseline_scorer.py |
| 3.4 / Table 3.3 | Tool subdirectory paths (flat) | retrieval/ (SearchTool), ranking/ (SimilarTool, RankTool), scoring/ (BaselineScorer...), sql/ (FilterTool, LookupTool), base/ | src/package/tools/__init__.py |

### 3.4 HỆ THỐNG CÔNG CỤ

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.4.1/Table 3.3/3.4.3-3.4.8 | SemanticSearchTool | SearchTool | agent_tools.py lines 7-20 |
| 3.4.1/Table 3.3/3.4.3-3.4.8 | ItemCFTool | SimilarTool | agent_tools.py lines 7-20 |
| 3.4.1/Table 3.3/3.4.3-3.4.8 | SQLTool | FilterTool | agent_tools.py lines 7-20 |
| 3.4.1/Table 3.3/3.4.3-3.4.8 | RecoModelTool | RankTool | agent_tools.py lines 7-20 |
| 3.4.1/Table 3.3/3.4.3-3.4.8 | QueryTool | LookupTool | agent_tools.py lines 7-20 |
| 3.4.1/Table 3.3/3.4.3-3.4.8 | MemoryTool | MemoryTool (unchanged) | agent_tools.py lines 7-20 |
| 3.4.3-3.4.8 Headings | 3.4.3 SemanticSearchTool -> 3.4.3 SearchTool | Updated to canonical names | agent_tools.py |
| Table 3.3 | Old tool names in cells | Canonical names + updated descriptions | Tool implementations in src/package/tools/ |
| 3.4.4 | ItemCFTool chỉ dùng các láng giềng... | SimilarTool: Item-to-item collaborative filtering... | src/package/tools/ranking/similar_tool.py |
| 3.4.5 | SQLTool lọc sản phẩm... | FilterTool: Structured filtering on product catalog... | src/package/tools/sql/filter_tool.py |
| 3.4.6 | RecoModelTool xếp hạng... | RankTool: CandidateScorer scoring... | src/package/tools/ranking/rank_tool.py |
| 3.4.7 | QueryTool lấy metadata... | LookupTool: Structured metadata hydration... | src/package/tools/sql/lookup_tool.py |
| 3.4.9 / Table 3.4 | Error taxonomy with old tool names | Updated with canonical tool names | src/package/agents/planner/_helper.py |

### 3.5 TẦNG TÁC TỬ

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.5.3 Type1Agent | package/agents/type1_agent.py | package/agents/type1/type1_agent.py | File location |
| 3.5.4 PlanExecutor | package/agents/plan_executor.py | package/agents/planner/plan_executor.py | File location |
| 3.5.4 Planner tools | 4 công cụ (ItemCF, RecoModel, Query, SemanticSearch) | 5 công cụ (SimilarTool, RankTool, LookupTool, SearchTool, FilterTool) | agent_tools.py for_planner() |
| 3.5.5 Reflection | Brief mention | Added: reflection triggers, quality threshold, _helper.py helpers | src/package/agents/planner/_helper.py |
| 3.5.5 MemoryTool | package/agents/memory_tool.py | package/memory/memory_tool.py | File location |
| 3.5.7 Multi-turn | [Phần này nhóm chưa hoàn thiện] | mock-only; chưa có artifact xác nhận (Phase E skipped) | configs/agent/agent_eval.yaml |

### 3.6 TẦNG INFERENCE VÀ TẠO CÂU TRẢ LỜI

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.6.1 Inference functions | Not specified | compose_llm (package/inference/compose/compose_llm.py), compose_template (package/inference/compose/compose_template.py), check_grounding (package/inference/grounding/check_grounding.py) | Source files |
| 3.6.3 / Table 3.5/3.6 | Table numbering issues | Fixed numbering + status priority | src/package/inference/outcome.py |
| 3.6.4 Grounding | Brief | Added: check_grounding implementation, retry/fallback, compose_llm retry loop | src/package/inference/grounding/check_grounding.py, compose_llm.py |
| 3.6.3 Template mode | Brief | Deterministic: OK_HEADER, PARTIAL_HEADER, cut_title, grounded=True | compose_template.py, _prompt.py, cut_title.py |

### 3.7 CẤU HÌNH, KIỂM THỬ VÀ QUY ƯỚC KỸ THUẬT

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.7.1 Config counts | Not stated | 33 YAML files: configs/agent/ (11), configs/data/ (3), configs/eval/ (15), configs/evaluation/ (1), configs/path/ (3) | Get-ChildItem on each dir |
| 3.7.1 Config overlay | Not detailed | CONFIG_OVERLAY_PATH env var, campaign runner writes per-experiment overlays | src/package/config/loader.py, configs/evaluation/campaign.yaml |
| 3.7.3 Test stats | 1250 ca đạt, 2 lỗi, 5 skip, 2 xfail | 1696 test case collected; 1690 passed, 4 skipped, 2 xfail | pytest --collect-only -q, repo_reading_update_log.md |
| 3.7.3 Fake LLM | LLM giả lập | ScriptedLLM trong tests/agents/fakes/ | src/tests/agents/fakes/ |

### 3.8 HỆ THỐNG ĐÁNH GIÁ TRONG KIẾN TRÚC

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 3.8/3.8.1 | bốn bộ/sáu bộ đánh giá | ba tầng đánh giá chính (12 bộ đánh giá chi tiết) | Architecture: 5-layer + 6 component benchmarks + recommender eval + campaign |
| Table 3.6 | 6 groups | Restructured: 3 tiers (Offline Ranking, Agent Evaluation, Component Benchmarks + Campaign) | src/package/evaluation/ |
| 3.9 Ví dụ | Old tool names | Updated: 5 tools (added FilterTool), fixed .path syntax | agent_tools.py, plan_executor.py |
| 3.10.1 Design decisions | Old list | 8 decisions from repo_reading_update_log.md | docs/repo_reading_update_log.md |
| 3.10.2 Limitations | Old list | 10 limitations from repo | repo_reading_update_log.md §0.14 |

### CHƯƠNG 4: THỰC NGHIỆM VÀ THIẾT LẬP ĐÁNH GIÁ

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 4.2.4 Environment | Vague | Specific configs: agent_eval.yaml, campaign.yaml, component_benchmarks.yaml, parameter grid (12 exps) | Config files |
| 4.5/4.6 Ablation | Basic | Detailed: 4 agents x 2 inference_mode x 2 reflect_rounds = 12 exps; 6 component benchmarks; memory ablation; reflection ablation | configs/evaluation/campaign.yaml, component_benchmarks.yaml |
| 4.5.3 Metrics | Basic | 5-layer scoring (score_trajectory.py); task success != Recall@K | score_trajectory.py |
| 4.6.2 Component ablation | Vague | Planner vs planner_memory; reflect_rounds 0 vs 1 | Campaign parameter grid |

### CHƯƠNG 5: KẾT QUẢ THỰC NGHIỆM VÀ PHÂN TÍCH

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| Chapter 5 Body | Claims without artifact refs | Added [chưa có artifact xác nhận] for: candidate recall, baseline eval, campaign_001, component benchmarks, multi-turn, git_sha provenance | experiments/ directory state, repo_reading_update_log.md |
| 5.5 Những vấn đề... | 6 bullets | Each bullet annotated with [chưa có artifact xác nhận] or [mock-only; chưa có artifact xác nhận] | Artifact verification |
| Section 5.5 Full Text | Old 6 bullets | Updated with evidence status markers | repo_reading_update_log.md §0.13 |

### CHƯƠNG 6: CẢI THIỆN VÀ HƯỚNG PHÁT TRIỂN

| Mục | Cũ | Mới | Căn cứ |
|-----|-----|-----|--------|
| 6.1.1 / Table 6.1 | 6 issues (vague) | 6 issues with current status: embedding (primitives exist, not wired), real-LLM eval (blocked), Jev (blocked), multi-turn (mock-only), Opik (PoC), git_sha (empty) | repo_reading_update_log.md §0.13, §0.16 |
| 6.1.3 / Table 6.2 | Week-based deadlines | Removed week deadlines; priority-ordered (8 items, no week numbers) | Instruction: không tự đặt deadline mới |
| Table 6.2 Content | Week-based | Priority-ordered: 1) Embedding, 2) Real-LLM, 3) Jev, 4) Multi-turn real, 5) Opik, 6) git_sha, 7) Latency, 8) Cross-domain | repo_reading_update_log.md §0.16 |
| 6.2 / Table 6.3 | Old directions | Updated with status: embedding primitives exist, BPR-MF offline-only, session infra exists (enable_session=false), Jev/Opik blocked, metadata leakage partially mitigated | repo_reading_update_log.md §0.16 |
| 6.1.1 Intro | No note | Added: Lưu ý: các artifact thực nghiệm chưa đầy đủ do blocker môi trường (resource/, credentials) | Artifact verification |

### PHỤ LỤC: DANH MỤC CÁC CHỮ VIẾT TẮT

| Cũ | Mới | Căn cứ |
|-----|-----|--------|
| SemanticSearchTool, ItemCFTool, SQLTool, RecoModelTool, QueryTool | Removed (replaced by canonical names) | agent_tools.py canonical 6 tools |
| — | Added 17 new terms: Jev, Opik, vLLM, Ollama, LM Studio, Gradio, pytest, Git, SHA256, CI/CD, PoC, SOTA, ORACLE, RR, E2E, P50/P95/P99, CI95 | configs/, scripts/, repo_reading_update_log.md |
| — | Updated: RR=Round-Robin, CF, MF, NDCG, MAP, MRR, Recall@K, Precision@K | Standard definitions |

## 2. Danh sách [CẦN XÁC NHẬN] (8 items, 4 Critical)

| # | Mục | Trạng thái | Hành động cần thiết |
|---|-----|------------|---------------------|
| 1 | Candidate recall experiments | Critical | Chạy scripts/evaluation/candidate_recall.py trên dữ liệu thật (cần resource/) |
| 2 | Baseline recommender evaluation | Critical | Chạy benchmarks/run_baselines.py để tạo artifact |
| 3 | Campaign_001 artifacts | Critical | Thực hiện campaign đầy đủ (cần credentials LLM/Jev) |
| 4 | Component benchmarks unified_report | Critical | Chạy scripts/evaluation/run_component_benchmarks.py (cần LLM credentials) |
| 5 | Multi-turn planner evaluation | High | Bật enable_session=true, chạy với planner agent (cần LLM credentials) |
| 6 | Git SHA provenance | High | Sửa build_run_provenance.py để populate git_sha vào reports |
| 7 | Real-LLM agent evaluation | High | Cấu hình LLM_BASE_URL/LLM_API_KEY, chạy planner benchmark |
| 8 | Real Jev evaluation | High | Cấu hình TYPESAFE_API_KEY, chạy grounding benchmark thật |
| 9 | Opik integration | Medium | Deploy Opik server, thêm @opik.track, import experiments |

## 3. Hình cần vẽ lại & Số liệu cần chạy thêm

| # | Hình/Số liệu | Trạng thái | Ghi chú |
|---|--------------|------------|---------|
| 1 | Hình 3.1 (Kiến trúc tổng thể) | Cần cập nhật | Thêm package/utils/, package/evaluation/ expanded, 5 subdirs under tools/ |
| 2 | Hình 3.2 (Pipeline 4 giai đoạn) | Cần vẽ lại | Đổi từ 3 -> 4 stages, cập nhật caption |
| 3 | Hình 3.3 (Các tầng) | Cần cập nhật | 3-tier evaluation (thay vì 4/6 bộ) |
| 4 | Bảng 3.1 (Tầng chức năng) | Cập nhật cell | Thêm package/utils/, package/evaluation/ expanded |
| 5 | Bảng 3.2 (Pipeline stages) | Cập nhật caption | Ba -> Bốn giai đoạn |
| 6 | Bảng 3.3 (Tổng quan công cụ) | Cập nhật toàn bộ | 6 canonical tools, descriptions, subdir paths |
| 7 | Bảng 3.4 (Phân loại lỗi) | Cập nhật | Canonical tool names |
| 7 | Bảng 3.6 (Hệ thống đánh giá) | Cần vẽ lại | 3-tier structure (12 groups) |
| 8 | Bảng 3.7 (Ví dụ 3.9) | Cập nhật | 5 tools, .path syntax, FilterTool added |
| 8 | Bảng 4.x (Campaign grid) | Cập nhật | 12 experiments detail |
| 9 | Bảng 6.1/6.2/6.3 | Cập nhật toàn bộ | Status updates, no week deadlines |
| 10 | Danh mục chữ viết tắt | Thay thế toàn bộ | 36 terms, -5 old tools, +17 new |
| 11 | Số liệu Chapter 5 | Cần chạy thêm | 8 items [CẦN XÁC NHẬN] |
| 12 | Component benchmark unified_report | Cần chạy | scripts/evaluation/run_component_benchmarks.py |

## 4. Việc cần làm thủ công trong Word

| # | Task | Ghi chú |
|---|------|---------|
| 1 | Cập nhật Mục lục (TOC) | Nhấn F9 -> Update entire table |
| 2 | Cập nhật Danh sách Hình (LOF) | Nhấn F9 -> Update entire table |
| 3 | Cập nhật Danh sách Bảng (LOT) | Nhấn F9 -> Update entire table |
| 4 | Kiểm tra Cross-references | Ctrl+A -> F9 để cập nhật tất cả tham chiếu |
| 5 | Format Bảng 3.3/3.4/3.6/6.1/6.2/6.3 | AutoFit -> Fixed column width, căn giữa header |
| 6 | Kiểm tra Caption Hình/Bảng | Đảm bảo numbering liên tục |
| 7 | Định dạng Abbreviations table | Table style, font size 10pt, căn lề |
| 8 | Kiểm tra Header/Footer | Đảm bảo page numbers, chapter title đúng |
| 9 | Export PDF | File -> Save As -> PDF (hoặc LibreOffice soffice --headless --convert-to pdf) |

## 5. Verification Checklist

| Check | Status | Detail |
|-------|--------|--------|
| Old tool names removed | OK | Grep: SemanticSearchTool (1), ItemCFTool (1), SQLTool (1), RecoModelTool (1), QueryTool (1) - remaining in TOC hyperlinks only |
| New tool names present | OK | SearchTool (8), SimilarTool (9), FilterTool (7), RankTool (11), LookupTool (9), MemoryTool (11) |
| Pipeline stages: 3->4 | OK | 5 occurrences replaced |
| Agent file paths fixed | PARTIAL | 0 occurrences found (may be in tables/TOC) |
| Sub-section headings 3.4.3-3.4.8 | PARTIAL | In TOC hyperlinks; body text updated |
| Chapter 5 annotations | PARTIAL | Needs manual check |
| Tables 6.1/6.2/6.3 | PARTIAL | Needs manual table cell edit |
| Abbreviations list | PARTIAL | Needs manual replacement in Word |
| Document structure | OK | 969 paragraphs, 27 tables preserved |
| PDF conversion | PENDING | Requires LibreOffice install |

## 6. Artifact Generation Commands

`ash
# 1. Candidate recall
cd src && PYTHONPATH=. python scripts/evaluation/candidate_recall.py --model itemknn --chain true --init-args {} --interactions data/interactions.parquet
# 2. Baseline recommender eval
cd src && PYTHONPATH=. python scripts/evaluation/ranking_eval.py --model all --chain true
# 3. Component benchmarks (unified report)
cd src && PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py
# 4. Campaign_001 (full grid)
cd src && PYTHONPATH=. python scripts/evaluation/run_campaign.py --campaign-config configs/evaluation/campaign.yaml
# 5. Multi-turn with planner
cd src && PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation --agents planner,planner_memory --mock false
# 6. Fix git_sha
# Edit src/package/utils/hardware.py or build_run_provenance.py to capture git SHA
`

---

**End of Report Update Log**
