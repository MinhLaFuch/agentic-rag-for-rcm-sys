# Agent Evaluation Report

**Generated**: 2026-11-23T09:03:45.332302+00:00

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
| planner/cold_text | answer_status_ok | 0.7500 | 0.4330 |
| planner/cold_text | asked_clarification | 0.0000 | 0.0000 |
| planner/cold_text | constraint_satisfaction | 0.7450 | 0.4307 |
| planner/cold_text | first_attempt_ok | 0.7500 | 0.4330 |
| planner/cold_text | hit_rate@10 | 0.1000 | 0.3000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0306 | 0.1104 |
| planner/cold_text | mrr@10 | 0.0306 | 0.1104 |
| planner/cold_text | n_steps | 3.0000 | 0.0000 |
| planner/cold_text | ndcg@10 | 0.0466 | 0.1492 |
| planner/cold_text | precision@10 | 0.0100 | 0.0300 |
| planner/cold_text | recall@10 | 0.1000 | 0.3000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.7000 | 0.4583 |
| planner/cold_text | tool_selection_ok | 1.0000 | 0.0000 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.5500 | 0.4975 |
| planner/exclusion | asked_clarification | 0.0250 | 0.1561 |
| planner/exclusion | exclusion_compliance | 1.0000 | 0.0000 |
| planner/exclusion | first_attempt_ok | 0.5750 | 0.4943 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.9500 | 0.4975 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.5500 | 0.4975 |
| planner/exclusion | tool_selection_ok | 0.6000 | 0.4899 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 1.0000 | 0.0000 |
| planner/personalized | asked_clarification | 0.0000 | 0.0000 |
| planner/personalized | first_attempt_ok | 1.0000 | 0.0000 |
| planner/personalized | hit_rate@10 | 0.0250 | 0.1561 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0083 | 0.0520 |
| planner/personalized | mrr@10 | 0.0083 | 0.0520 |
| planner/personalized | n_steps | 3.5000 | 0.8660 |
| planner/personalized | ndcg@10 | 0.0125 | 0.0781 |
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
| answer_status_ok | 0.7566 | 0.6842 | 0.8224 |
| asked_clarification | 0.0461 | 0.0132 | 0.0789 |
| constraint_satisfaction | 0.7450 | 0.5499 | 0.9000 |
| exclusion_compliance | 1.0000 | 1.0000 | 1.0000 |
| first_attempt_ok | 0.8026 | 0.7368 | 0.8618 |
| hit_rate@10 | 0.0259 | 0.0000 | 0.0603 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0081 | 0.0000 | 0.0196 |
| mrr@10 | 0.0081 | 0.0000 | 0.0196 |
| n_steps | 3.0000 | 2.8684 | 3.1250 |
| ndcg@10 | 0.0123 | 0.0000 | 0.0301 |
| precision@10 | 0.0026 | 0.0000 | 0.0052 |
| recall@10 | 0.0259 | 0.0000 | 0.0603 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.7143 | 0.6339 | 0.7946 |
| tool_selection_ok | 0.8571 | 0.7857 | 0.9196 |

## Failure Analysis

**Total Failures**: 32

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-6**: task_success=False
- **planner:cold_text-cold-9**: task_success=False
- **planner:cold_text-cold-17**: task_success=False
- **planner:cold_text-cold-18**: task_success=False
- **planner:cold_text-cold-19**: task_success=False
- **planner:exclusion-sparse-2**: task_success=False
- **planner:exclusion-sparse-5**: task_success=False
- ... and 22 more failures
