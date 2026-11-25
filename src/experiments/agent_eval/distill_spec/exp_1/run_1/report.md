# Agent Evaluation Report

**Generated**: 2026-11-24T08:00:24.198936+00:00

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
| planner/cold_text | answer_status_ok | 1.0000 | 0.0000 |
| planner/cold_text | asked_clarification | 0.0000 | 0.0000 |
| planner/cold_text | constraint_satisfaction | 1.0000 | 0.0000 |
| planner/cold_text | first_attempt_ok | 1.0000 | 0.0000 |
| planner/cold_text | hit_rate@10 | 0.1000 | 0.3000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0225 | 0.0680 |
| planner/cold_text | mrr@10 | 0.0225 | 0.0680 |
| planner/cold_text | n_steps | 3.0000 | 0.0000 |
| planner/cold_text | ndcg@10 | 0.0409 | 0.1228 |
| planner/cold_text | precision@10 | 0.0100 | 0.0300 |
| planner/cold_text | recall@10 | 0.1000 | 0.3000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 1.0000 | 0.0000 |
| planner/cold_text | tool_selection_ok | 1.0000 | 0.0000 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.4750 | 0.4994 |
| planner/exclusion | asked_clarification | 0.1750 | 0.3800 |
| planner/exclusion | exclusion_compliance | 0.9947 | 0.0223 |
| planner/exclusion | first_attempt_ok | 0.6500 | 0.4770 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.5000 | 1.1832 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.4500 | 0.4975 |
| planner/exclusion | tool_selection_ok | 0.5500 | 0.4975 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.9750 | 0.1561 |
| planner/personalized | asked_clarification | 0.0000 | 0.0000 |
| planner/personalized | first_attempt_ok | 0.9750 | 0.1561 |
| planner/personalized | hit_rate@10 | 0.0250 | 0.1561 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0063 | 0.0390 |
| planner/personalized | mrr@10 | 0.0063 | 0.0390 |
| planner/personalized | n_steps | 3.4250 | 0.8027 |
| planner/personalized | ndcg@10 | 0.0108 | 0.0672 |
| planner/personalized | precision@10 | 0.0025 | 0.0156 |
| planner/personalized | recall@10 | 0.0250 | 0.1561 |
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
| answer_status_ok | 0.7632 | 0.6974 | 0.8289 |
| asked_clarification | 0.0855 | 0.0461 | 0.1316 |
| constraint_satisfaction | 1.0000 | 1.0000 | 1.0000 |
| exclusion_compliance | 0.9947 | 0.9842 | 1.0000 |
| first_attempt_ok | 0.8487 | 0.7895 | 0.9013 |
| hit_rate@10 | 0.0259 | 0.0000 | 0.0603 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0060 | 0.0000 | 0.0138 |
| mrr@10 | 0.0060 | 0.0000 | 0.0129 |
| n_steps | 2.8618 | 2.6972 | 3.0132 |
| ndcg@10 | 0.0108 | 0.0000 | 0.0256 |
| precision@10 | 0.0026 | 0.0000 | 0.0060 |
| recall@10 | 0.0259 | 0.0000 | 0.0603 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.7321 | 0.6429 | 0.8125 |
| tool_selection_ok | 0.8393 | 0.7679 | 0.9018 |

## Failure Analysis

**Total Failures**: 30

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:exclusion-sparse-2**: task_success=False
- **planner:exclusion-sparse-3**: task_success=False
- **planner:exclusion-sparse-4**: task_success=False
- **planner:exclusion-sparse-10**: task_success=False
- **planner:exclusion-sparse-11**: task_success=False
- **planner:exclusion-sparse-12**: task_success=False
- **planner:exclusion-sparse-13**: task_success=False
- **planner:exclusion-sparse-16**: task_success=False
- ... and 20 more failures
