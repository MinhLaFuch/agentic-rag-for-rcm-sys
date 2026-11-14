# Ablation scope — campaign_001

Phạm vi ablation **đã thực sự đo được** và những gì **không claim**.

## Arms (đều inference_mode=template, dataset multi_domain/validation, per_segment=20, seed=42)

| Arm | Config | Experiment |
|---|---|---|
| Baseline ItemKNN | agent=`baseline`, không LLM | campaign_001 exp_1 |
| planner, reflect=0 | agent=`planner` | exp_5 |
| planner, reflect=1 | agent=`planner` | exp_6 |
| planner_memory, reflect=0 (−Reflect vs Full) | agent=`planner_memory` | exp_9 |
| **Full** = planner_memory, reflect=1 | agent=`planner_memory` | exp_10 |
| **−Rank** = Full − RankTool | `exclude_tools: [RankTool]` | campaign_001_ablation_norank exp_1 (CHƯA CHẠY — chờ user) |

2×2 planner-memory × reflect (template): exp_5 / exp_6 / exp_9 / exp_10.

Biến thể llm (exp_7/8/11/12) tồn tại nhưng **không nằm trong ablation scope** —
inference_mode là một trục khác, không suy diễn chéo sang template.

## Tool subset (mới)

- `agent_eval.exclude_tools: []` trong `configs/agent/agent_eval.yaml` — danh sách
  tên class tool bị loại khỏi planner/planner_memory; validate qua
  `validate_tool_names` (`package/agents/toolkit/agent_tools.py`).
- Campaign grid hỗ trợ `exclude_tools` trong `agent_config`
  (`campaign_runner._AGENT_CONFIG_KEYS` → overlay `agent_eval.exclude_tools`).
- `exclude_tools` đi vào `resume_identity` qua `_resume_agent_config` → subset
  khác = protocol_hash khác = không lẫn trajectory.
- Config sẵn cho arm −Rank: `configs/evaluation/campaign_ablation_norank.yaml`
  (1 experiment, multi_turn=false để tiết kiệm LLM calls — ablation chỉ so
  single-turn scored.jsonl).

## Lệnh chạy (PowerShell / Bash)

Dry-run (đã verify):

```powershell
cd src; $env:PYTHONPATH="."
python scripts/evaluation/run_campaign.py --campaign-config configs/evaluation/campaign_ablation_norank.yaml --dry-run
```
```bash
cd src && PYTHONPATH=. python scripts/evaluation/run_campaign.py --campaign-config configs/evaluation/campaign_ablation_norank.yaml --dry-run
```

Chạy thật arm −Rank (1 experiment ≈ 132 requests × ~1.3 plan attempts ≈
**~170–200 LLM calls**, runtime kỳ vọng tương đương exp_10 ~600–1400s;
KHÔNG multi_turn):

```powershell
cd src; $env:PYTHONPATH="."; $env:LLM_BASE_URL="..."; $env:LLM_API_KEY="..."
python scripts/evaluation/run_campaign.py --campaign-config configs/evaluation/campaign_ablation_norank.yaml 2>&1 | Tee-Object -FilePath "experiments/logs/$(Get-Date -Format yyyyMMdd-HHmm)-ablation_norank.txt"
```
```bash
cd src && export PYTHONPATH=. LLM_BASE_URL=... LLM_API_KEY=...
python scripts/evaluation/run_campaign.py --campaign-config configs/evaluation/campaign_ablation_norank.yaml 2>&1 | tee "experiments/logs/$(date +%Y%m%d-%H%M)-ablation_norank.txt"
```

Phân tích (không LLM — đã chạy thử trên dữ liệu thật):

```powershell
cd src; $env:PYTHONPATH="."
python scripts/experiments/compare_experiments.py
python scripts/experiments/pairwise_ablation.py --a <scored_A.jsonl> --a-agent planner --b <scored_B.jsonl> --b-agent planner_memory --out experiments/agent_eval/ablation/<ten>.md
```
```bash
cd src && PYTHONPATH=. python scripts/experiments/compare_experiments.py
PYTHONPATH=. python scripts/experiments/pairwise_ablation.py --a <scored_A.jsonl> --a-agent planner --b <scored_B.jsonl> --b-agent planner_memory --out experiments/agent_eval/ablation/<ten>.md
```

## Đã chạy thử (không cần LLM)

- `compare_experiments.py`: 4 contrasts → `experiments/agent_eval/ablation/{reflect_effect_planner_memory, reflect_effect_planner, memory_effect_reflect1, baseline_vs_full_agent}/`.
- `pairwise_ablation.py` planner(exp_6) vs planner_memory(exp_10) →
  `experiments/agent_eval/ablation/pairwise_planner_vs_memory.md`;
  personalized `task_success` n_effective=0 (planner=None → drop đúng,
  không tính False).

## Không claim

- **Không** claim "agentic RAG đóng góp X điểm so với pipeline non-agent" —
  baseline ItemKNN ≠ non-agent RAG pipeline; đây chỉ là 1 baseline recommender.
- **Không** claim ablation `−Retrieval`, `−Planning`, `−Profile`,
  `−Explanation`, `−Multi-agent`, hay E0–E9 (plan cũ đã xóa).
- Retrieval/embedding quality thuộc effort khác; ablation này chỉ đo
  **agent-layer**: reflect, memory, rank.
- Baseline `task_success=160/160` trên các kind nó xử lý được — tiêu chí
  "đủ item trả về" quá dễ; mọi so sánh baseline-vs-agent phải đọc kèm
  `answer_grounded`/metric retrieval, không chỉ task_success.
- Multi-turn metrics **không** vào paired comparisons (theo thiết kế campaign).
