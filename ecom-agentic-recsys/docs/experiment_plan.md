# Experiment Plan — PHASE 0

## 1. Mục tiêu

Không chỉ đo "hệ thống cuối có tốt không" mà phải đo **từng thành phần đóng góp gì**, theo đúng cảnh báo của Lin et al. 2026 về agent-contribution analysis.

## 2. Experiment matrix (mục XVII)

| ID | Cấu hình | Mục đích |
|---|---|---|
| E0 | Random | sanity lower-bound |
| E1 | Popularity | baseline không cá nhân hoá |
| E2 | Collaborative baseline (UserKNN/ItemKNN hoặc MF/BPR) | baseline cổ điển |
| E3 | Sequential baseline (model chọn ở Phase 5) | baseline SOTA non-LLM |
| E4 | Hybrid retrieval (collaborative + embedding) | đo chất lượng candidate generation độc lập |
| E5 | Sequential + retrieval | kết hợp 2 nguồn candidate |
| E6 | Sequential + Agent (single-agent, không memory) | đo giá trị thêm của agent layer khi chưa có memory |
| E7 | Sequential + Memory + Agent | đo giá trị thêm của memory |
| E8 | Sequential + Retrieval + Agent + Reranking | pipeline gần đầy đủ |
| E9 | Full system (tất cả module) | hệ thống cuối cùng |

## 3. Ablation (loại từng module khỏi Full system E9)

```
Full
 - Memory
 - Retrieval
 - Reranking
 - Planning (agent chạy fixed workflow, không tự quyết định tool)
 - Profile
 - Explanation
 - Multi-agent (nếu Phase 10 có triển khai)
```
Mỗi dòng ablation phải chạy trên cùng test set, cùng seed, để so sánh công bằng.

## 4. Metrics (mục XVI)

**Recommendation metrics:** Precision@K, Recall@K, HitRate@K, NDCG@K, MRR@K, MAP@K (K ∈ {5, 10, 20} — chốt cụ thể ở Phase 11 dựa theo domain).
**Bổ sung nếu phù hợp:** Coverage, Catalog Coverage, Novelty, Diversity, Serendipity.
**Agent metrics:** task success rate, constraint satisfaction rate, explanation faithfulness (evidence có thật hay hallucinate), tool selection accuracy, số lượt gọi tool, latency, token usage, cost ước tính.

## 5. Cold-start / evolving-interest evaluation (mục XVIII)

Chạy lại E3/E6/E9 riêng trên 4 nhóm user (warm/new/sparse/evolving) đã định nghĩa ở `data_specification.md` §6 — không chỉ báo cáo một số trung bình toàn tập.

## 6. Reproducibility record (mục XXII)

Mỗi experiment lưu tại `experiments/exp_XXX/` gồm: `config.yaml, metrics.json, predictions.parquet, logs/, README.md`, kèm seed, dataset version, model version, git commit, hardware, thời gian chạy.

## 7. Trạng thái Phase 0

Toàn bộ bảng trên là **kế hoạch**, chưa có số liệu thật (`BLOCKED — cần Phase 4 trở đi mới có kết quả`). Không tạo số liệu giả để lấp bảng.
