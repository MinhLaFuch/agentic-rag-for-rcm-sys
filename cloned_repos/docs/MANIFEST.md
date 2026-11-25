# MANIFEST — cloned reference repos

Clone: `git clone --depth 1` + `GIT_LFS_SKIP_SMUDGE=1`, ngày 2026-11-25. Tất cả URL trong brief đều tồn tại và đúng repo của paper tương ứng (README nêu tên paper/tác giả/venue).

| # | Repo | URL | Commit | Commit cuối | License | Dung lượng | Ngôn ngữ | Code thật? | Eval script? | GPU/weights/API key? |
|---|------|-----|--------|-------------|---------|-----------|----------|-----------|--------------|----------------------|
| 1 | iAgent / i²Agent | https://github.com/agiresearch/iAgent | `e546d17` | 2025-05-23 | Không có file license | 467K | Python | Có, nhưng tối giản (2 file .py) | Không có script riêng — metric tính inline trong `main_iagent_mp.py` | OpenAI API key; dataset InstructRec tải ngoài (gdown); không GPU |
| 2 | MemRec | https://github.com/rutgerswiselab/memrec | `58d9031` | 2026-07-28 | Không có file license | 609K | Python | Có (~6.3k dòng, src/ đầy đủ) | `scripts/run_train.py` + `src/train/trainer_memrec.py` | LLM API (Azure OpenAI/vLLM…); PyTorch; dataset `.inter` tải ngoài; eval-user JSON mẫu có sẵn |
| 3 | ItemRAG | https://github.com/kswoo97/ItemRAG | `45f41b1` | 2026-04-11 | Không có file license | 1.5M | Python | Có (4 script, ~440 dòng) | `evaluation.py` (step 4) | GPU cho embedding step1; OpenAI API key cho step3/4; dataset pickle tải ngoài (Dropbox) |
| 4 | BiLLP | https://github.com/jizhi-zhang/BiLLP | `ced0214` | 2024-09-24 | MIT (`LICENSE`) | 300M | Python | Có (fork FireAct + rec env) | `generation_rec_agents.py --evaluate` | OpenAI API key; SERPAPI key (chỉ task QA); LLaMA grounding weights + `*_embedding_task.pt`; data `.npy` tải ngoài |
| 5 | T-PRA | https://github.com/gnaWeinrE/T-PRA | `8730e41` | 2025-09-15 | Không có file license | 64M | Python | Có (~3k dòng) | `generation_rec_agents.py` + `tpra_start.sh` (train+eval) | GPU; LLaMA-3.1-8B weights; LLaMA-Factory (clone ngoài); dataset zip tải ngoài |
| 6 | VibeMus | https://github.com/tuteng0915/VibeMus | `f92f7d9` | 2026-06-01 | MIT (`LICENSE`) | 148M | Python | Có (app hoàn chỉnh) | `experiments/evaluation.py`, `dialog_eval.py` (eval nhạc, không phải recsys) | GPU; ACE-Step 3.5B weights (HF); DashScope API key; `acestep` cài từ git trong requirements |
| 7 | RecAI (InteRecAgent) | https://github.com/microsoft/RecAI | `0959ecb` | 2026-01-27 | MIT (`LICENSE.txt`) | 49M | Python (monorepo) | Có — InteRecAgent ở `RecAI/InteRecAgent/` (~6k dòng llm4crs) | `InteRecAgent/eval/one_turn_eval.py`, `one_turn_eval_ranking.py`, `user_simulator.py` + `eval_*.sh` | OpenAI/Azure API key; `resources/<domain>/` tải ngoài (không có trong repo); `unirec` package + model checkpoint cho RankingTool; torch + sentence-transformers (gte-base) |

## Ghi chú

- Không repo nào là stub: cả 7 đều có code chạy được về mặt cấu trúc. iAgent là nhỏ nhất và đơn giản nhất (về bản chất là LLM re-ranker 2 bước trên candidate list có sẵn trong dataset).
- RecAI là monorepo 6 project; chỉ `InteRecAgent/` liên quan task này (Knowledge_Plugin, RecLM-*, RecExplainer là các project khác — RecLM-gen/uni cung cấp ranking model checkpoint cho InteRecAgent).
- `RecAI/InteRecAgent` tham chiếu `../UniRec/` (`environ_variables.py:10`) nhưng thư mục đó **không có trong repo** — ranking model nạp qua `unirec` pip package (`requirements.txt`: `unirec>=0.0.1a4`) và checkpoint per-domain trong `resources/`.
- `resources/` (item table parquet/csv, col-desc json, model ckpt, item_sim .npt, settings.json) **không nằm trong repo** — README hướng dẫn tải từ GoogleDrive/RecDrive.
