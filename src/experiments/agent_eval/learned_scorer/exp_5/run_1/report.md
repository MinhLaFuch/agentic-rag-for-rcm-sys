# Agent Evaluation Report

**Generated**: 2026-11-22T07:52:20.256073+00:00

## Executive Summary

- **scored_rows**: 152
- **requests**: 152
- **agents**: planner
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| planner/ambiguous | answer_status_ok | 0.0000 | 0.0000 |
| planner/ambiguous | asked_clarification | 1.0000 | 0.0000 |
| planner/ambiguous | first_attempt_ok | 1.0000 | 0.0000 |
| planner/ambiguous | invented_ids | 0.0000 | 0.0000 |
| planner/ambiguous | n_steps | 0.0000 | 0.0000 |
| planner/ambiguous | reflections | 0.0000 | 0.0000 |
| planner/ambiguous | task_success | 1.0000 | 0.0000 |
| planner/ambiguous | tool_selection_ok | 1.0000 | 0.0000 |
| planner/cold_text | answer_fallback | 0.0000 | 0.0000 |
| planner/cold_text | answer_grounded | 1.0000 | 0.0000 |
| planner/cold_text | answer_status_ok | 0.7000 | 0.4583 |
| planner/cold_text | asked_clarification | 0.0000 | 0.0000 |
| planner/cold_text | constraint_satisfaction | 0.6300 | 0.4337 |
| planner/cold_text | first_attempt_ok | 0.7000 | 0.4583 |
| planner/cold_text | hit_rate@10 | 0.0500 | 0.2179 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0071 | 0.0311 |
| planner/cold_text | mrr@10 | 0.0071 | 0.0311 |
| planner/cold_text | n_steps | 3.0000 | 0.0000 |
| planner/cold_text | ndcg@10 | 0.0167 | 0.0726 |
| planner/cold_text | precision@10 | 0.0050 | 0.0218 |
| planner/cold_text | recall@10 | 0.0500 | 0.2179 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.4500 | 0.4975 |
| planner/cold_text | tool_selection_ok | 1.0000 | 0.0000 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.5250 | 0.4994 |
| planner/exclusion | asked_clarification | 0.3000 | 0.4583 |
| planner/exclusion | exclusion_compliance | 0.8095 | 0.3927 |
| planner/exclusion | first_attempt_ok | 0.7750 | 0.4176 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.2000 | 1.4697 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.4250 | 0.4943 |
| planner/exclusion | tool_selection_ok | 0.5250 | 0.4994 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.6500 | 0.4770 |
| planner/personalized | asked_clarification | 0.2750 | 0.4465 |
| planner/personalized | first_attempt_ok | 0.9250 | 0.2634 |
| planner/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0000 | 0.0000 |
| planner/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner/personalized | n_steps | 2.1000 | 1.3748 |
| planner/personalized | ndcg@10 | 0.0000 | 0.0000 |
| planner/personalized | precision@10 | 0.0000 | 0.0000 |
| planner/personalized | recall@10 | 0.0000 | 0.0000 |
| planner/personalized | reflections | 0.0000 | 0.0000 |
| planner/similar | answer_fallback | 0.0000 | 0.0000 |
| planner/similar | answer_grounded | 1.0000 | 0.0000 |
| planner/similar | answer_status_ok | 0.9500 | 0.2179 |
| planner/similar | asked_clarification | 0.0000 | 0.0000 |
| planner/similar | first_attempt_ok | 0.9500 | 0.2179 |
| planner/similar | hit_rate@10 | 0.0000 | 0.0000 |
| planner/similar | invented_ids | 0.0000 | 0.0000 |
| planner/similar | map@10 | 0.0000 | 0.0000 |
| planner/similar | mrr@10 | 0.0000 | 0.0000 |
| planner/similar | n_steps | 3.0000 | 0.0000 |
| planner/similar | ndcg@10 | 0.0000 | 0.0000 |
| planner/similar | precision@10 | 0.0000 | 0.0000 |
| planner/similar | recall@10 | 0.0000 | 0.0000 |
| planner/similar | reflections | 0.0000 | 0.0000 |
| planner/similar | task_success | 0.9500 | 0.2179 |
| planner/similar | tool_selection_ok | 1.0000 | 0.0000 |
| planner/unanswerable | answer_status_ok | 0.0000 | 0.0000 |
| planner/unanswerable | asked_clarification | 0.0000 | 0.0000 |
| planner/unanswerable | first_attempt_ok | 0.0000 | 0.0000 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 3.0000 | 0.0000 |
| planner/unanswerable | reflections | 0.0000 | 0.0000 |
| planner/unanswerable | task_success | 0.0000 | 0.0000 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.6513 | 0.5789 | 0.7237 |
| asked_clarification | 0.1908 | 0.1316 | 0.2566 |
| constraint_satisfaction | 0.6300 | 0.4450 | 0.8150 |
| exclusion_compliance | 0.8095 | 0.6190 | 0.9524 |
| first_attempt_ok | 0.8289 | 0.7762 | 0.8882 |
| hit_rate@10 | 0.0086 | 0.0000 | 0.0259 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0012 | 0.0000 | 0.0037 |
| mrr@10 | 0.0012 | 0.0000 | 0.0037 |
| n_steps | 2.4342 | 2.2368 | 2.6118 |
| ndcg@10 | 0.0029 | 0.0000 | 0.0086 |
| precision@10 | 0.0009 | 0.0000 | 0.0026 |
| recall@10 | 0.0086 | 0.0000 | 0.0259 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.6250 | 0.5357 | 0.7143 |
| tool_selection_ok | 0.8304 | 0.7589 | 0.8931 |

## Failure Analysis

**Total Failures**: 42

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-2**: task_success=False
- **planner:cold_text-cold-5**: task_success=False
- **planner:cold_text-cold-7**: task_success=False
- **planner:cold_text-cold-9**: task_success=False
- **planner:cold_text-cold-12**: task_success=False
- **planner:cold_text-cold-13**: task_success=False
- **planner:cold_text-cold-16**: task_success=False
- ... and 32 more failures
