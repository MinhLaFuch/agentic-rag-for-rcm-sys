# Agent Evaluation Report

**Generated**: 2026-11-18T22:15:07.207523+00:00

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
| planner/cold_text | answer_status_ok | 0.4000 | 0.4899 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.3500 | 0.4522 |
| planner/cold_text | first_attempt_ok | 0.4500 | 0.4975 |
| planner/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0000 | 0.0000 |
| planner/cold_text | mrr@10 | 0.0000 | 0.0000 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| planner/cold_text | precision@10 | 0.0000 | 0.0000 |
| planner/cold_text | recall@10 | 0.0000 | 0.0000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.2500 | 0.4330 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.4750 | 0.4994 |
| planner/exclusion | asked_clarification | 0.2250 | 0.4176 |
| planner/exclusion | exclusion_compliance | 0.8316 | 0.3450 |
| planner/exclusion | first_attempt_ok | 0.5500 | 0.4975 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.2500 | 1.2990 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.2250 | 0.4176 |
| planner/exclusion | task_success | 0.3250 | 0.4684 |
| planner/exclusion | tool_selection_ok | 0.4500 | 0.4975 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.6750 | 0.4684 |
| planner/personalized | asked_clarification | 0.3250 | 0.4684 |
| planner/personalized | first_attempt_ok | 0.9500 | 0.2179 |
| planner/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0000 | 0.0000 |
| planner/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner/personalized | n_steps | 2.0250 | 1.4051 |
| planner/personalized | ndcg@10 | 0.0000 | 0.0000 |
| planner/personalized | precision@10 | 0.0000 | 0.0000 |
| planner/personalized | recall@10 | 0.0000 | 0.0000 |
| planner/personalized | reflections | 0.0500 | 0.2179 |
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
| planner/similar | reflections | 0.0500 | 0.2179 |
| planner/similar | task_success | 0.9500 | 0.2179 |
| planner/similar | tool_selection_ok | 1.0000 | 0.0000 |
| planner/unanswerable | answer_status_ok | 0.0000 | 0.0000 |
| planner/unanswerable | asked_clarification | 0.8333 | 0.3727 |
| planner/unanswerable | first_attempt_ok | 0.5000 | 0.5000 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 0.5000 | 1.1180 |
| planner/unanswerable | reflections | 0.5000 | 0.5000 |
| planner/unanswerable | task_success | 0.8333 | 0.3727 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

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
| answer_status_ok | 0.6053 | 0.5329 | 0.6908 |
| asked_clarification | 0.2237 | 0.1579 | 0.2896 |
| constraint_satisfaction | 0.3500 | 0.1500 | 0.5451 |
| exclusion_compliance | 0.8316 | 0.6632 | 0.9579 |
| first_attempt_ok | 0.7632 | 0.6974 | 0.8289 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| n_steps | 2.3092 | 2.1051 | 2.5066 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| reflections | 0.1053 | 0.0592 | 0.1515 |
| task_success | 0.5982 | 0.5089 | 0.6786 |
| tool_selection_ok | 0.7946 | 0.7143 | 0.8571 |

## Failure Analysis

**Total Failures**: 45

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-1**: task_success=False
- **planner:cold_text-cold-3**: task_success=False
- **planner:cold_text-cold-4**: task_success=False
- **planner:cold_text-cold-5**: task_success=False
- **planner:cold_text-cold-7**: task_success=False
- **planner:cold_text-cold-10**: task_success=False
- **planner:cold_text-cold-11**: task_success=False
- ... and 35 more failures
