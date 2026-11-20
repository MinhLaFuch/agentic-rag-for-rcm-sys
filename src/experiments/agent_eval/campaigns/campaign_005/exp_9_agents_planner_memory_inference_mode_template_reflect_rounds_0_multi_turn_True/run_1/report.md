# Agent Evaluation Report

**Generated**: 2026-11-18T23:07:25.836142+00:00

## Executive Summary

- **scored_rows**: 152
- **requests**: 152
- **agents**: planner_memory
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| planner_memory/ambiguous | answer_status_ok | 0.0000 | 0.0000 |
| planner_memory/ambiguous | asked_clarification | 1.0000 | 0.0000 |
| planner_memory/ambiguous | first_attempt_ok | 1.0000 | 0.0000 |
| planner_memory/ambiguous | invented_ids | 0.0000 | 0.0000 |
| planner_memory/ambiguous | n_steps | 0.0000 | 0.0000 |
| planner_memory/ambiguous | reflections | 0.0000 | 0.0000 |
| planner_memory/ambiguous | task_success | 1.0000 | 0.0000 |
| planner_memory/ambiguous | tool_selection_ok | 1.0000 | 0.0000 |
| planner_memory/cold_text | answer_fallback | 0.0000 | 0.0000 |
| planner_memory/cold_text | answer_grounded | 1.0000 | 0.0000 |
| planner_memory/cold_text | answer_status_ok | 0.1500 | 0.3571 |
| planner_memory/cold_text | asked_clarification | 0.0000 | 0.0000 |
| planner_memory/cold_text | constraint_satisfaction | 0.1450 | 0.3457 |
| planner_memory/cold_text | first_attempt_ok | 0.1500 | 0.3571 |
| planner_memory/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner_memory/cold_text | map@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | mrr@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | n_steps | 3.0000 | 0.0000 |
| planner_memory/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | precision@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | recall@10 | 0.0000 | 0.0000 |
| planner_memory/cold_text | reflections | 0.0000 | 0.0000 |
| planner_memory/cold_text | task_success | 0.1000 | 0.3000 |
| planner_memory/cold_text | tool_selection_ok | 1.0000 | 0.0000 |
| planner_memory/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner_memory/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner_memory/exclusion | answer_status_ok | 0.4500 | 0.4975 |
| planner_memory/exclusion | asked_clarification | 0.0250 | 0.1561 |
| planner_memory/exclusion | exclusion_compliance | 0.9167 | 0.2409 |
| planner_memory/exclusion | first_attempt_ok | 0.4500 | 0.4975 |
| planner_memory/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner_memory/exclusion | map@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | n_steps | 3.6000 | 0.9434 |
| planner_memory/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner_memory/exclusion | reflections | 0.0000 | 0.0000 |
| planner_memory/exclusion | task_success | 0.3750 | 0.4841 |
| planner_memory/exclusion | tool_selection_ok | 0.4000 | 0.4899 |
| planner_memory/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner_memory/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner_memory/personalized | answer_status_ok | 0.8000 | 0.4000 |
| planner_memory/personalized | asked_clarification | 0.0000 | 0.0000 |
| planner_memory/personalized | first_attempt_ok | 0.8000 | 0.4000 |
| planner_memory/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | invented_ids | 0.0000 | 0.0000 |
| planner_memory/personalized | map@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | n_steps | 4.0000 | 0.0000 |
| planner_memory/personalized | ndcg@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | precision@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | recall@10 | 0.0000 | 0.0000 |
| planner_memory/personalized | reflections | 0.0000 | 0.0000 |
| planner_memory/personalized | task_success | 0.8000 | 0.4000 |
| planner_memory/personalized | tool_selection_ok | 0.2000 | 0.4000 |
| planner_memory/similar | answer_fallback | 0.0000 | 0.0000 |
| planner_memory/similar | answer_grounded | 1.0000 | 0.0000 |
| planner_memory/similar | answer_status_ok | 0.9500 | 0.2179 |
| planner_memory/similar | asked_clarification | 0.0000 | 0.0000 |
| planner_memory/similar | first_attempt_ok | 0.9500 | 0.2179 |
| planner_memory/similar | hit_rate@10 | 0.0000 | 0.0000 |
| planner_memory/similar | invented_ids | 0.0000 | 0.0000 |
| planner_memory/similar | map@10 | 0.0000 | 0.0000 |
| planner_memory/similar | mrr@10 | 0.0000 | 0.0000 |
| planner_memory/similar | n_steps | 3.0000 | 0.0000 |
| planner_memory/similar | ndcg@10 | 0.0000 | 0.0000 |
| planner_memory/similar | precision@10 | 0.0000 | 0.0000 |
| planner_memory/similar | recall@10 | 0.0000 | 0.0000 |
| planner_memory/similar | reflections | 0.0000 | 0.0000 |
| planner_memory/similar | task_success | 0.9500 | 0.2179 |
| planner_memory/similar | tool_selection_ok | 1.0000 | 0.0000 |
| planner_memory/unanswerable | answer_status_ok | 0.0000 | 0.0000 |
| planner_memory/unanswerable | asked_clarification | 0.0000 | 0.0000 |
| planner_memory/unanswerable | first_attempt_ok | 0.0000 | 0.0000 |
| planner_memory/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner_memory/unanswerable | n_steps | 3.0000 | 0.0000 |
| planner_memory/unanswerable | reflections | 0.0000 | 0.0000 |
| planner_memory/unanswerable | task_success | 0.0000 | 0.0000 |
| planner_memory/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Multi-turn Analysis

- **Turn Success Rate**: 100.00%
- **Conversation Success Rate**: 100.00%
- **Context Retention**: 1.0000

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.5987 | 0.5197 | 0.6712 |
| asked_clarification | 0.0461 | 0.0197 | 0.0789 |
| constraint_satisfaction | 0.1450 | 0.0000 | 0.2950 |
| exclusion_compliance | 0.9167 | 0.8000 | 1.0000 |
| first_attempt_ok | 0.6382 | 0.5592 | 0.7105 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| n_steps | 3.3026 | 3.1447 | 3.4344 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.6118 | 0.5329 | 0.6908 |
| tool_selection_ok | 0.6316 | 0.5526 | 0.7039 |

## Failure Analysis

**Total Failures**: 59

- **planner_memory:similar-sparse-14**: task_success=False
- **planner_memory:similar-warm-8**: task_success=False
- **planner_memory:personalized-sparse-8**: task_success=False
- **planner_memory:personalized-sparse-9**: task_success=False
- **planner_memory:personalized-sparse-12**: task_success=False
- **planner_memory:personalized-warm-1**: task_success=False
- **planner_memory:personalized-warm-3**: task_success=False
- **planner_memory:personalized-warm-6**: task_success=False
- **planner_memory:personalized-warm-8**: task_success=False
- **planner_memory:personalized-warm-12**: task_success=False
- ... and 49 more failures
