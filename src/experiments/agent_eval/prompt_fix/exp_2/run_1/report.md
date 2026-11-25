# Agent Evaluation Report

**Generated**: 2026-11-23T18:13:59.870297+00:00

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
| planner/cold_text | answer_status_ok | 0.8500 | 0.3571 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.7800 | 0.3669 |
| planner/cold_text | first_attempt_ok | 0.9000 | 0.3000 |
| planner/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0000 | 0.0000 |
| planner/cold_text | mrr@10 | 0.0000 | 0.0000 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| planner/cold_text | precision@10 | 0.0000 | 0.0000 |
| planner/cold_text | recall@10 | 0.0000 | 0.0000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.6500 | 0.4770 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.3500 | 0.4770 |
| planner/exclusion | asked_clarification | 0.5250 | 0.4994 |
| planner/exclusion | exclusion_compliance | 0.7857 | 0.4103 |
| planner/exclusion | first_attempt_ok | 0.8000 | 0.4000 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 1.5000 | 1.5969 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.2500 | 0.4330 |
| planner/exclusion | tool_selection_ok | 0.3750 | 0.4841 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.7000 | 0.4583 |
| planner/personalized | asked_clarification | 0.1000 | 0.3000 |
| planner/personalized | first_attempt_ok | 0.8000 | 0.4000 |
| planner/personalized | hit_rate@10 | 0.0250 | 0.1561 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0063 | 0.0390 |
| planner/personalized | mrr@10 | 0.0063 | 0.0390 |
| planner/personalized | n_steps | 2.8500 | 1.2359 |
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
| planner/unanswerable | asked_clarification | 0.1667 | 0.3727 |
| planner/unanswerable | first_attempt_ok | 0.1667 | 0.3727 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 2.1667 | 1.2134 |
| planner/unanswerable | reflections | 0.0000 | 0.0000 |
| planner/unanswerable | task_success | 0.3333 | 0.4714 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.6382 | 0.5526 | 0.7171 |
| asked_clarification | 0.2171 | 0.1579 | 0.2829 |
| constraint_satisfaction | 0.7800 | 0.6100 | 0.9351 |
| exclusion_compliance | 0.7857 | 0.5714 | 1.0000 |
| first_attempt_ok | 0.8355 | 0.7763 | 0.8947 |
| hit_rate@10 | 0.0086 | 0.0000 | 0.0261 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0022 | 0.0000 | 0.0065 |
| mrr@10 | 0.0022 | 0.0000 | 0.0065 |
| n_steps | 2.3947 | 2.1776 | 2.5988 |
| ndcg@10 | 0.0037 | 0.0000 | 0.0111 |
| precision@10 | 0.0009 | 0.0000 | 0.0026 |
| recall@10 | 0.0086 | 0.0000 | 0.0259 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.6161 | 0.5179 | 0.7054 |
| tool_selection_ok | 0.7679 | 0.6875 | 0.8482 |

## Failure Analysis

**Total Failures**: 43

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-2**: task_success=False
- **planner:cold_text-cold-3**: task_success=False
- **planner:cold_text-cold-10**: task_success=False
- **planner:cold_text-cold-12**: task_success=False
- **planner:cold_text-cold-14**: task_success=False
- **planner:cold_text-cold-16**: task_success=False
- **planner:exclusion-sparse-0**: task_success=False
- ... and 33 more failures
