# Agent Evaluation Report

**Generated**: 2026-11-24T09:10:33.507324+00:00

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
| planner/cold_text | answer_status_ok | 0.9000 | 0.3000 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.9000 | 0.3000 |
| planner/cold_text | first_attempt_ok | 0.9500 | 0.2179 |
| planner/cold_text | hit_rate@10 | 0.1000 | 0.3000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0225 | 0.0680 |
| planner/cold_text | mrr@10 | 0.0225 | 0.0680 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0409 | 0.1228 |
| planner/cold_text | precision@10 | 0.0100 | 0.0300 |
| planner/cold_text | recall@10 | 0.1000 | 0.3000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.9000 | 0.3000 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.5250 | 0.4994 |
| planner/exclusion | asked_clarification | 0.3000 | 0.4583 |
| planner/exclusion | exclusion_compliance | 1.0000 | 0.0000 |
| planner/exclusion | first_attempt_ok | 0.8000 | 0.4000 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.1500 | 1.4239 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.5000 | 0.5000 |
| planner/exclusion | tool_selection_ok | 0.5500 | 0.4975 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.1250 | 0.3307 |
| planner/personalized | asked_clarification | 0.0000 | 0.0000 |
| planner/personalized | first_attempt_ok | 0.1250 | 0.3307 |
| planner/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0000 | 0.0000 |
| planner/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner/personalized | n_steps | 4.4250 | 0.7031 |
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
| planner/unanswerable | asked_clarification | 0.3333 | 0.4714 |
| planner/unanswerable | first_attempt_ok | 0.3333 | 0.4714 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 2.0000 | 1.4142 |
| planner/unanswerable | reflections | 0.0000 | 0.0000 |
| planner/unanswerable | task_success | 0.3333 | 0.4714 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.5395 | 0.4605 | 0.6250 |
| asked_clarification | 0.1382 | 0.0855 | 0.1974 |
| constraint_satisfaction | 0.9000 | 0.7500 | 1.0000 |
| exclusion_compliance | 1.0000 | 1.0000 | 1.0000 |
| first_attempt_ok | 0.6711 | 0.5987 | 0.7434 |
| hit_rate@10 | 0.0172 | 0.0000 | 0.0431 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0039 | 0.0000 | 0.0099 |
| mrr@10 | 0.0039 | 0.0000 | 0.0103 |
| n_steps | 2.9737 | 2.7696 | 3.1908 |
| ndcg@10 | 0.0070 | 0.0000 | 0.0178 |
| precision@10 | 0.0017 | 0.0000 | 0.0043 |
| recall@10 | 0.0172 | 0.0000 | 0.0431 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.7500 | 0.6696 | 0.8304 |
| tool_selection_ok | 0.8304 | 0.7589 | 0.8929 |

## Failure Analysis

**Total Failures**: 28

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-19**: task_success=False
- **planner:exclusion-sparse-1**: task_success=False
- **planner:exclusion-sparse-2**: task_success=False
- **planner:exclusion-sparse-4**: task_success=False
- **planner:exclusion-sparse-5**: task_success=False
- **planner:exclusion-sparse-9**: task_success=False
- **planner:exclusion-sparse-13**: task_success=False
- ... and 18 more failures
