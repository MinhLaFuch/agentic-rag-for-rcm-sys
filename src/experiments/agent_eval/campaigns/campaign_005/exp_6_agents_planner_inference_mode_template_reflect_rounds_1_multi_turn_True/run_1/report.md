# Agent Evaluation Report

**Generated**: 2026-11-18T20:11:34.395208+00:00

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
| planner/cold_text | answer_status_ok | 0.6000 | 0.4899 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.5300 | 0.4518 |
| planner/cold_text | first_attempt_ok | 0.6500 | 0.4770 |
| planner/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0000 | 0.0000 |
| planner/cold_text | mrr@10 | 0.0000 | 0.0000 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| planner/cold_text | precision@10 | 0.0000 | 0.0000 |
| planner/cold_text | recall@10 | 0.0000 | 0.0000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.3000 | 0.4583 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.2750 | 0.4465 |
| planner/exclusion | asked_clarification | 0.4250 | 0.4943 |
| planner/exclusion | exclusion_compliance | 0.9667 | 0.0850 |
| planner/exclusion | first_attempt_ok | 0.6000 | 0.4899 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0250 | 0.1561 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 1.7500 | 1.5124 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.1500 | 0.3571 |
| planner/exclusion | task_success | 0.2500 | 0.4330 |
| planner/exclusion | tool_selection_ok | 0.3500 | 0.4770 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.6000 | 0.4899 |
| planner/personalized | asked_clarification | 0.4000 | 0.4899 |
| planner/personalized | first_attempt_ok | 1.0000 | 0.0000 |
| planner/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0000 | 0.0000 |
| planner/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner/personalized | n_steps | 1.8000 | 1.4697 |
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
| planner/similar | reflections | 0.0500 | 0.2179 |
| planner/similar | task_success | 0.9500 | 0.2179 |
| planner/similar | tool_selection_ok | 1.0000 | 0.0000 |
| planner/unanswerable | answer_status_ok | 0.0000 | 0.0000 |
| planner/unanswerable | asked_clarification | 0.6667 | 0.4714 |
| planner/unanswerable | first_attempt_ok | 0.1667 | 0.3727 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 0.3333 | 0.4714 |
| planner/unanswerable | reflections | 0.8333 | 0.3727 |
| planner/unanswerable | task_success | 1.0000 | 0.0000 |
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
| answer_status_ok | 0.5592 | 0.4803 | 0.6382 |
| asked_clarification | 0.2895 | 0.2171 | 0.3618 |
| constraint_satisfaction | 0.5300 | 0.3250 | 0.7200 |
| exclusion_compliance | 0.9667 | 0.9167 | 1.0000 |
| first_attempt_ok | 0.8026 | 0.7368 | 0.8618 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| invented_ids | 0.0066 | 0.0000 | 0.0197 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| n_steps | 2.1118 | 1.8882 | 2.3289 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| reflections | 0.0855 | 0.0461 | 0.1316 |
| task_success | 0.5893 | 0.5000 | 0.6696 |
| tool_selection_ok | 0.7589 | 0.6786 | 0.8304 |

## Failure Analysis

**Total Failures**: 46

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-1**: task_success=False
- **planner:cold_text-cold-2**: task_success=False
- **planner:cold_text-cold-3**: task_success=False
- **planner:cold_text-cold-5**: task_success=False
- **planner:cold_text-cold-9**: task_success=False
- **planner:cold_text-cold-10**: task_success=False
- **planner:cold_text-cold-11**: task_success=False
- ... and 36 more failures
