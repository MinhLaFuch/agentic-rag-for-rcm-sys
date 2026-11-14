# planner vs planner_memory

- A: `planner` (132 requests)
- B: `planner_memory` (132 requests)
- confidence: 0.95

| kind | metric | n_eff | A | B | diff / McNemar |
|---|---|---|---|---|---|
| ambiguous | task_success | 6 | 1.000 [0.610,1.000] | 1.000 [0.610,1.000] | McNemar n/a (b+c<10) |
| ambiguous | first_attempt_ok | 6 | 1.000 [0.610,1.000] | 1.000 [0.610,1.000] | McNemar n/a (b+c<10) |
| ambiguous | tool_selection_ok | 6 | 1.000 [0.610,1.000] | 1.000 [0.610,1.000] | McNemar n/a (b+c<10) |
| ambiguous | recall@10 | 0 | — | — | all pairs dropped (None) |
| ambiguous | ndcg@10 | 0 | — | — | all pairs dropped (None) |
| ambiguous | mrr@10 | 0 | — | — | all pairs dropped (None) |
| exclusion | task_success | 40 | 0.925 [0.801,0.974] | 0.950 [0.835,0.986] | McNemar n/a (b+c<10) |
| exclusion | first_attempt_ok | 40 | 0.975 [0.871,0.996] | 0.700 [0.546,0.819] | McNemar b=12 c=1 p=0.01 |
| exclusion | tool_selection_ok | 40 | 0.275 [0.161,0.428] | 0.425 [0.285,0.578] | McNemar b=6 c=12 p=1.0 |
| exclusion | recall@10 | 21 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| exclusion | ndcg@10 | 21 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| exclusion | mrr@10 | 21 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| personalized | task_success | 0 | — | — | all pairs dropped (None) |
| personalized | first_attempt_ok | 40 | 0.500 [0.352,0.648] | 0.575 [0.422,0.715] | McNemar b=8 c=11 p=1.0 |
| personalized | tool_selection_ok | 0 | — | — | all pairs dropped (None) |
| personalized | recall@10 | 40 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| personalized | ndcg@10 | 40 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| personalized | mrr@10 | 40 | 0.0000 | 0.0000 | diff=+0.0000 CI[+0.0000,+0.0000] |
| similar | task_success | 40 | 1.000 [0.912,1.000] | 1.000 [0.912,1.000] | McNemar n/a (b+c<10) |
| similar | first_attempt_ok | 40 | 1.000 [0.912,1.000] | 1.000 [0.912,1.000] | McNemar n/a (b+c<10) |
| similar | tool_selection_ok | 40 | 1.000 [0.912,1.000] | 1.000 [0.912,1.000] | McNemar n/a (b+c<10) |
| similar | recall@10 | 40 | 0.0063 | 0.0063 | diff=+0.0000 CI[+0.0000,+0.0000] |
| similar | ndcg@10 | 40 | 0.0062 | 0.0062 | diff=+0.0000 CI[+0.0000,+0.0000] |
| similar | mrr@10 | 40 | 0.0125 | 0.0125 | diff=+0.0000 CI[+0.0000,+0.0000] |
| unanswerable | task_success | 6 | 1.000 [0.610,1.000] | 1.000 [0.610,1.000] | McNemar n/a (b+c<10) |
| unanswerable | first_attempt_ok | 6 | 0.000 [0.000,0.390] | 0.000 [0.000,0.390] | McNemar n/a (b+c<10) |
| unanswerable | tool_selection_ok | 6 | 1.000 [0.610,1.000] | 1.000 [0.610,1.000] | McNemar n/a (b+c<10) |
| unanswerable | recall@10 | 0 | — | — | all pairs dropped (None) |
| unanswerable | ndcg@10 | 0 | — | — | all pairs dropped (None) |
| unanswerable | mrr@10 | 0 | — | — | all pairs dropped (None) |
